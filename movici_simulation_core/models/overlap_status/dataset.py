import model_engine.dataset_manager.entity_definition as ed
from model_engine.dataset_manager.property_definition import (
    DisplayName,
    ConnectionProperties,
    Overlap_Active,
    PointProperties,
)
from movici_simulation_core.legacy_base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB


class OverlapEntity(EntityGroup, name=ed.Overlap):
    display_name = field(to_spec(DisplayName), flags=PUB)
    overlap_active = field(to_spec(Overlap_Active), flags=PUB)
    connection_from_id = field(to_spec(ConnectionProperties.FromId), flags=PUB)
    connection_to_id = field(to_spec(ConnectionProperties.ToId), flags=PUB)
    connection_from_reference = field(to_spec(ConnectionProperties.FromReference), flags=PUB)
    connection_to_reference = field(to_spec(ConnectionProperties.ToReference), flags=PUB)
    connection_from_dataset = field(to_spec(ConnectionProperties.FromDataset), flags=PUB)
    connection_to_dataset = field(to_spec(ConnectionProperties.ToDataset), flags=PUB)
    x = field(to_spec(PointProperties.PositionX), flags=PUB)
    y = field(to_spec(PointProperties.PositionY), flags=PUB)
