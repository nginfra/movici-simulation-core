from logging import WARNING
from unittest.mock import Mock, call

import numpy as np
import pytest

from movici_simulation_core.core.attribute import (
    INIT,
    INITIALIZE,
    OPT,
    PUB,
    PUBLISH,
    REQUIRED,
    SUB,
    SUBSCRIBE,
    AttributeField,
)
from movici_simulation_core.core.attribute_spec import AttributeSpec
from movici_simulation_core.core.data_type import UNDEFINED, DataType
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import (
    EntityDataHandler,
    StateProxy,
    TrackedState,
    ensure_path,
    filter_attrs,
    parse_special_values,
)
from movici_simulation_core.testing.helpers import (
    dataset_data_to_numpy,
    dataset_dicts_equal,
    get_attribute,
)


class MyEntity(EntityGroup, name="my_entities"):
    attr = AttributeField(
        spec=AttributeSpec("attr", data_type=DataType(int, (), False)), flags=PUB
    )


class Pub(EntityGroup, name="pub_entities"):
    pub_attr = get_attribute(name="pub_attr", flags=PUB)


class Sub(EntityGroup, name="sub_entities"):
    sub_attr = get_attribute(name="sub_attr", flags=SUB)
    init_attr = get_attribute(name="init_attr", flags=INIT)
    opt_attr = get_attribute(name="opt_attr", flags=OPT)


@pytest.fixture
def dataset_name():
    return "dataset"


@pytest.fixture
def state(dataset_name):
    state = TrackedState()
    state.register_dataset(dataset_name, [MyEntity])
    return state


@pytest.fixture
def entity(state, dataset_name):
    return state.register_entity_group(dataset_name, MyEntity)


def test_can_add_dataset(state: TrackedState, dataset_name):
    assert state.attributes.keys() == {dataset_name}
    assert len(state.attributes[dataset_name]) == 1
    assert state.attributes[dataset_name].keys() == {"my_entities"}


def test_can_add_dataset_with_multiple_entities(state: TrackedState):
    class OtherEntity(EntityGroup, name="other_entities"):
        sub_attr = get_attribute(name="sub_attr", flags=SUB)

    state.register_dataset("large_dataset", [MyEntity, OtherEntity])
    assert {k for k in state.attributes["large_dataset"].keys()} == {
        "my_entities",
        "other_entities",
    }


def test_can_add_dataset_with_entity_group_instances(state):
    entities = [MyEntity("a"), MyEntity("b")]

    assert state.register_dataset("dynamic_dataset", entities) == entities
    assert all(e.state.state is state for e in entities)


def test_raises_when_dataset_already_exists(state, dataset_name):
    with pytest.raises(ValueError) as e:
        state.register_dataset(dataset_name, [])
    assert "already exists" in str(e.value)


@pytest.mark.parametrize("entity_group", [EntityGroup, EntityGroup()])
def test_raises_on_nameless_entity_group(state, entity_group):
    with pytest.raises(ValueError) as e:
        state.register_dataset("some_dataset", [entity_group])
    assert "must have __entity_name__ defined" in str(e.value)


@pytest.mark.parametrize("entity_group", [MyEntity, MyEntity("bla")])
def test_register_entity_group_to_existing_dataset(state, dataset_name, entity_group):
    state.register_entity_group(dataset_name, entity_group)
    assert entity_group.__entity_name__ in state.attributes[dataset_name]


def test_can_create_attribute(state, dataset_name):
    attr_name = "new_attr"
    spec = AttributeSpec(attr_name, data_type=DataType(int, (), False))
    state.register_attribute(
        dataset_name,
        MyEntity.__entity_name__,
        spec=spec,
        flags=OPT,
    )
    assert spec.name in state.attributes[dataset_name][MyEntity.__entity_name__]


def test_can_get_attribute(state, dataset_name):
    attr_name = "new_attr"
    spec = AttributeSpec(attr_name, data_type=DataType(int, (), False))
    state.register_attribute(
        dataset_name,
        MyEntity.__entity_name__,
        spec=spec,
        flags=OPT,
    )
    assert state.get_attribute(dataset_name, MyEntity.__entity_name__, spec.name).flags == OPT


@pytest.mark.parametrize(
    "dataset, entity_type",
    [
        ("invalid_dataset", MyEntity.__entity_name__),
        ("dataset", "invalid_entity_group"),
    ],
)
def test_returns_none_when_not_found(state, dataset, entity_type):
    assert state._get_entity_group(dataset, entity_type) is None


def test_is_ready_for_check_initialized(state):
    class FakeEntity(EntityGroup):
        sub = get_attribute(name="sub_attr", flags=SUB)
        pub = get_attribute(name="pub_attr", flags=PUB)

    entity = FakeEntity(name="a")
    state.register_entity_group("some_dataset", entity)
    entity.sub.is_initialized = Mock()
    entity.pub.is_initialized = Mock()

    state.is_ready_for(REQUIRED)
    assert entity.sub.is_initialized.call_count == 1
    assert entity.pub.is_initialized.call_count == 0


@pytest.mark.parametrize(
    ["attr_flag", "initial_data", "ready_flags", "expected"],
    [
        (INIT, None, INITIALIZE, False),
        (INIT, None, REQUIRED, False),  # can only be ready for SUB if also ready for INIT
        (SUB, None, INITIALIZE, True),
        (INIT, dataset_data_to_numpy({"id": [1], "attr": [1]}), INITIALIZE, True),
        (
            INIT,
            dataset_data_to_numpy({"id": [1, 2], "attr": [1, UNDEFINED[int]]}),
            INITIALIZE,
            False,
        ),
        (SUB, dataset_data_to_numpy({"id": [1], "attr": [1]}), REQUIRED, True),
        (INIT, dataset_data_to_numpy({"id": [1]}), INITIALIZE, False),
    ],
)
def test_is_ready_for(
    dataset_name, state, attr_flag: int, initial_data: dict, ready_flags: int, expected: bool
):
    attr = state.register_attribute(
        dataset_name,
        MyEntity.__entity_name__,
        spec=AttributeSpec("attr", data_type=DataType(int, (), False)),
        flags=attr_flag,
    )
    if initial_data:
        EntityDataHandler(
            state._get_entity_group(dataset_name, MyEntity.__entity_name__), attr.index
        ).receive_update(initial_data)
    assert state.is_ready_for(ready_flags) == expected


@pytest.mark.parametrize(
    ["initial_data", "optional", "expected"],
    [
        (None, True, True),
        (None, False, False),
        (dataset_data_to_numpy({"id": [1], "attr": [1]}), True, True),
        (dataset_data_to_numpy({"id": [1]}), True, False),
        (dataset_data_to_numpy({"id": []}), True, True),
        (dataset_data_to_numpy({"id": [1]}), False, False),
        (dataset_data_to_numpy({"id": [1], "attr": [1]}), False, True),
    ],
)
def test_is_ready_for_with_optional_entity_group(initial_data, optional, expected):
    state = TrackedState()

    class FakeEntity(EntityGroup):
        __optional__ = optional
        attr = get_attribute(name="attr", flags=INIT)

    entity = FakeEntity(name="a")
    state.register_entity_group("some_dataset", entity)
    if initial_data:
        EntityDataHandler(
            state._get_entity_group("some_dataset", entity.__entity_name__), entity.index
        ).receive_update(initial_data)
    assert state.is_ready_for(INITIALIZE) == expected


def test_get_data_mask():
    state = TrackedState()
    state.register_dataset("pub_dataset", [Pub])
    state.register_dataset("sub_dataset", [Sub])
    assert state.get_data_mask() == {
        "pub": {"pub_dataset": {"pub_entities": ["pub_attr"]}},
        "sub": {"sub_dataset": {"sub_entities": ["sub_attr", "init_attr", "opt_attr"]}},
    }


@pytest.fixture
def tracked_entity(state, dataset_name):
    class SomeEntity(EntityGroup, name="some_entities"):
        pub_attr = get_attribute(name="pub_attr", flags=PUB)
        sub_attr = get_attribute(name="sub_attr", flags=SUB)
        init_attr = get_attribute(name="init_attr", flags=INIT)
        opt_attr = get_attribute(name="opt_attr", flags=OPT)

    entity = SomeEntity()
    state.register_entity_group(dataset_name, entity)
    state.receive_update(
        {dataset_name: {entity.__entity_name__: dataset_data_to_numpy({"id": [1, 2, 3]})}}
    )
    for field in entity.attributes.values():
        attr = entity.get_attribute(field.name)
        attr[0] = 1
        assert np.any(attr.changed)

    return entity


@pytest.mark.parametrize(
    "flag, reset_fields, not_reset_fields",
    [
        (PUBLISH, ("pub_attr",), ("sub_attr", "init_attr", "opt_attr")),
        (
            SUBSCRIBE,
            ("sub_attr", "init_attr", "opt_attr"),
            ("pub_attr",),
        ),
    ],
)
def test_reset_tracked_changes(state, tracked_entity, flag, reset_fields, not_reset_fields):
    state.reset_tracked_changes(flag)
    for field in reset_fields:
        assert not np.any(getattr(tracked_entity, field).changed)

    for field in not_reset_fields:
        assert np.any(getattr(tracked_entity, field).changed)


@pytest.fixture
def update(dataset_name, entity):
    return {
        dataset_name: {
            MyEntity.__entity_name__: {
                "id": {"data": np.array([9])},
                MyEntity.attr.spec.name: {"data": np.array([47])},
            }
        }
    }


@pytest.fixture
def other_update(dataset_name, entity):
    return {
        dataset_name: {
            MyEntity.__entity_name__: {
                "id": {"data": np.array([9])},
                MyEntity.attr.spec.name: {"data": np.array([42])},
            }
        }
    }


def test_receive_update_sets_data(state, entity, update):
    state.receive_update(update)
    assert entity.attr[0] == 47


def test_first_update_creates_index(state, entity, update):
    state.receive_update(update)
    assert entity.get_indices([9]) == 0


def test_receive_initial_doesnt_mark_as_changed(state, entity, update):
    state.receive_update(update, is_initial=True)
    assert not entity.attr.changed
    assert not state.generate_update()


def test_tracks_changes_on_update(state, entity, update, other_update):
    state.receive_update(update)
    state.receive_update(other_update)
    assert np.any(entity.attr.changed)
    assert state.generate_update()


def test_update_ignore_received_extra_dataset(state, entity, update, dataset_name):
    update["other_dataset"] = update.pop(dataset_name)
    state.receive_update(update)
    assert len(entity) == 0


def test_update_ignore_received_extra_entity_group(state, entity, update, dataset_name):
    entity = state.register_entity_group(dataset_name, MyEntity)
    update[dataset_name]["other_entities"] = update[dataset_name].pop(entity.__entity_name__)
    state.receive_update(update)
    assert len(entity) == 0


def test_ensure_path():
    d = {}
    path = ["a", "b", "c"]
    ensure_path(d, path)
    assert isinstance(d["a"]["b"]["c"], dict)


def test_ensure_path_doesnt_overwrite():
    d = {"a": {"d": None}}
    path = ["a", "b"]
    ensure_path(d, path)
    assert "d" in d["a"]


class TestEntityUpdateHandler:
    @pytest.fixture
    def entity_type(self):
        return "my_entities"

    @pytest.fixture
    def initial_data(self, dataset_name, entity_type):
        return dataset_data_to_numpy(
            {
                dataset_name: {
                    entity_type: {
                        "id": [1, 2, 3],
                        "attr": [4, 5, 6],
                    },
                }
            }
        )

    @pytest.fixture
    def update_with_new_attr(self, dataset_name, entity_type):
        return dataset_data_to_numpy(
            {
                dataset_name: {
                    entity_type: {
                        "id": [1, 2, 3],
                        "new_attr": [4, 5, 6],
                    },
                }
            }
        )

    @pytest.fixture
    def entity_group(self, entity_type):
        class MyEntity(EntityGroup, name=entity_type):
            attr = get_attribute(name="attr", flags=PUB)
            other_attr = get_attribute(name="other_attr", flags=PUB)
            non_changed_attr = get_attribute(name="non_changed", flags=PUB)

        entity_group = MyEntity()
        return entity_group

    @pytest.fixture
    def state(self, initial_data, dataset_name, entity_group):
        state = TrackedState()
        state.register_entity_group(dataset_name, entity_group)
        state.receive_update(initial_data, is_initial=True)
        return state

    @pytest.fixture
    def get_attribute_from_state(self, state, entity_group, dataset_name):
        def _get_attribute(identifier):
            return state.get_attribute(dataset_name, entity_group.__entity_name__, identifier)

        return _get_attribute

    def test_initialization(self, get_attribute_from_state):
        assert get_attribute_from_state("attr").is_initialized()

    def test_initializes_with_empty_attribute_when_not_supplied(self, get_attribute_from_state):
        assert np.all(get_attribute_from_state("non_changed").is_undefined())

    def test_later_added_attribute_is_initialized(
        self, state, get_attribute_from_state, update_with_new_attr, dataset_name, entity_group
    ):
        attr = get_attribute("new_attr")
        state.register_attribute(dataset_name, entity_group.__entity_name__, attr.spec, attr.flags)
        state.receive_update(update_with_new_attr)
        assert np.all(get_attribute_from_state("new_attr").is_initialized())

    def test_generate_update(self, initial_data, dataset_name, entity_group, state):
        entity_group.attr[0] = 42
        entity_group.other_attr[1] = 43
        update = state.generate_update()[dataset_name][entity_group.__entity_name__]
        undefined = entity_group.attr.data_type.undefined
        assert dataset_dicts_equal(
            update,
            {
                "id": {"data": [1, 2]},
                "attr": {"data": [42, undefined]},
                "other_attr": {"data": [undefined, 43]},
            },
        )


@pytest.fixture
def state_proxy(state, dataset_name, entity):
    return StateProxy(state, dataset_name, entity.__entity_name__)


def test_state_proxy_can_get_attribute(state_proxy, update):
    state_proxy.state.receive_update(update)
    attr = state_proxy.get_attribute(MyEntity.attr.name)
    assert attr[0] == 47


def test_state_proxy_can_get_index(state_proxy, update):
    state_proxy.state.receive_update(update)
    index = state_proxy.get_index()
    expected_index = np.array([0])
    assert np.array_equal(index[[9]], expected_index)


@pytest.mark.parametrize(
    ["flag", "attrs"],
    [
        (SUBSCRIBE, ["sub_attr", "init_attr", "opt_attr", "either_attr"]),
        (INITIALIZE, ["init_attr"]),
        (REQUIRED, ["sub_attr", "init_attr", "either_attr"]),
        (PUBLISH, ["pub_attr", "either_attr"]),
    ],
)
def test_can_filter_attributes_by_flag(dataset_name, flag, attrs):
    class AllFlags(EntityGroup, name="all_flags_entities"):
        pub_attr = get_attribute(name="pub_attr", flags=PUB)
        sub_attr = get_attribute(name="sub_attr", flags=SUB)
        init_attr = get_attribute(name="init_attr", flags=INIT)
        opt_attr = get_attribute(name="opt_attr", flags=OPT)
        either = get_attribute(name="either_attr", flags=PUB | SUB)

    state = TrackedState()
    state.register_dataset(dataset_name, [AllFlags])
    attributes = state.attributes[dataset_name][AllFlags.__entity_name__]

    assert set(filter_attrs(attributes, flag).keys()) == set(attrs)


def test_set_special_value_on_init_data(state, entity, dataset_name):
    init_data = {"general": {"special": {"my_entities.attr": -100}}, dataset_name: {}}
    state.receive_update(init_data)
    assert entity.attr.options.special == -100


def test_set_enum_on_init_data(state, entity, dataset_name):
    entity.attr.options.enum_name = "bla"
    init_data = {"general": {"enum": {"bla": ["a", "b"]}}, dataset_name: {}}
    state.receive_update(init_data)
    assert entity.attr.options.enum_values == ["a", "b"]


def test_logs_on_double_general_section_assignment_conflict(state, entity, dataset_name):
    entity.attr.options.enum_name = "bla"

    state.logger = Mock()
    state.receive_update(
        {
            "general": {"special": {"my_entities.attr": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )
    state.receive_update(
        {
            "general": {"special": {"my_entities.attr": -99}, "enum": {"bla": ["c"]}},
            dataset_name: {},
        }
    )

    assert state.logger.log.call_args_list == [
        call(
            WARNING,
            f"Special value already set for {dataset_name}/{entity.__entity_name__}/attr",
        ),
        call(
            WARNING,
            f"Enum already set for {dataset_name}/{entity.__entity_name__}/attr",
        ),
    ]


def test_does_not_log_when_double_general_section_assignment_equal_values(
    state, entity, dataset_name
):
    entity.attr.options.enum_name = "bla"

    state.logger = Mock()
    state.receive_update(
        {
            "general": {"special": {"my_entities.attr": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )
    state.receive_update(
        {
            "general": {"special": {"my_entities.attr": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )

    assert state.logger.log.call_count == 0


def test_exposes_general_section_once_received(state, dataset_name):
    state.receive_update(
        {
            "general": {"my": "data"},
            dataset_name: {},
        }
    )
    assert state.general[dataset_name] == {"my": "data"}


def test_strips_special_and_enum_from_general_section(state, dataset_name):
    state.receive_update(
        {
            "general": {
                "special": {"my_entities.attr": -100},
                "enum": {"bla": ["a", "b"]},
                "my": "data",
            },
            dataset_name: {},
        }
    )
    assert state.general[dataset_name] == {"my": "data"}


@pytest.mark.parametrize(
    "e1_dataset, e1_entity, e2_dataset, e2_entity, length",
    [
        ("some_dataset", MyEntity, "some_dataset", MyEntity, 1),
        ("some_dataset", MyEntity, "other_dataset", MyEntity, 2),
        ("some_dataset", MyEntity, "some_dataset", Pub, 2),
        ("some_dataset", Pub, "some_dataset", Pub, 1),
        ("some_dataset", MyEntity, "other_dataset", Pub, 2),
        ("some_dataset", MyEntity(), "some_dataset", MyEntity(), 1),
        ("some_dataset", MyEntity("some_entities"), "some_dataset", MyEntity("other_entities"), 2),
    ],
)
def test_can_hash_entity_groups_with_state(
    state, e1_dataset, e1_entity, e2_dataset, e2_entity, length
):
    e1 = state.register_entity_group(e1_dataset, e1_entity)
    e2 = state.register_entity_group(e2_dataset, e2_entity)
    assert len({e1, e2}) == length


@pytest.mark.parametrize(
    "e1, e2, length",
    [
        (MyEntity, MyEntity, 1),
        (MyEntity, Pub, 2),
        (MyEntity(), MyEntity(), 1),
        (MyEntity("some_entities"), MyEntity("other_entities"), 2),
        (MyEntity, MyEntity(), 2),
    ],
)
def test_can_hash_detached_entity_groups(e1, e2, length):
    assert len({e1, e2}) == length


def test_resets_changes_with_recurring_attributes():
    state = TrackedState()
    e1 = state.register_entity_group("dataset", MyEntity("e1"))
    e2 = state.register_entity_group("dataset", MyEntity("e2"))
    e1.attr.initialize(1)
    e2.attr.initialize(1)
    e1.attr[0] = 1
    e2.attr[0] = 1
    assert np.array_equal(e1.attr.changed, [True])
    assert np.array_equal(e2.attr.changed, [True])
    state.reset_tracked_changes(PUB)
    assert np.array_equal(e1.attr.changed, [False])
    assert np.array_equal(e2.attr.changed, [False])


def test_can_grow_entity_group_with_new_entities():
    state = TrackedState()
    state.register_attribute(
        "dataset", "some_entities", AttributeSpec("some_attr", DataType(int, (), False))
    )
    state.receive_update(
        {
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([2])},
                    "some_attr": {"data": np.array([10])},
                }
            }
        }
    )
    state.receive_update(
        {
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([1])},
                    "some_attr": {"data": np.array([20])},
                }
            }
        }
    )
    assert np.array_equal(
        state.get_attribute("dataset", "some_entities", "some_attr").array, [10, 20]
    )
    assert np.array_equal(state.index["dataset"]["some_entities"].ids, [2, 1])


@pytest.mark.parametrize(
    "track_unknown, expected",
    [
        (None, 0),
        (True, OPT),
        (False, 0),
        (SUB, SUB),
    ],
)
def test_interpret_track_unknown(track_unknown, expected):
    kwargs = {} if track_unknown is None else {"track_unknown": track_unknown}
    state = TrackedState(**kwargs)
    assert state.track_unknown == expected


def test_can_add_new_entity_groups_and_attributes_in_update():
    state = TrackedState(track_unknown=OPT)
    state.register_attribute(
        "dataset", "some_entities", AttributeSpec("some_attr", DataType(int, (), False))
    )
    state.receive_update(
        {
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([2])},
                    "some_attr": {"data": np.array([10])},
                }
            }
        }
    )
    state.receive_update(
        {
            "dataset": {
                "other_entities": {
                    "id": {"data": np.array([1])},
                    "other_attr": {"data": np.array([20])},
                }
            }
        }
    )
    assert np.array_equal(
        state.get_attribute("dataset", "other_entities", "other_attr").array, [20]
    )
    assert np.array_equal(state.index["dataset"]["other_entities"].ids, [1])


def test_adds_enum_name_values_and_special_to_newly_tracked_attributes():
    schema = AttributeSchema(
        [
            AttributeSpec("some_attr", DataType(int, (), False), enum_name="my_enum"),
        ]
    )
    state = TrackedState(track_unknown=OPT, schema=schema)
    state.receive_update(
        {
            "general": {
                "enum": {"my_enum": ["a", "b"]},
                "special": {"some_entities.some_attr": 1},
            },
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([2])},
                    "some_attr": {"data": np.array([1])},
                }
            },
        }
    )
    _, _, name, some_attr = next(state.iter_attributes())
    assert name == "some_attr"
    assert some_attr.options.enum_name == "my_enum"
    assert some_attr.options.enum_values == ["a", "b"]
    assert some_attr.options.special == 1


def test_can_grow_entity_group():
    state = TrackedState(track_unknown=OPT)
    state.receive_update(
        {
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([2])},
                    "some_attr": {"data": np.array([10])},
                }
            }
        }
    )
    state.receive_update(
        {
            "dataset": {
                "some_entities": {
                    "id": {"data": np.array([1])},
                    "other_attr": {"data": np.array([20])},
                }
            }
        }
    )
    np.testing.assert_array_equal(state.index["dataset"]["some_entities"].ids, [2, 1])
    np.testing.assert_array_equal(
        state.get_attribute("dataset", "some_entities", "some_attr").array,
        [10, UNDEFINED[int]],
    )
    np.testing.assert_array_equal(
        state.get_attribute("dataset", "some_entities", "other_attr").array,
        [UNDEFINED[int], 20],
    )


def test_can_inherit_attributes():
    class Derived(MyEntity):
        also_attr = AttributeField(
            spec=AttributeSpec("also_attr", data_type=DataType(int, (), False)), flags=PUB
        )

    assert {attr.name for attr in Derived.all_attributes().values()} == {
        "attr",
        "also_attr",
    }


def test_can_override_attributes():
    class Derived(MyEntity):
        attr = AttributeField(
            spec=AttributeSpec("also_attr", data_type=DataType(int, (), False)), flags=PUB
        )

    assert [attr.name for attr in Derived.all_attributes().values()] == ["also_attr"]


def test_cascading_inheritance():
    class Derived(MyEntity):
        attr = AttributeField(
            spec=AttributeSpec("also_attr", data_type=DataType(int, (), False)), flags=PUB
        )

    class DoubleDerived(Derived):
        other_attr = AttributeField(
            spec=AttributeSpec("other_attr", data_type=DataType(int, (), False)), flags=PUB
        )

    assert {attr.name for attr in DoubleDerived.all_attributes().values()} == {
        "also_attr",
        "other_attr",
    }


def test_can_duplicate_attr():
    class Derived(MyEntity):
        attr_2 = AttributeField(
            spec=AttributeSpec("attr", data_type=DataType(int, (), False)), flags=PUB
        )

    assert [attr.name for attr in Derived.all_attributes().values()] == [
        "attr",
        "attr",
    ]


@pytest.mark.parametrize(
    "general_section, key, expected",
    [
        ({"special": {"my_entities.attribute": -1}}, "attribute", -1),
        ({"no_data": {"my_entities.attribute": -1}}, "attribute", -1),
        ({"special": {"my_entities.my.attribute": -1}}, "my.attribute", -1),
    ],
)
def test_parse_special_value(general_section: dict, key, expected: int, state: TrackedState):
    assert parse_special_values(general_section)["my_entities"][key] == expected
