from movici_simulation_core.core.attribute import OPT, PUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.models.unit_conversions.attributes import (
    Transport_CargoFlow,
    Transport_CargoVehicleFlow,
    Transport_PassengerFlow,
    Transport_PassengerVehicleFlow,
    Transport_TotalInwardCargoDemand,
    Transport_TotalInwardCargoDemandVehicles,
    Transport_TotalInwardPassengerDemand,
    Transport_TotalInwardPassengerDemandVehicles,
    Transport_TotalOutwardCargoDemand,
    Transport_TotalOutwardCargoDemandVehicles,
    Transport_TotalOutwardPassengerDemand,
    Transport_TotalOutwardPassengerDemandVehicles,
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
