from model_engine.dataset_manager.property_definition import (
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
    Transport_CargoFlow,
    Transport_PassengerFlow,
    Transport_TotalInwardPassengerDemandVehicles,
    Transport_TotalOutwardPassengerDemandVehicles,
    Transport_TotalInwardCargoDemandVehicles,
    Transport_TotalOutwardCargoDemandVehicles,
    Transport_TotalOutwardCargoDemand,
    Transport_TotalInwardCargoDemand,
    Transport_TotalOutwardPassengerDemand,
    Transport_TotalInwardPassengerDemand,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB, OPT


class ODEntityGroup(EntityGroup):
    outward_cargo_vehicle = field(to_spec(Transport_TotalOutwardCargoDemandVehicles), flags=OPT)
    inward_cargo_vehicle = field(to_spec(Transport_TotalInwardCargoDemandVehicles), flags=OPT)
    outward_passenger_vehicle = field(
        to_spec(Transport_TotalOutwardPassengerDemandVehicles), flags=OPT
    )
    inward_passenger_vehicle = field(
        to_spec(Transport_TotalInwardPassengerDemandVehicles), flags=OPT
    )

    outward_cargo = field(to_spec(Transport_TotalOutwardCargoDemand), flags=PUB)
    inward_cargo = field(to_spec(Transport_TotalInwardCargoDemand), flags=PUB)
    outward_passenger = field(to_spec(Transport_TotalOutwardPassengerDemand), flags=PUB)
    inward_passenger = field(to_spec(Transport_TotalInwardPassengerDemand), flags=PUB)


class FlowEntityGroup(EntityGroup):
    passenger_vehicle_flow = field(to_spec(Transport_PassengerVehicleFlow), flags=OPT)
    cargo_vehicle_flow = field(to_spec(Transport_CargoVehicleFlow), flags=OPT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
