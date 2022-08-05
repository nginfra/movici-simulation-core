import json
import logging
import re
import sys
import typing as t
from multiprocessing import Process
from pathlib import Path
from unittest.mock import Mock, call, patch

import numpy as np
import pytest

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import Service
from movici_simulation_core.core.attribute import PUB, SUB
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.moment import Moment, TimelineInfo, get_timeline_info
from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import StartupFailure
from movici_simulation_core.messages import ErrorMessage, ModelMessage
from movici_simulation_core.networking.stream import MessageRouterSocket, Stream
from movici_simulation_core.settings import Settings
from movici_simulation_core.simulation import (
    ModelFromInstanceInfo,
    ModelFromTypeInfo,
    ModelRunner,
    ModelTypeInfo,
    ServiceInfo,
    ServiceRunner,
    ServiceTypeInfo,
    Simulation,
)
from movici_simulation_core.testing.dummy import DummyModel


class SimpleModel(TrackedModel):
    def __init__(self, config):
        super().__init__(config)
        self.mode = config["mode"]
        self.output_file = config.get("output")
        self.attr = None

    def setup(self, state: TrackedState, schema, **_):
        self.schema = schema
        mode = PUB if self.mode == "pub" else SUB
        self.attr = state.register_attribute(
            "dataset", "entity", AttributeSpec("attr", DataType(float, (), False)), flags=mode
        )

    def initialize(self, state: TrackedState):

        state.receive_update(
            {
                "dataset": {
                    "entity": {
                        "id": {"data": np.array([1])},
                        "attr": {"data": np.array([0.0])},
                    }
                }
            }
        )

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        if self.attr.flags & PUB:
            self.attr[0] = 1.0
        else:
            Path(self.output_file).write_bytes(
                EntityInitDataFormat(self.schema).dumps(state.to_dict())
            )

        return None

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_model_type("dummy", cls)


@pytest.fixture(autouse=True)
def reset_dummy_model_mocks():
    yield
    DummyModel.reset_mocks()


class DummyService(Service):
    stream: Stream[ModelMessage]

    def setup(
        self,
        *,
        settings: Settings,
        stream: Stream,
        logger: logging.Logger,
        socket: MessageRouterSocket
    ):
        pass

    def run(self):
        pass

    @classmethod
    def install(cls, sim: Simulation):
        pass


@pytest.fixture
def temp_output_file(tmp_path):
    return tmp_path / "test.json"


@pytest.fixture
def service_info():
    info = ServiceInfo("dummy", DummyService)
    yield info
    if info.process is not None:
        info.process.join()


@pytest.fixture
def model_info():
    info = ModelFromTypeInfo("model", DummyModel)
    yield info
    if info.process is not None:
        info.process.join()


@pytest.fixture
def settings():
    return Settings()


class TestServiceRunner:
    @pytest.fixture
    def runner(self, settings, service_info):
        return ServiceRunner(service_info, settings)

    def test_run_service_sets_process(self, runner, service_info):
        runner.start()
        assert isinstance(service_info.process, Process)

    def test_run_service_sets_address(self, runner, service_info):
        runner.start()
        assert re.match(r"tcp://127.0.0.1:\d+", service_info.address)

    def test_raises_when_service_doesnt_start(self, runner):
        runner.TIMEOUT = 0
        with pytest.raises(StartupFailure):
            runner.start()


class TestServiceRunnerEntryPoint:
    @pytest.fixture
    def runner(self, get_bound_socket, service_info, settings):
        rv = ServiceRunner(service_info, settings)
        rv._get_bound_socket = get_bound_socket
        return rv

    @pytest.fixture
    def get_bound_socket(self):
        return Mock(return_value=(Mock(), 1234))

    def test_entry_point_calls_for_socket(self, service_info, runner):
        runner.entry_point(Mock())
        assert runner._get_bound_socket.call_args == call(service_info.name)

    def test_entry_point_reports_socket_port(self, service_info, runner):
        connection = Mock()
        runner.entry_point(connection)
        assert connection.send.call_args == call(1234)

    def test_entry_point_sets_name(self, runner, settings, service_info):
        assert settings.name != service_info.name
        runner.entry_point(Mock())
        assert settings.name == service_info.name

    def test_entry_point_calls_service(self, settings):
        class MockService:
            setup = Mock()
            run = Mock(return_value=0)

        ServiceRunner(ServiceInfo("service", MockService), settings).entry_point(Mock())
        assert MockService.setup.call_count == 1
        assert MockService.setup.call_count == 1


class TestModelRunner:
    @pytest.fixture
    def settings(self):
        settings = Settings(
            service_discovery={
                "orchestrator": "tcp://127.0.0.1:8001",
                "update_data": "tcp://127.0.0.1:8002",
                "init_data": "tcp://127.0.0.1:8003",
            },
            
        )
        settings.timeline_info =TimelineInfo(0, 1, 0)
        return settings

    @pytest.fixture
    def stream_run(self):
        with patch.object(Stream, "run") as mock:
            yield mock

    @pytest.fixture
    def sys_exit(self):
        with patch.object(sys, "exit") as mock:
            yield mock

    @pytest.fixture
    def runner(self, settings, model_info, stream_run, sys_exit):
        runner = ModelRunner(model_info, settings, None)
        runner._get_orchestrator_socket = Mock()
        runner.close = Mock()
        return runner

    def test_run_model_sets_process(self, settings, runner, model_info):
        runner = ModelRunner(model_info, settings, None)
        runner.start()
        assert isinstance(model_info.process, Process)

    def test_entry_point_sets_timeline_info(self, runner):
        assert get_timeline_info() is None
        runner.entry_point()
        assert isinstance(get_timeline_info(), TimelineInfo)

    def test_entry_point_runs_stream(self, runner, stream_run):
        runner.entry_point()
        assert stream_run.call_count == 1

    def test_entry_point_handles_exception(self, runner, stream_run):
        stream_run.side_effect = ValueError
        runner.entry_point()
        error_resp = runner._get_orchestrator_socket().send.call_args[0][0]
        assert isinstance(error_resp, ErrorMessage)

    def test_shuts_down_model_on_exception(self, runner, stream_run):
        stream_run.side_effect = ValueError
        runner.entry_point()
        assert DummyModel.shutdown.call_count == 1

    def test_entry_point_exits_on_exception(self, runner, stream_run, sys_exit):
        stream_run.side_effect = ValueError
        runner.entry_point()
        assert sys_exit.call_args == call(1)


class TestSimulation:
    @pytest.fixture
    def simulation(self):
        return Simulation(use_global_plugins=False)

    def test_use_global_plugins_by_default(self):
        sim = Simulation()
        assert len(sim.service_types) > 0

    def test_dont_use_global_plugins(self, simulation):
        sim = Simulation(use_global_plugins=False)
        assert len(sim.service_types) == 0

    @pytest.mark.parametrize(
        "model, expected_info",
        [
            (DummyModel, ModelFromTypeInfo),
            (DummyModel({}), ModelFromInstanceInfo),
        ],
    )
    def test_add_model_activates_model(self, model, expected_info, simulation):
        simulation.add_model("model", model)
        assert isinstance(simulation.active_modules["model"], expected_info)

    def test_add_model_adds_schema_attributes(self, simulation):
        spec = AttributeSpec("attr", data_type=DataType(float, (), False))

        class ModelWithAttributes(DummyModel):
            @classmethod
            def get_schema_attributes(cls) -> t.Sequence[AttributeSpec]:
                return [spec]

        simulation.add_model("model", ModelWithAttributes)
        assert simulation.schema[spec.name] is spec

    def test_can_configure_simulation(self, simulation, settings):
        simulation.configure(
            {
                "simulation_info": {
                    "start_time": 0,
                    "time_scale": 1,
                    "reference_time": 0,
                    "duration": 1,
                },
                "models": [{"name": "dummy_1", "type": "dummy"}],
                "services": ["my_service"],
            }
        )
        assert simulation.settings.timeline_info == TimelineInfo(0, 1, 0, 1)
        assert simulation.settings.models == [{"name": "dummy_1", "type": "dummy"}]
        assert simulation.settings.model_names == ["dummy_1"]
        assert simulation.settings.service_types == ["my_service"]

    def test_can_set_timeline_info(self, simulation):
        info = TimelineInfo(10, 10, 10)
        simulation.set_timeline_info(info)
        assert simulation.settings.timeline_info == info

    def test_use_plugin(self, simulation):
        plugin = Mock()
        simulation.use(plugin)
        assert plugin.install.call_args == call(simulation)

    def test_register_service(self, simulation):
        simulation.register_service("myservice", DummyService)
        assert simulation.service_types["myservice"] == ServiceTypeInfo(
            "myservice", DummyService, auto_use=False, daemon=True
        )

    def test_register_service_with_non_defaults(self, simulation):
        simulation.register_service("myservice", DummyService, auto_use=True, daemon=False)
        assert simulation.service_types["myservice"] == ServiceTypeInfo(
            "myservice", DummyService, auto_use=True, daemon=False
        )

    def test_register_model_type(self, simulation):
        simulation.register_model_type("dummy", DummyModel)
        assert simulation.model_types["dummy"] == ModelTypeInfo("dummy", DummyModel)

    def test_register_model_updates_schema(self, simulation):
        spec = AttributeSpec("attr", data_type=DataType(float, (), False))

        class ModelWithAttributes(DummyModel):
            @classmethod
            def get_schema_attributes(cls) -> t.Sequence[AttributeSpec]:
                return [spec]

        simulation.register_model_type("dummy", ModelWithAttributes)
        assert simulation.schema[spec.name] is spec

    def test_register_attributes(self, simulation):
        assert len(simulation.schema) == 0
        simulation.register_attributes(
            [
                AttributeSpec("attr", data_type=DataType(float, (), False)),
                AttributeSpec("attr2", data_type=DataType(float, (), False)),
            ]
        )
        assert len(simulation.schema) == 2

    def test_register_duplicate_attribute(self, simulation):
        assert len(simulation.schema) == 0
        simulation.register_attributes(
            [
                AttributeSpec("attr", data_type=DataType(float, (), False)),
                AttributeSpec("attr", data_type=DataType(float, (), False)),
            ]
        )
        assert len(simulation.schema) == 1

    @pytest.mark.parametrize(
        "incompatible",
        [
            AttributeSpec("attr", data_type=DataType(int, (), False)),
            AttributeSpec("attr", data_type=DataType(float, (), False), enum_name="bla"),
        ],
    )
    def test_register_incompatible_attributes(self, simulation, incompatible):
        attrs = [
            AttributeSpec("attr", data_type=DataType(float, (), False)),
            incompatible,
        ]
        with pytest.raises(TypeError):
            simulation.register_attributes(attrs)


def test_full_simulation_run(temp_output_file, tmp_path):
    sim = Simulation(data_dir=tmp_path, debug=True)

    sim.add_model("pub", SimpleModel({"mode": "pub"}))
    sim.add_model(
        "sub", SimpleModel, {"mode": "sub", "output": str(temp_output_file)}
    )  # defer instantiation to subprocess

    sim.set_timeline_info(TimelineInfo(reference=0, time_scale=1, start_time=0))
    sim.run()

    # If this test fails on the exit_code assert below, it is recommended to set a breakpoint at
    # the `sys.exit` call in `ModelRunner.entry_point` to be able to see the
    # `traceback.format_exc()` since the logger output from multiprocessing may not be not
    # available
    assert sim.exit_code == 0
    assert json.loads(temp_output_file.read_text()) == {
        "dataset": {"entity": {"id": [1], "attr": [1.0]}}
    }
