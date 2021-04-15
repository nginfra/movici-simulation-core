from model_engine.dataset_manager.entity_definition import Road
from model_engine.dataset_manager.property_definition import (
    LineProperties,
    Transport_PassengerFlow,
    Transport_CargoFlow,
    Transport_EnergyConsumption_Hours,
    Transport_Co2Emission_Hours,
    Transport_NoxEmission_Hours,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, PUB, OPT


class TransportSegments(EntityGroup, name=Road):
    length = field(to_spec(LineProperties.Length), flags=INIT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=OPT)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=OPT)

    energy_consumption = field(to_spec(Transport_EnergyConsumption_Hours), flags=PUB)
    co2_emission = field(to_spec(Transport_Co2Emission_Hours), flags=PUB)
    nox_emission = field(to_spec(Transport_NoxEmission_Hours), flags=PUB)
