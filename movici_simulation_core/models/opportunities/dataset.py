import model_engine.dataset_manager.entity_definition as ed
from model_engine.dataset_manager.property_definition import (
    ConnectionProperties,
    Overlap_Active,
    LineProperties,
    Opportunity,
    MissedOpportunity,
)
from movici_simulation_core.legacy_base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, PUB, UniformProperty, OPT


class OverlapEntity(EntityGroup, name=ed.Overlap):
    overlap_active = field(to_spec(Overlap_Active), flags=OPT)
    connection_from_id = field(to_spec(ConnectionProperties.FromId), flags=OPT)
    connection_to_id = field(to_spec(ConnectionProperties.ToId), flags=OPT)
    connection_from_dataset = field(to_spec(ConnectionProperties.FromDataset), flags=OPT)
    connection_to_dataset = field(to_spec(ConnectionProperties.ToDataset), flags=OPT)


class LineEntity(EntityGroup):
    length = field(to_spec(LineProperties.Length), flags=INIT)
    opportunity = field(to_spec(Opportunity), flags=PUB)
    missed_opportunity = field(to_spec(MissedOpportunity), flags=PUB)
    opportunity_taken_property: UniformProperty
