from movici_simulation_core.attributes import (
    Connection_FromDataset,
    Connection_FromId,
    Connection_FromReference,
    Connection_ToDataset,
    Connection_ToId,
    Connection_ToReference,
    DisplayName,
    Geometry_X,
    Geometry_Y,
)
from movici_simulation_core.core.attribute import PUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.schema import AttributeSpec, DataType

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
