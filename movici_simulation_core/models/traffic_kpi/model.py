import typing as t

import pandas as pd

from model_engine import TimeStamp, DataFetcher
from model_engine.model_driver.data_handlers import DType
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.property import UniformProperty
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.models.common import model_util
from movici_simulation_core.models.traffic_kpi.coefficients_tape import CoefficientsTape
from .entities import TransportSegments

CARGO = "cargo"
PASSENGER = "passenger"
CO2 = "co2"
NOX = "nox"
ENERGY = "energy"


class Model(TrackedBaseModel):
    """
    Implementation of the traffic KPI model.
    Reads a csv with coefficients.
    Calculates segment CO2, NOx and energy consumption.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    segments: t.Optional[TransportSegments]
    coefficients_tape: t.Optional[CoefficientsTape]

    def __init__(self):
        self.segments = None
        self.coefficients_tape = CoefficientsTape()

    def setup(self, state: TrackedState, config: dict, data_fetcher: DataFetcher, **_):
        transport_type = model_util.get_transport_type(config)
        self.build_state(state, config, transport_type)

        if transport_type == "roads":
            self.add_road_coefficients()
        elif transport_type == "waterways":
            self.add_waterway_coefficients()
        elif transport_type == "tracks":
            self.add_tracks_coefficients()
        else:
            raise RuntimeError(
                "There should be exactly one of [roads, waterways, tracks] in config"
            )

        self.initialize_coefficients(data_fetcher=data_fetcher, name=config["coefficients_csv"][0])

    def add_road_coefficients(
        self,
    ):
        add = self.coefficients_tape.add_coefficient
        add(
            CARGO,
            CO2,
            "cef_f_truck_medium",
            "share_truck_medium",
            "load_capacity_truck_medium",
        )
        add(
            CARGO,
            CO2,
            "cef_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
        )
        add(
            CARGO,
            CO2,
            "cef_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
        )

        add(
            CARGO,
            NOX,
            "nef_f_truck_medium",
            "share_truck_medium",
            "load_capacity_truck_medium",
        )
        add(
            CARGO,
            NOX,
            "nef_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
        )
        add(
            CARGO,
            NOX,
            "nef_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
        )

        add(
            CARGO,
            ENERGY,
            "ecf_f_truck_medium",
            "share_truck_medium",
            "load_capacity_truck_medium",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
        )

        add(
            PASSENGER,
            CO2,
            "cef_p_passenger_car",
            "share_passenger_car",
            "load_capacity_passenger_car",
        )
        add(
            PASSENGER,
            NOX,
            "nef_p_passenger_car",
            "share_passenger_car",
            "load_capacity_passenger_car",
        )
        add(
            PASSENGER,
            ENERGY,
            "ecf_p_passenger_car",
            "share_passenger_car",
            "load_capacity_passenger_car",
        )

    def add_waterway_coefficients(self):
        raise RuntimeError("waterway coefficients not defined in model")

    def add_tracks_coefficients(self):
        raise RuntimeError("tracks coefficients not defined in model")

    def initialize_coefficients(self, data_fetcher: DataFetcher, name: str):
        dtype, data = data_fetcher.get(name)
        if dtype != DType.CSV:
            raise RuntimeError("Given non-csv as CSV input")
        csv: pd.DataFrame = pd.read_csv(data)
        self.coefficients_tape.initialize(csv)

    def build_state(self, state: TrackedState, config: t.Dict, transport_type: str):
        self.segments = state.register_entity_group(
            dataset_name=config[transport_type][0],
            entity=TransportSegments(name=model_util.dataset_to_segments[transport_type]),
        )

    def initialize(self, state: TrackedState):
        if (
            not self.segments.passenger_flow.is_initialized()
            and not self.segments.cargo_flow.is_initialized()
        ):
            raise NotReady

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        self.coefficients_tape.proceed_to(time_stamp)
        if not self.has_anything_changed():
            return self.coefficients_tape.get_next_timestamp()

        self.reset_values()
        self.add_cargo_flow_contribution()
        self.add_passenger_flow_contribution()

        return self.coefficients_tape.get_next_timestamp()

    def has_anything_changed(self):
        return (
            self.coefficients_tape.has_update()
            or self.segments.passenger_flow.has_changes()
            or self.segments.cargo_flow.has_changes()
        )

    def reset_values(self):
        self.segments.energy_consumption[:] = 0
        self.segments.co2_emission[:] = 0
        self.segments.nox_emission[:] = 0

    def add_cargo_flow_contribution(self):
        cargo_flow = self.segments.cargo_flow
        if not cargo_flow.is_initialized():
            return
        self._add_contributions(
            self.segments.co2_emission,
            cargo_flow,
            self.segments.length,
            CARGO,
            CO2,
            multiplier=1.0e-6,
        )
        self._add_contributions(
            self.segments.nox_emission,
            cargo_flow,
            self.segments.length,
            CARGO,
            NOX,
            multiplier=1.0e-9,
        )
        self._add_contributions(
            self.segments.energy_consumption, cargo_flow, self.segments.length, CARGO, ENERGY
        )

    def add_passenger_flow_contribution(self):
        passenger_flow = self.segments.passenger_flow
        if not passenger_flow.is_initialized():
            return
        self._add_contributions(
            self.segments.co2_emission,
            passenger_flow,
            self.segments.length,
            PASSENGER,
            CO2,
            multiplier=1.0e-6,
        )
        self._add_contributions(
            self.segments.nox_emission,
            passenger_flow,
            self.segments.length,
            PASSENGER,
            NOX,
            multiplier=1.0e-9,
        )
        self._add_contributions(
            self.segments.energy_consumption,
            passenger_flow,
            self.segments.length,
            PASSENGER,
            ENERGY,
        )

    def _add_contributions(
        self,
        output: UniformProperty,
        flows: UniformProperty,
        lengths: UniformProperty,
        category: str,
        kpi: str,
        multiplier: float = 1,
    ):
        for factors in self.coefficients_tape[(category, kpi)]:
            coefficient_times_share = factors[0] * factors[1] * factors[2] * multiplier
            output.array += flows.array * lengths.array * coefficient_times_share
