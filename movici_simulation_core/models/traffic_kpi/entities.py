from movici_simulation_core.core.attributes import LineProperties_Length
from movici_simulation_core.core.schema import PropertySpec, DataType
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, PUB, OPT
from movici_simulation_core.models.common.attributes import (
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
)

Transport_EnergyConsumption_Hours = PropertySpec(
    "transport.energy_consumption.hours", DataType(float)
)
Transport_Co2Emission_Hours = PropertySpec("transport.co2_emission.hours", DataType(float))
Transport_NoxEmission_Hours = PropertySpec("transport.nox_emission.hours", DataType(float))


class TransportSegments(EntityGroup):
    length = field(LineProperties_Length, flags=INIT)

    passenger_flow = field(Transport_PassengerVehicleFlow, flags=OPT)
    cargo_flow = field(Transport_CargoVehicleFlow, flags=OPT)

    energy_consumption = field(Transport_EnergyConsumption_Hours, flags=PUB)
    co2_emission = field(Transport_Co2Emission_Hours, flags=PUB)
    nox_emission = field(Transport_NoxEmission_Hours, flags=PUB)
