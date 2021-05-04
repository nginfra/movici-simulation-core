from model_engine.dataset_manager.property_definition import (
    Transport_PassengerDemand,
    Transport_CargoDemand,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.property import (
    field,
    PUB,
    INIT,
)
from movici_simulation_core.models.common.entities import PointEntity


class DemandNodeEntity(PointEntity):
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=INIT | PUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=INIT | PUB)
