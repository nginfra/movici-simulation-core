from movici_simulation_core.core.attributes import (
    Connection_FromId,
    Connection_ToId,
    Connection_FromDataset,
    Connection_ToDataset,
    Shape_Length,
)
from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import field, INIT, PUB, UniformAttribute, OPT

Overlap_Active = AttributeSpec("overlap.active", data_type=DataType(bool))
Opportunity = AttributeSpec("opportunity", data_type=DataType(float))
MissedOpportunity = AttributeSpec("missed_opportunity", data_type=DataType(float))


class OverlapEntity(EntityGroup, name="overlap_entities"):
    overlap_active = field(Overlap_Active, flags=OPT)
    connection_from_id = field(Connection_FromId, flags=OPT)
    connection_to_id = field(Connection_ToId, flags=OPT)
    connection_from_dataset = field(Connection_FromDataset, flags=OPT)
    connection_to_dataset = field(Connection_ToDataset, flags=OPT)


class LineEntity(EntityGroup):
    length = field(Shape_Length, flags=INIT)
    opportunity = field(Opportunity, flags=PUB)
    missed_opportunity = field(MissedOpportunity, flags=PUB)
    opportunity_taken_attribute: UniformAttribute
