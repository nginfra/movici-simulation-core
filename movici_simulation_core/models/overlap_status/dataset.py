from movici_simulation_core.core.attributes import (
    Connection_FromId,
    Connection_ToId,
    Connection_FromReference,
    Connection_ToReference,
    Connection_FromDataset,
    Connection_ToDataset,
    Geometry_X,
    Geometry_Y,
    DisplayName,
)

from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import field, PUB

Overlap_Active = AttributeSpec("overlap.active", data_type=DataType(bool))


class OverlapEntity(EntityGroup, name="overlap_entities"):
    display_name = field(DisplayName, flags=PUB)
    overlap_active = field(Overlap_Active, flags=PUB)
    connection_from_id = field(Connection_FromId, flags=PUB)
    connection_to_id = field(Connection_ToId, flags=PUB)
    connection_from_reference = field(Connection_FromReference, flags=PUB)
    connection_to_reference = field(Connection_ToReference, flags=PUB)
    connection_from_dataset = field(Connection_FromDataset, flags=PUB)
    connection_to_dataset = field(Connection_ToDataset, flags=PUB)
    x = field(Geometry_X, flags=PUB)
    y = field(Geometry_Y, flags=PUB)
