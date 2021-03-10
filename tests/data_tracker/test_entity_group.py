from unittest.mock import Mock

import pytest
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import (
    INIT,
    PUB,
)

from movici_simulation_core.testing.helpers import get_property


def get_entity_group(name="some_name", **kwargs) -> EntityGroup:
    return type("SomeEntityGroup", (EntityGroup,), kwargs)(name)


@pytest.fixture
def entity_group():
    return get_entity_group(
        "some_name",
        prop=get_property(name="prop", flags=INIT),
        pub_prop=get_property(name="pub_prop", flags=PUB),
    )


def test_can_set_name_by_type_constructor():
    class MyEntity(EntityGroup, name="someentity"):
        ...

    assert MyEntity().__entity_name__ == "someentity"


def test_can_override_name_by_constructor():
    class MyEntity(EntityGroup, name="someentity"):
        pass

    assert MyEntity(name="othername").__entity_name__ == "othername"


def test_creates_property_fields_attribute():
    class MyEntity(EntityGroup):
        prop = get_property(name="someproperty")
        prop2 = get_property(name="otherproperty")
        not_a_prop = 123

    assert set(MyEntity.properties.values()) == {MyEntity.prop, MyEntity.prop2}


def test_can_ask_state_for_property(entity_group):
    state = Mock()
    entity_group.register(state)

    identifier = (None, "prop")
    entity_group.get_property(identifier)
    state.get_property.assert_called_with(identifier)


def test_can_ask_state_for_index(entity_group):
    sentinel = object()
    state = Mock()
    state.get_index.return_value = sentinel
    entity_group.register(state)
    assert entity_group.index is sentinel


def test_get_full_name():
    class MyEntity(EntityGroup, name="some_entities"):
        prop = get_property(name="someproperty")
        prop2 = get_property(name="otherproperty", component="component")

    assert MyEntity.prop.full_name == "someproperty"
    assert MyEntity.prop2.full_name == "component/otherproperty"
