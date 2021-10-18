import json
import logging
from unittest.mock import Mock, call

import pytest

from movici_simulation_core.networking.messages import GetDataMessage
from movici_simulation_core.networking.stream import Stream
from movici_simulation_core.services.init_data.service import InitDataService
from movici_simulation_core.utils.settings import Settings


@pytest.fixture
def stream():
    return Mock(Stream)


@pytest.fixture
def logger():
    return Mock(logging.Logger)


@pytest.fixture
def data_dir(tmp_path):
    tmp_path.joinpath("dataset.json").write_text(json.dumps({"some": "data"}))
    return tmp_path


@pytest.fixture
def settings(data_dir):
    return Settings(data_dir=data_dir)


@pytest.fixture
def init_data_service(stream, settings, logger):
    service = InitDataService()
    service.setup(stream=stream, logger=logger, settings=settings)
    return service


def test_install():
    simulation = Mock()
    InitDataService.install(simulation)
    assert simulation.register_service.call_args == call(
        "init_data", InitDataService, auto_use=True
    )


def test_setup_registers_handler(stream, init_data_service):
    assert stream.set_handler.call_count == 1


def test_run_starts_stream(stream, init_data_service):
    init_data_service.run()
    assert stream.run.call_count == 1


def test_get(init_data_service, data_dir):
    get = GetDataMessage("dataset")
    resp = init_data_service.handle_message(get)
    assert resp.path == data_dir / "dataset.json"
