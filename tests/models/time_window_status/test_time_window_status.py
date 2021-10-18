import typing as t

import numpy as np
import pytest

from movici_simulation_core.core.schema import PropertySpec, DataType, AttributeSchema
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.time_series import TimeSeries
from movici_simulation_core.models.time_window_status.dataset import (
    TimeWindowEntity,
    TimeWindowStatusEntity,
    ScheduleEvent,
    Connection,
)
from movici_simulation_core.models.time_window_status.time_window_status import TimeWindowStatus
from movici_simulation_core.utils.moment import TimelineInfo, Moment

T = t.TypeVar("T", bound=EntityGroup)


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def convert_data_to_numpy(global_schema):
    def _convert(data: dict):
        return EntityInitDataFormat(global_schema).load_json(data)

    return _convert


def _get_entity(dataset_name: str, entity_name: str, cls: t.Type[T], state: TrackedState) -> T:
    return state.register_entity_group(dataset_name, cls(entity_name))


@pytest.fixture
def get_source_entity(state):
    def _get(dataset_name: str, entity_name: str) -> TimeWindowEntity:
        source = _get_entity(dataset_name, entity_name, cls=TimeWindowEntity, state=state)
        source.time_window_begin = state.register_property(
            dataset_name, entity_name, PropertySpec("begin", data_type=DataType(str))
        )

        source.time_window_end = state.register_property(
            dataset_name, entity_name, PropertySpec("end", data_type=DataType(str))
        )

        return source

    return _get


@pytest.fixture
def get_target_entity(state):
    def _get(dataset_name: str, entity_name: str) -> TimeWindowStatusEntity:
        target = _get_entity(dataset_name, entity_name, cls=TimeWindowStatusEntity, state=state)
        target.time_window_status = state.register_property(
            dataset_name, entity_name, PropertySpec("status", data_type=DataType(bool))
        )
        return target

    return _get


@pytest.fixture
def timeline_info():
    return TimelineInfo(0, 1, 0)


@pytest.fixture
def create_init_data(convert_data_to_numpy):
    def iter_attribute_data(attributes: dict):
        for attr in attributes.values():
            if isinstance(attr, dict):
                yield from iter_attribute_data(attr)
            yield attr

    def _create(entity: EntityGroup, attributes: dict):
        all_attributes = iter_attribute_data(attributes)
        num_entities = len(next(all_attributes))

        if "id" not in attributes:
            attributes = {"id": list(range(num_entities)), **attributes}

        return convert_data_to_numpy(
            {
                entity.dataset_name: {
                    entity.__entity_name__: attributes,
                }
            }
        )

    return _create


@pytest.fixture
def create_source_data(state, source_entity, create_init_data):
    def _create(data: dict, entity=None):
        entity = entity or source_entity
        state.receive_update(create_init_data(entity, data))

    return _create


@pytest.fixture
def create_target_data(state, target_entity, create_init_data):
    def _create(data: dict, entity=None):
        entity = entity or target_entity
        state.receive_update(create_init_data(entity, data))

    return _create


@pytest.fixture(autouse=True)
def global_schema(global_schema: AttributeSchema):
    global_schema.add_attributes(
        [
            PropertySpec("begin", data_type=DataType(str)),
            PropertySpec("end", data_type=DataType(str)),
            PropertySpec("status", data_type=DataType(bool)),
        ]
    )
    return global_schema


@pytest.fixture
def source_entity(state, get_source_entity):
    dataset_name, entity_name = "dataset_a", "source"
    return get_source_entity(dataset_name, entity_name)


@pytest.fixture
def target_entity(state, get_target_entity):
    dataset_name, entity_name = "dataset_b", "target"
    return get_target_entity(dataset_name, entity_name)


@pytest.fixture
def tws(
    source_entity,
    target_entity,
    timeline_info,
    create_source_data,
    create_target_data,
):
    return TimeWindowStatus(source_entity, [target_entity], timeline_info)


@pytest.mark.parametrize(
    "to_dataset, to_references, reference, expected",
    [
        (["dataset_a"], [["1"]], ["1"], [0]),
        (["dataset_a"], [["2", "3"]], ["1", "2", "3"], [1, 2]),
    ],
)
def test_tws_resolve_single_connection(
    source_entity,
    target_entity,
    create_source_data,
    create_target_data,
    tws,
    to_dataset,
    to_references,
    reference,
    expected,
):
    create_source_data(
        {"connection_properties": {"to_dataset": to_dataset, "to_references": to_references}},
    )
    create_target_data({"reference": reference})
    tws.initialize()
    connections = source_entity.get_connections(0)
    assert len(connections) == 1
    assert connections[0].connected_entities == target_entity
    np.testing.assert_array_equal(connections[0].connected_indices, expected)


def test_tws_resolve_self_connection(
    source_entity,
    create_source_data,
    get_target_entity,
    timeline_info,
):
    target: TimeWindowStatusEntity = get_target_entity("dataset_a", "source")
    create_source_data({"reference": ["1", "2"]})

    tws = TimeWindowStatus(source_entity, [target], timeline_info)
    tws.initialize()
    for i in range(len(source_entity)):
        connections = source_entity.get_connections(i)
        assert len(connections) == 1
        assert connections[0].connected_entities == target
        np.testing.assert_array_equal(connections[0].connected_indices, [i])


def test_resolve_multiple_foreign_connections(
    source_entity,
    target_entity,
    create_source_data,
    create_target_data,
    create_init_data,
    state,
    get_target_entity,
    timeline_info,
):
    target_2 = get_target_entity("dataset_c", "target")
    target_2.time_window_status = state.register_property(
        "dataset_c", "target", PropertySpec("status", data_type=DataType(bool))
    )

    create_source_data(
        {
            "connection_properties": {
                "to_dataset": [
                    "dataset_a",
                    "dataset_b",
                ],
                "to_references": [["1"], ["2"]],
            },
        },
    )
    create_target_data({"reference": ["1"]})

    state.receive_update(create_init_data(target_2, {"reference": ["2"]}))

    tws = TimeWindowStatus(source_entity, [target_entity, target_2], timeline_info)
    tws.initialize()
    connected_entity_groups = [
        set(c.connected_entities for c in source_entity.get_connections(i))
        for i in range(len(source_entity))
    ]
    assert connected_entity_groups == [{target_entity}, {target_2}]


def test_resolve_self_and_foreign_connection(
    source_entity,
    target_entity,
    create_source_data,
    create_target_data,
    get_target_entity,
    timeline_info,
):
    self_target = get_target_entity("dataset_a", "source")
    create_source_data(
        {
            "connection_properties": {"to_dataset": ["dataset_a"], "to_references": [["2"]]},
        },
    )
    create_target_data({"reference": ["2"]})
    tws = TimeWindowStatus(source_entity, [self_target, target_entity], timeline_info)
    tws.initialize()
    connected_entity_groups = set(c.connected_entities for c in source_entity.get_connections(0))
    assert connected_entity_groups == {self_target, target_entity}


@pytest.mark.parametrize(
    "source_data, expected",
    [
        (
            {"begin": ["2021", "2022"], "end": ["2023", "2024"]},
            [
                ("2021", ScheduleEvent(True, 0)),
                ("2022", ScheduleEvent(True, 1)),
                ("2023", ScheduleEvent(False, 0)),
                ("2024", ScheduleEvent(False, 1)),
            ],
        ),
        (
            {"begin": [None, "2022", None], "end": [None, "2024", None]},
            [
                ("2022", ScheduleEvent(True, 1)),
                ("2024", ScheduleEvent(False, 1)),
            ],
        ),
        (
            {
                "begin": [None, None],
                "end": [None, None],
            },
            [],
        ),
    ],
)
def test_resolve_schedule(
    create_source_data,
    tws,
    timeline_info,
    source_data,
    expected,
):
    expected = [(timeline_info.string_to_timestamp(exp[0]), exp[1]) for exp in expected]
    create_source_data(source_data)

    tws.initialize()
    assert list(reversed(tws.schedule)) == expected


@pytest.mark.parametrize(
    "initial_event_count, conn_indices, is_begin_event, expected",
    [
        (np.array([0, 0]), [0], True, [True, False]),
        (np.array([0, 0]), [0, 1], True, [True, True]),
        (np.array([1, 0]), [0], True, [True, False]),
        (np.array([1, 0]), [1], True, [True, True]),
        (np.array([1, 1]), [0], False, [False, True]),
        (np.array([2, 0]), [0], True, [True, False]),
    ],
)
def test_process_event(
    tws,
    create_source_data,
    create_target_data,
    source_entity,
    target_entity,
    initial_event_count,
    conn_indices,
    is_begin_event,
    expected,
):
    create_target_data({"reference": ["1", "2"]})
    target_entity.event_count = initial_event_count
    source_entity.connections = [
        [
            Connection(target_entity, conn_indices),
        ]
    ]
    event = ScheduleEvent(is_begin_event, 0)
    tws.process_event(event)
    tws.update_statuses()

    np.testing.assert_array_equal(target_entity.time_window_status.array, expected)


@pytest.mark.parametrize(
    "events, timestamp, expected",
    [
        ([(1, ScheduleEvent(True, 0))], 1, [True]),
        ([(1, ScheduleEvent(True, 0)), (2, ScheduleEvent(False, 0))], 1, [True]),
        ([(1, ScheduleEvent(True, 0)), (2, ScheduleEvent(False, 0))], 2, [False]),
        ([(1, ScheduleEvent(True, 0))], 0, [False]),
    ],
)
def test_update_one_event(
    source_entity, create_target_data, target_entity, tws, events, timestamp, expected
):
    create_target_data({"reference": ["1"]})
    target_entity.initialize_event_count()

    tws.schedule = TimeSeries(events)
    source_entity.connections = [[Connection(target_entity, [0])]]
    tws.update(Moment(timestamp))
    np.testing.assert_array_equal(target_entity.time_window_status.array, expected)
