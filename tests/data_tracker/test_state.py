from logging import WARN
from unittest.mock import Mock, call

import numpy as np
import pytest

from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import (
    PropertyField,
    DataType,
    PUB,
    SUB,
    INIT,
    OPT,
    PropertySpec,
    UNDEFINED,
)
from movici_simulation_core.data_tracker.state import (
    TrackedState,
    ensure_path,
    StateProxy,
    EntityUpdateHandler,
    filter_props,
)
from movici_simulation_core.testing.helpers import (
    dataset_data_to_numpy,
    get_property,
    dataset_dicts_equal,
)


class MyEntity(EntityGroup, name="my_entities"):
    prop = PropertyField(spec=PropertySpec("prop", data_type=DataType(int, (), False)), flags=PUB)


class Pub(EntityGroup, name="pub_entities"):
    pub_prop = get_property(name="pub_prop", flags=PUB)
    component_prop = get_property(name="comp_prop", component="component", flags=PUB)


class Sub(EntityGroup, name="sub_entities"):
    sub_prop = get_property(name="sub_prop", flags=SUB)
    init_prop = get_property(name="init_prop", flags=INIT)
    opt_prop = get_property(name="opt_prop", flags=OPT)


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
    assert state.properties.keys() == {dataset_name}
    assert len(state.properties[dataset_name]) == 1
    assert state.properties[dataset_name].keys() == {"my_entities"}


def test_can_add_dataset_with_multiple_entities(state: TrackedState):
    class OtherEntity(EntityGroup, name="other_entities"):
        sub_prop = get_property(name="sub_prop", flags=SUB)

    state.register_dataset("large_dataset", [MyEntity, OtherEntity])
    assert {k for k in state.properties["large_dataset"].keys()} == {
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
    assert entity_group.__entity_name__ in state.properties[dataset_name]


def test_can_create_property(state, dataset_name):
    prop_name = "new_prop"
    spec = PropertySpec(prop_name, data_type=DataType(int, (), False))
    state.register_property(
        dataset_name,
        MyEntity.__entity_name__,
        spec=spec,
        flags=OPT,
    )
    assert spec.key in state.properties[dataset_name][MyEntity.__entity_name__]


def test_can_get_property(state, dataset_name):
    prop_name = "new_prop"
    spec = PropertySpec(prop_name, data_type=DataType(int, (), False))
    state.register_property(
        dataset_name,
        MyEntity.__entity_name__,
        spec=spec,
        flags=OPT,
    )
    assert state.get_property(dataset_name, MyEntity.__entity_name__, spec.key).flags == OPT


@pytest.mark.parametrize(
    "dataset, entity_type",
    [
        ("invalid_dataset", MyEntity.__entity_name__),
        ("dataset", "invalid_entity_group"),
    ],
)
def test_returns_none_when_not_found(state, dataset, entity_type):
    assert state._get_entity_group(dataset, entity_type) is None


def test_is_ready_for(state):
    class FakeEntity(EntityGroup):
        sub = get_property(name="sub_prop", flags=SUB)
        pub = get_property(name="pub_prop", flags=PUB)

    entity = FakeEntity(name="a")
    state.register_entity_group("some_dataset", entity)
    entity.sub.is_initialized = Mock()
    entity.pub.is_initialized = Mock()

    state.is_ready_for(SUB)
    assert entity.sub.is_initialized.call_count == 1
    assert entity.pub.is_initialized.call_count == 0


@pytest.mark.parametrize(
    ["prop_flag", "initial_data", "ready_flags", "expected"],
    [
        (INIT, None, INIT, False),
        (INIT, None, SUB, False),  # can only be ready for SUB if also ready for INIT
        (SUB, None, INIT, True),
        (INIT, dataset_data_to_numpy({"id": [1], "prop": [1]}), INIT, True),
        (INIT, dataset_data_to_numpy({"id": [1, 2], "prop": [1, UNDEFINED[int]]}), INIT, False),
        (SUB, dataset_data_to_numpy({"id": [1], "prop": [1]}), SUB, True),
        (INIT, dataset_data_to_numpy({"id": [1]}), INIT, False),
    ],
)
def test_is_ready_for2(
    dataset_name, state, prop_flag: int, initial_data: dict, ready_flags: int, expected: bool
):
    prop = state.register_property(
        dataset_name,
        MyEntity.__entity_name__,
        spec=PropertySpec("prop", data_type=DataType(int, (), False)),
        flags=prop_flag,
    )
    if initial_data:
        EntityUpdateHandler(
            state._get_entity_group(dataset_name, MyEntity.__entity_name__), prop.index
        ).receive_update(initial_data)
    assert state.is_ready_for(ready_flags) == expected


def test_pub_sub_filter():
    state = TrackedState()
    state.register_dataset("pub_dataset", [Pub])
    state.register_dataset("sub_dataset", [Sub])
    assert state.get_pub_sub_filter() == {
        "pub": {
            "pub_dataset": {
                "pub_entities": {
                    "pub_prop": "*",
                    "component": {
                        "comp_prop": "*",
                    },
                }
            }
        },
        "sub": {
            "sub_dataset": {
                "sub_entities": {
                    "id": "*",
                    "sub_prop": "*",
                    "init_prop": "*",
                    "opt_prop": "*",
                }
            }
        },
    }


@pytest.fixture
def tracked_entity(state, dataset_name):
    class SomeEntity(EntityGroup, name="some_entities"):
        pub_prop = get_property(name="pub_prop", flags=PUB)
        sub_prop = get_property(name="sub_prop", flags=SUB)
        init_prop = get_property(name="init_prop", flags=INIT)
        opt_prop = get_property(name="opt_prop", flags=OPT)

    entity = SomeEntity()
    state.register_entity_group(dataset_name, entity)
    state.receive_update(
        {dataset_name: {entity.__entity_name__: dataset_data_to_numpy({"id": [1, 2, 3]})}}
    )
    for field in entity.properties.values():
        prop = entity.get_property(field.key)
        prop[0] = 1
        assert np.any(prop.changed)

    return entity


@pytest.mark.parametrize(
    "flag, reset_fields, not_reset_fields",
    [
        (PUB, ("pub_prop",), ("sub_prop", "init_prop", "opt_prop")),
        (
            SUB,
            ("sub_prop", "init_prop", "opt_prop"),
            ("pub_prop",),
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
                MyEntity.prop.spec.name: {"data": np.array([47])},
            }
        }
    }


@pytest.fixture
def other_update(dataset_name, entity):
    return {
        dataset_name: {
            MyEntity.__entity_name__: {
                "id": {"data": np.array([9])},
                MyEntity.prop.spec.name: {"data": np.array([42])},
            }
        }
    }


def test_receive_update_sets_data(state, entity, update):
    state.receive_update(update)
    assert entity.prop[0] == 47


def test_first_update_creates_index(state, entity, update):
    state.receive_update(update)
    assert entity.get_indices([9]) == 0


def test_first_doesnt_mark_as_changed(state, entity, update):
    state.receive_update(update)
    assert not entity.prop.changed
    assert not state.generate_update()


def test_tracks_changes_on_update(state, entity, update, other_update):
    state.receive_update(update)
    state.receive_update(other_update)
    assert np.any(entity.prop.changed)
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
                        "prop": [4, 5, 6],
                    },
                }
            }
        )

    @pytest.fixture
    def update_with_new_prop(self, dataset_name, entity_type):
        return dataset_data_to_numpy(
            {
                dataset_name: {
                    entity_type: {
                        "id": [1, 2, 3],
                        "new_prop": [4, 5, 6],
                    },
                }
            }
        )

    @pytest.fixture
    def entity_group(self, entity_type):
        class MyEntity(EntityGroup, name=entity_type):
            prop = get_property(name="prop", flags=PUB)
            component_prop = get_property(name="component_prop", component="component", flags=PUB)
            non_changed_prop = get_property(name="non_changed", flags=PUB)

        entity_group = MyEntity()
        return entity_group

    @pytest.fixture
    def state(self, initial_data, dataset_name, entity_group):
        state = TrackedState()
        state.register_entity_group(dataset_name, entity_group)
        state.receive_update(initial_data)
        return state

    @pytest.fixture
    def get_property_from_state(self, state, entity_group, dataset_name):
        def _get_property(identifier):
            return state.get_property(dataset_name, entity_group.__entity_name__, identifier)

        return _get_property

    def test_initialization(self, get_property_from_state):
        assert get_property_from_state((None, "prop")).is_initialized()

    def test_initializes_with_empty_property_when_not_supplied(self, get_property_from_state):
        assert np.all(get_property_from_state((None, "non_changed")).is_undefined())

    def test_later_added_property_is_initialized(
        self, state, get_property_from_state, update_with_new_prop, dataset_name, entity_group
    ):
        prop = get_property("new_prop")
        state.register_property(dataset_name, entity_group.__entity_name__, prop.spec, prop.flags)
        state.receive_update(update_with_new_prop)
        assert np.all(get_property_from_state((None, "new_prop")).is_initialized())

    def test_generate_update(self, initial_data, dataset_name, entity_group, state):
        entity_group.prop[0] = 42
        entity_group.component_prop[1] = 43
        update = state.generate_update()[dataset_name][entity_group.__entity_name__]
        undefined = entity_group.prop.data_type.undefined
        assert dataset_dicts_equal(
            update,
            {
                "id": {"data": [1, 2]},
                "prop": {"data": [42, undefined]},
                "component": {
                    "component_prop": {"data": [undefined, 43]},
                },
            },
        )


@pytest.fixture
def state_proxy(state, dataset_name, entity):
    return StateProxy(state, dataset_name, entity.__entity_name__)


def test_state_proxy_can_get_property(state_proxy, update):
    state_proxy.state.receive_update(update)
    prop = state_proxy.get_property(MyEntity.prop.key)
    assert prop[0] == 47


def test_state_proxy_can_get_index(state_proxy, update):
    state_proxy.state.receive_update(update)
    index = state_proxy.get_index()
    expected_index = np.array([0])
    assert np.array_equal(index[[9]], expected_index)


@pytest.mark.parametrize(
    ["flag", "props"],
    [
        (SUB, ["sub_prop", "either_prop"]),
        (INIT, ["init_prop", "either_prop"]),
        (OPT, ["opt_prop"]),
        (PUB, ["pub_prop"]),
    ],
)
def test_can_filter_properties_by_flag(dataset_name, flag, props):
    class AllFlags(EntityGroup, name="all_flags_entities"):
        pub_prop = get_property(name="pub_prop", flags=PUB)
        sub_prop = get_property(name="sub_prop", flags=SUB)
        init_prop = get_property(name="init_prop", flags=INIT)
        opt_prop = get_property(name="opt_prop", flags=OPT)
        either = get_property(name="either_prop", flags=INIT | SUB)

    state = TrackedState()
    state.register_dataset(dataset_name, [AllFlags])
    properties = state.properties[dataset_name][AllFlags.__entity_name__]

    assert set(filter_props(properties, flag).keys()) == set((None, prop) for prop in props)


def test_set_special_value_on_init_data(state, entity, dataset_name):
    init_data = {"general": {"special": {"my_entities..prop": -100}}, dataset_name: {}}
    state.receive_update(init_data)
    assert entity.prop.options.special == -100


def test_set_enum_on_init_data(state, entity, dataset_name):
    entity.prop.options.enum_name = "bla"
    init_data = {"general": {"enum": {"bla": ["a", "b"]}}, dataset_name: {}}
    state.receive_update(init_data)
    assert entity.prop.options.enum == ["a", "b"]


def test_logs_on_double_general_section_assignment_conflict(state, entity, dataset_name):
    entity.prop.options.enum_name = "bla"

    state.logger = Mock()
    state.receive_update(
        {
            "general": {"special": {"my_entities..prop": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )
    state.receive_update(
        {
            "general": {"special": {"my_entities..prop": -99}, "enum": {"bla": ["c"]}},
            dataset_name: {},
        }
    )

    assert state.logger.log.call_args_list == [
        call(
            WARN,
            f"Special value already set for {dataset_name}/{entity.__entity_name__}/prop",
        ),
        call(
            WARN,
            f"Enum already set for {dataset_name}/{entity.__entity_name__}/prop",
        ),
    ]


def test_does_not_log_when_double_general_section_assignment_equal_values(
    state, entity, dataset_name
):
    entity.prop.options.enum_name = "bla"

    state.logger = Mock()
    state.receive_update(
        {
            "general": {"special": {"my_entities..prop": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )
    state.receive_update(
        {
            "general": {"special": {"my_entities..prop": -100}, "enum": {"bla": ["a", "b"]}},
            dataset_name: {},
        }
    )

    assert state.logger.log.call_count == 0


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


def test_resets_changes_with_recurring_properties():
    state = TrackedState()
    e1 = state.register_entity_group("dataset", MyEntity("e1"))
    e2 = state.register_entity_group("dataset", MyEntity("e2"))
    e1.prop.initialize(1)
    e2.prop.initialize(1)
    e1.prop[0] = 1
    e2.prop[0] = 1
    assert np.array_equal(e1.prop.changed, [True])
    assert np.array_equal(e2.prop.changed, [True])
    state.reset_tracked_changes(PUB)
    assert np.array_equal(e1.prop.changed, [False])
    assert np.array_equal(e2.prop.changed, [False])


def test_can_inherit_properties():
    class Derived(MyEntity):
        also_prop = PropertyField(
            spec=PropertySpec("also_prop", data_type=DataType(int, (), False)), flags=PUB
        )

    assert {prop.key for prop in Derived.all_properties().values()} == {
        (None, "prop"),
        (None, "also_prop"),
    }


def test_can_override_properties():
    class Derived(MyEntity):
        prop = PropertyField(
            spec=PropertySpec("also_prop", data_type=DataType(int, (), False)), flags=PUB
        )

    assert [prop.key for prop in Derived.all_properties().values()] == [(None, "also_prop")]


def test_cascading_inheritance():
    class Derived(MyEntity):
        prop = PropertyField(
            spec=PropertySpec("also_prop", data_type=DataType(int, (), False)), flags=PUB
        )

    class DoubleDerived(Derived):
        other_prop = PropertyField(
            spec=PropertySpec("other_prop", data_type=DataType(int, (), False)), flags=PUB
        )

    assert {prop.key for prop in DoubleDerived.all_properties().values()} == {
        (None, "also_prop"),
        (None, "other_prop"),
    }


def test_can_duplicate_prop():
    class Derived(MyEntity):
        prop_2 = PropertyField(
            spec=PropertySpec("prop", data_type=DataType(int, (), False)), flags=PUB
        )

    assert [prop.key for prop in Derived.all_properties().values()] == [
        (None, "prop"),
        (None, "prop"),
    ]
