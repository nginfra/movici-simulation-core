import json
import typing as t
from unittest.mock import Mock, call

import numpy as np
import pytest

from movici_simulation_core.base_models.tracked_model import TrackedModel, TrackedModelAdapter
from movici_simulation_core.core.attribute import INIT, PUB, SUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, DataType
from movici_simulation_core.core.serialization import dump_update, load_update
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.messages import (
    NewTimeMessage,
    QuitMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.model_connector.init_data import FileType
from movici_simulation_core.testing.helpers import dataset_data_to_numpy, dataset_dicts_equal


@pytest.fixture
def additional_attributes():
    return [AttributeSpec("init_attr", data_type=DataType(int, (), False))]


@pytest.fixture
def entity_group():
    init_spec = AttributeSpec("init_attr", data_type=DataType(int, (), False))
    sub_spec = AttributeSpec("sub_attr", data_type=DataType(int, (), False))
    pub_spec = AttributeSpec("pub_attr", data_type=DataType(int, (), False))

    class MyEntity(EntityGroup, name="my_entities"):
        init_attr = field(init_spec, flags=INIT)
        sub_attr = field(sub_spec, flags=SUB)
        pub_attr = field(pub_spec, flags=PUB)

    return MyEntity


@pytest.fixture
def model(entity_group):
    class Model(TrackedModel):
        def __init__(self, config=None):
            super().__init__(config)
            self.entity = None

        def setup(self, state: TrackedState, **_):
            self.entity = state.register_entity_group("dataset", entity_group)

        initialize = Mock()
        update = Mock()
        new_time = Mock()
        shutdown = Mock()
        install = Mock()

    return Model()


@pytest.fixture
def get_adapter(settings, entity_group):
    def _get_adapter(model, override_settings=None):
        adapter = TrackedModelAdapter(model, settings=override_settings or settings, logger=Mock())
        adapter.set_schema(
            AttributeSchema(
                [
                    AttributeSpec("id", DataType(int)),
                    entity_group.init_attr.spec,
                    entity_group.pub_attr.spec,
                    entity_group.sub_attr.spec,
                ]
            )
        )
        return adapter

    return _get_adapter


@pytest.fixture
def adapter(model, get_adapter) -> TrackedModelAdapter:
    return get_adapter(model)


@pytest.fixture
def create_update(entity_group):
    def _create(payload):
        return dump_update(
            dataset_data_to_numpy({"dataset": {entity_group.__entity_name__: payload}})
        )

    return _create


@pytest.fixture
def update(create_update):
    return create_update(
        {
            "id": [1, 2],
            "sub_attr": [5, 6],
        }
    )


@pytest.fixture
def init_data_handler(tmp_path):
    path = tmp_path / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "dataset": {
                    "my_entities": {
                        "id": [1, 2],
                        "init_attr": [3, 4],
                    },
                }
            }
        )
    )

    class FakeInitDataHandler:
        def get(self, key=None):
            if key != "dataset":
                return None, None
            return FileType.JSON, path

    return FakeInitDataHandler()


def test_base_model(model, adapter, update, init_data_handler):
    assert not adapter.model_initialized
    assert model.initialize.call_count == 0
    adapter.initialize(init_data_handler)
    assert adapter.model_initialized
    assert model.initialize.call_args == call(state=adapter.state)

    assert not adapter.model_ready_for_update
    adapter.update(UpdateMessage(0), None)
    assert not adapter.model_ready_for_update
    assert model.update.call_count == 0

    adapter.update(UpdateMessage(0), update)
    assert adapter.model_ready_for_update
    assert model.update.call_count == 1


def test_data_mask(adapter, init_data_handler):
    assert adapter.initialize(init_data_handler) == {
        "sub": {"dataset": {"my_entities": ["init_attr", "sub_attr"]}},
        "pub": {"dataset": {"my_entities": ["pub_attr"]}},
    }


def test_new_time(adapter, model):
    assert model.new_time.call_count == 0
    adapter.new_time(NewTimeMessage(0))
    assert model.new_time.call_count == 1


def test_new_time_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.new_time(NewTimeMessage(1))


def test_new_time_raises_when_not_ready_for_updates(adapter):
    adapter.model_initialized = True
    with pytest.raises(RuntimeError):
        adapter.new_time(NewTimeMessage(1))


def test_formats_error_message_when_not_ready(adapter):
    adapter.state.register_attribute(
        "dataset", "my_entities", AttributeSpec("init_attr", float), flags=INIT
    )
    with pytest.raises(RuntimeError) as e:
        adapter.new_time(NewTimeMessage(1))
    assert "dataset/my_entities/init_attr" in str(e.value)


def test_formats_error_message_from_entity_group_when_not_ready(adapter, entity_group):
    adapter.state.register_entity_group("dataset", entity_group)
    adapter.state.register_entity_group("dataset2", entity_group(optional=True))
    with pytest.raises(RuntimeError) as e:
        adapter.new_time(NewTimeMessage(1))
    assert "dataset/my_entities/init_attr" in str(e.value)
    assert "dataset/my_entities/pub_attr" not in str(e.value)
    assert "dataset2/my_entities/init_attr" not in str(e.value)


def test_formats_error_message_from_optional_entity_group_with_entities(
    adapter, entity_group, init_data_handler
):
    entity_group.__optional__ = True
    adapter.new_time(NewTimeMessage(0))
    adapter.initialize(init_data_handler)
    adapter.state.register_entity_group("dataset2", entity_group)
    with pytest.raises(RuntimeError) as e:
        adapter.new_time(NewTimeMessage(1))

    assert "dataset/my_entities/init_attr" not in str(e.value)
    assert "dataset/my_entities/sub_attr" in str(e.value)
    assert "dataset2/my_entities/init_attr" not in str(e.value)
    assert "dataset2/my_entities/sub_attr" not in str(e.value)


def test_not_ready_on_extra_required_entity_group(adapter, entity_group, init_data_handler):
    adapter.state.register_entity_group("dataset2", entity_group)
    adapter.initialize(init_data_handler)
    assert not adapter.model_initialized


def test_ready_on_optional_entity_group(adapter, entity_group, init_data_handler):
    adapter.state.register_entity_group("dataset2", entity_group(optional=True))
    adapter.initialize(init_data_handler)
    assert adapter.model_initialized


def test_shutdown_raises_when_not_initialized(adapter):
    with pytest.raises(RuntimeError):
        adapter.close(QuitMessage())


def test_shutdown_raises_when_not_ready_for_updates(adapter):
    adapter.model_initialized = True
    with pytest.raises(RuntimeError):
        adapter.close(QuitMessage())


def test_shutdown_doesnt_raise_when_quitting_due_to_failure(adapter):
    adapter.close(QuitMessage(due_to_failure=True))  # should not raise


def test_new_time_accepted_when_ready_for_updates(adapter, init_data_handler, update, model):
    adapter.new_time(NewTimeMessage(0))
    adapter.initialize(init_data_handler)
    adapter.update(UpdateMessage(0), update)
    adapter.new_time(NewTimeMessage(1))
    assert model.new_time.call_args == call(adapter.state, Moment(1))


def test_shutdown_succeeds_when_ready_for_updates(adapter, init_data_handler, update, model):
    adapter.new_time(NewTimeMessage(0))
    adapter.initialize(init_data_handler)
    adapter.update(UpdateMessage(0), update)
    adapter.close(QuitMessage())
    assert model.shutdown.call_count == 1


def test_full_run(model, get_adapter, update, init_data_handler, entity_group):
    class Model(TrackedModel):
        def __init__(self):
            self.entity_group = None

        def setup(self, state: TrackedState, **_):
            self.entity_group = state.register_entity_group("dataset", entity_group)

        def initialize(self, state: TrackedState):
            self.entity_group.pub_attr[:] = -1

        def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
            self.entity_group.pub_attr[:] = moment.timestamp
            return Moment(moment.timestamp + 1)

        new_time = Mock()
        shutdown = Mock()
        install = Mock()

    model = Model()
    adapter = get_adapter(model)
    adapter.initialize(init_data_handler)

    def compare_update_result(timestamp, raw_update, expected):
        raw_result = adapter.update(UpdateMessage(timestamp), raw_update)[0]
        assert dataset_dicts_equal(
            load_update(raw_result) if raw_result is not None else {},
            dataset_data_to_numpy(expected),
        )

    compare_update_result(
        0, None, {"dataset": {"my_entities": {"id": [1, 2], "pub_attr": [-1, -1]}}}
    )
    compare_update_result(0, None, {})
    compare_update_result(
        0, update, {"dataset": {"my_entities": {"id": [1, 2], "pub_attr": [0, 0]}}}
    )
    compare_update_result(
        1, update, {"dataset": {"my_entities": {"id": [1, 2], "pub_attr": [1, 1]}}}
    )


def test_handles_not_ready(adapter, model, init_data_handler):
    model.initialize.side_effect = NotReady()
    adapter.initialize(init_data_handler)

    assert model.initialize.call_count == 1
    assert not adapter.model_initialized


class TestUpdate:
    @pytest.fixture
    def filtered_update(self):
        return dump_update({})

    def test_skips_calculation_on_empty_cascading_update(self, adapter, model, filtered_update):
        adapter.update(UpdateMessage(1, "bla", "bla"), filtered_update)
        assert not model.update.call_count

    def test_remembers_next_time_when_skipping_cascading_update(
        self, adapter, model, filtered_update
    ):
        model.update.return_value = 12
        adapter.update(UpdateMessage(1), None)
        result = adapter.update(UpdateMessage(1), filtered_update)
        assert result == (None, 12)


class TestUpdateSeries:
    @pytest.fixture
    def message(self):
        return UpdateSeriesMessage(
            updates=[UpdateMessage(0, "key_a", "address"), UpdateMessage(0, "key_b", "address")]
        )

    @pytest.fixture
    def data(self, create_update):
        return [
            create_update({"id": [1], "sub_attr": [1]}),
            create_update({"id": [2], "sub_attr": [2]}),
        ]

    @pytest.fixture
    def adapter(self, adapter, init_data_handler):
        adapter.initialize(init_data_handler)
        return adapter

    def test_calls_model_once(self, adapter, model, message, data):
        adapter.update_series(message, data)
        assert model.update.call_count == 1

    def test_processes_all_data(self, adapter, model, message, data):
        adapter.update_series(message, data)
        np.testing.assert_array_equal(
            adapter.state.attributes["dataset"]["my_entities"]["sub_attr"].array, [1, 2]
        )
