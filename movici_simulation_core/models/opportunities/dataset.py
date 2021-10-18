from movici_simulation_core.core.attributes import (
    ConnectionProperties_FromId,
    ConnectionProperties_ToId,
    ConnectionProperties_FromDataset,
    ConnectionProperties_ToDataset,
    LineProperties_Length,
)
from movici_simulation_core.core.schema import PropertySpec, DataType
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, PUB, UniformProperty, OPT

Overlap_Active = PropertySpec("overlap.active", data_type=DataType(bool))
Opportunity = PropertySpec("opportunity", data_type=DataType(float))
MissedOpportunity = PropertySpec("missed_opportunity", data_type=DataType(float))


class OverlapEntity(EntityGroup, name="overlap_entities"):
    overlap_active = field(Overlap_Active, flags=OPT)
    connection_from_id = field(ConnectionProperties_FromId, flags=OPT)
    connection_to_id = field(ConnectionProperties_ToId, flags=OPT)
    connection_from_dataset = field(ConnectionProperties_FromDataset, flags=OPT)
    connection_to_dataset = field(ConnectionProperties_ToDataset, flags=OPT)


class LineEntity(EntityGroup):
    length = field(LineProperties_Length, flags=INIT)
    opportunity = field(Opportunity, flags=PUB)
    missed_opportunity = field(MissedOpportunity, flags=PUB)
    opportunity_taken_property: UniformProperty
