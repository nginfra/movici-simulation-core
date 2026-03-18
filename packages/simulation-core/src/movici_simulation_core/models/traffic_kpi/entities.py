from movici_simulation_core.attributes import Shape_Length
from movici_simulation_core.core.attribute import INIT, OPT, PUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.models.common.attributes import (
    Transport_CargoVehicleFlow,
    Transport_PassengerVehicleFlow,
)

Transport_EnergyConsumption_Hours = AttributeSpec(
    "transport.energy_consumption.hours", DataType(float)
)
Transport_Co2Emission_Hours = AttributeSpec("transport.co2_emission.hours", DataType(float))
Transport_NoxEmission_Hours = AttributeSpec("transport.nox_emission.hours", DataType(float))


class TransportSegments(EntityGroup):
    length = field(Shape_Length, flags=INIT)

    passenger_flow = field(Transport_PassengerVehicleFlow, flags=OPT)
    cargo_flow = field(Transport_CargoVehicleFlow, flags=OPT)

    energy_consumption = field(Transport_EnergyConsumption_Hours, flags=PUB)
    co2_emission = field(Transport_Co2Emission_Hours, flags=PUB)
    nox_emission = field(Transport_NoxEmission_Hours, flags=PUB)
