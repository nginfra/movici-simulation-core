from movici_simulation_core.core.attributes import (
    ConnectionProperties_FromId,
    ConnectionProperties_ToId,
    ConnectionProperties_FromReference,
    ConnectionProperties_ToReference,
    ConnectionProperties_FromDataset,
    ConnectionProperties_ToDataset,
    PointProperties_PositionX,
    PointProperties_PositionY,
    DisplayName,
)

from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import field, PUB

Overlap_Active = AttributeSpec("overlap.active", data_type=DataType(bool))


class OverlapEntity(EntityGroup, name="overlap_entities"):
    display_name = field(DisplayName, flags=PUB)
    overlap_active = field(Overlap_Active, flags=PUB)
    connection_from_id = field(ConnectionProperties_FromId, flags=PUB)
    connection_to_id = field(ConnectionProperties_ToId, flags=PUB)
    connection_from_reference = field(ConnectionProperties_FromReference, flags=PUB)
    connection_to_reference = field(ConnectionProperties_ToReference, flags=PUB)
    connection_from_dataset = field(ConnectionProperties_FromDataset, flags=PUB)
    connection_to_dataset = field(ConnectionProperties_ToDataset, flags=PUB)
    x = field(PointProperties_PositionX, flags=PUB)
    y = field(PointProperties_PositionY, flags=PUB)
