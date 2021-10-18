from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB, OPT
from movici_simulation_core.models.unit_conversions.attributes import (
    Transport_TotalOutwardCargoDemandVehicles,
    Transport_TotalInwardCargoDemandVehicles,
    Transport_TotalOutwardPassengerDemandVehicles,
    Transport_TotalInwardPassengerDemandVehicles,
    Transport_TotalOutwardCargoDemand,
    Transport_TotalInwardCargoDemand,
    Transport_TotalOutwardPassengerDemand,
    Transport_TotalInwardPassengerDemand,
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
    Transport_PassengerFlow,
    Transport_CargoFlow,
)


class ODEntityGroup(EntityGroup):
    outward_cargo_vehicle = field(Transport_TotalOutwardCargoDemandVehicles, flags=OPT)
    inward_cargo_vehicle = field(Transport_TotalInwardCargoDemandVehicles, flags=OPT)
    outward_passenger_vehicle = field(Transport_TotalOutwardPassengerDemandVehicles, flags=OPT)
    inward_passenger_vehicle = field(Transport_TotalInwardPassengerDemandVehicles, flags=OPT)

    outward_cargo = field(Transport_TotalOutwardCargoDemand, flags=PUB)
    inward_cargo = field(Transport_TotalInwardCargoDemand, flags=PUB)
    outward_passenger = field(Transport_TotalOutwardPassengerDemand, flags=PUB)
    inward_passenger = field(Transport_TotalInwardPassengerDemand, flags=PUB)


class FlowEntityGroup(EntityGroup):
    passenger_vehicle_flow = field(Transport_PassengerVehicleFlow, flags=OPT)
    cargo_vehicle_flow = field(Transport_CargoVehicleFlow, flags=OPT)

    passenger_flow = field(Transport_PassengerFlow, flags=PUB)
    cargo_flow = field(Transport_CargoFlow, flags=PUB)
