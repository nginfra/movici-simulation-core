from unittest.mock import Mock

import pytest
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import (
    INIT,
    PUB,
)

from movici_simulation_core.testing.helpers import get_attribute


def get_entity_group(name="some_name", **kwargs) -> EntityGroup:
    return type("SomeEntityGroup", (EntityGroup,), kwargs)(name)


@pytest.fixture
def entity_group():
    return get_entity_group(
        "some_name",
        attr=get_attribute(name="attr", flags=INIT),
        pub_attr=get_attribute(name="pub_attr", flags=PUB),
    )


def test_can_set_name_by_type_constructor():
    class MyEntity(EntityGroup, name="someentity"):
        ...

    assert MyEntity().__entity_name__ == "someentity"


def test_can_override_name_by_constructor():
    class MyEntity(EntityGroup, name="someentity"):
        pass

    assert MyEntity(name="othername").__entity_name__ == "othername"


def test_creates_attribute_fields_attribute():
    class MyEntity(EntityGroup):
        attr = get_attribute(name="some_attribute")
        attr2 = get_attribute(name="other_attribute")
        not_a_attr = 123

    assert set(MyEntity.attributes.values()) == {MyEntity.attr, MyEntity.attr2}


def test_can_ask_state_for_attribute(entity_group):
    state = Mock()
    entity_group.register(state)

    identifier = (None, "attr")
    entity_group.get_attribute(identifier)
    state.get_attribute.assert_called_with(identifier)


def test_can_ask_state_for_index(entity_group):
    sentinel = object()
    state = Mock()
    state.get_index.return_value = sentinel
    entity_group.register(state)
    assert entity_group.index is sentinel


def test_get_full_name():
    class MyEntity(EntityGroup, name="some_entities"):
        attr = get_attribute(name="some_attribute")
        attr2 = get_attribute(name="other_attribute", component="component")

    assert MyEntity.attr.full_name == "some_attribute"
    assert MyEntity.attr2.full_name == "component/other_attribute"


def test_overwrite_attribute():
    class BaseEntity(EntityGroup):
        attr = get_attribute(name="some_attribute", flags=INIT)

    class Derived(BaseEntity):
        attr = get_attribute(name="some_attribute", flags=0)

    attrs = Derived.all_attributes()
    assert set(attrs) == {"attr"}
    assert attrs["attr"].flags == 0
