import typing as t

import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB, UniformAttribute
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common import model_util
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.traffic_kpi.coefficients_tape import CoefficientsTape
from movici_simulation_core.validate import ensure_valid_config

from .entities import TransportSegments

CARGO = "cargo"
PASSENGER = "passenger"
CO2 = "co2"
NOX = "nox"
ENERGY = "energy"

DEFAULT_ENERGY_CONSUMPTION_ATTR = "transport.energy_consumption.hours"
DEFAULT_CO2_EMISSION_ATTR = "transport.co2_emission.hours"
DEFAULT_NOX_EMISSION_ATTR = "transport.nox_emission.hours"


class Model(TrackedModel, name="traffic_kpi"):
    """
    Implementation of the traffic KPI model.
    Reads a csv with coefficients.
    Calculates segment CO2, NOx and energy consumption.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    segments: t.Optional[TransportSegments]
    modality: t.Literal["roads", "tracks", "waterways"]
    ec_attr: UniformAttribute
    co2_attr: UniformAttribute
    nox_attr: UniformAttribute

    _cargo_scenario_parameters: t.List[str]
    _passenger_scenario_parameters: t.List[str]
    scenario_parameters_tape: t.Optional[CsvTape] = None
    _new_timesteps_first_update: bool = True

    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)
        self.segments = None
        self.coefficients_tape = CoefficientsTape()

    def setup(
        self, state: TrackedState, init_data_handler: InitDataHandler, schema: AttributeSchema, **_
    ):
        self.modality, dataset = model_util.get_transport_info(self.config)
        self.build_state(state=state, dataset_name=dataset, schema=schema)
        if self.modality == "roads":
            self.add_road_coefficients()
        elif self.modality == "waterways":
            self.add_waterway_coefficients()
        elif self.modality == "tracks":
            self.add_tracks_coefficients()
        else:
            raise RuntimeError(f"Unsupported modality '{self.modality}'")
        self._cargo_scenario_parameters = self.set_scenario_parameters(
            self.config, config_key="cargo_scenario_parameters"
        )
        self._passenger_scenario_parameters = self.set_scenario_parameters(
            self.config, config_key="passenger_scenario_parameters"
        )
        if "scenario_parameters_dataset" in self.config:
            self._initialize_scenario_parameters_tape(
                data_handler=init_data_handler, name=self.config["scenario_parameters_dataset"]
            )
        self.initialize_coefficients(
            data_handler=init_data_handler, name=self.config["coefficients_dataset"]
        )

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
            "road_effective_load_factor",
        )
        add(
            CARGO,
            CO2,
            "cef_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
            "road_effective_load_factor",
        )
        add(
            CARGO,
            CO2,
            "cef_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
            "road_effective_load_factor",
        )

        add(
            CARGO,
            NOX,
            "nef_f_truck_medium",
            "share_truck_medium",
            "load_capacity_truck_medium",
            "road_effective_load_factor",
        )
        add(
            CARGO,
            NOX,
            "nef_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
            "road_effective_load_factor",
        )
        add(
            CARGO,
            NOX,
            "nef_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
            "road_effective_load_factor",
        )

        add(
            CARGO,
            ENERGY,
            "ecf_f_truck_medium",
            "share_truck_medium",
            "load_capacity_truck_medium",
            "road_effective_load_factor",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_tractor_light",
            "share_tractor_light",
            "load_capacity_tractor_light",
            "road_effective_load_factor",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_tractor_heavy",
            "share_tractor_heavy",
            "load_capacity_tractor_heavy",
            "road_effective_load_factor",
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
        add = self.coefficients_tape.add_coefficient
        add(
            CARGO,
            CO2,
            "cef_f_rhc",
            "share_rhc",
            "load_capacity_rhc",
            "waterway_effective_load_factor",
        )
        add(
            CARGO,
            CO2,
            "cef_f_lr",
            "share_lr",
            "load_capacity_lr",
            "waterway_effective_load_factor",
        )
        add(
            CARGO,
            NOX,
            "nef_f_rhc",
            "share_rhc",
            "load_capacity_rhc",
            "waterway_effective_load_factor",
        )
        add(
            CARGO,
            NOX,
            "nef_f_lr",
            "share_lr",
            "load_capacity_lr",
            "waterway_effective_load_factor",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_rhc",
            "share_rhc",
            "load_capacity_rhc",
            "waterway_effective_load_factor",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_lr",
            "share_lr",
            "load_capacity_lr",
            "waterway_effective_load_factor",
        )

    def add_tracks_coefficients(self):
        add = self.coefficients_tape.add_coefficient
        add(
            CARGO,
            CO2,
            "cef_f_train_medium_length",
            "share_train_medium_length",
        )
        add(
            CARGO,
            NOX,
            "nef_f_train_medium_length",
            "share_train_medium_length",
        )
        add(
            CARGO,
            ENERGY,
            "ecf_f_train_medium_length",
            "share_train_medium_length",
        )
        add(
            PASSENGER,
            CO2,
            "cef_p_ic",
            "share_ic",
            "passenger_train_capacity",
        )
        add(
            PASSENGER,
            NOX,
            "nef_p_ic",
            "share_ic",
            "passenger_train_capacity",
        )
        add(
            PASSENGER,
            ENERGY,
            "ecf_p_ic",
            "share_ic",
            "passenger_train_capacity",
        )
        add(
            PASSENGER,
            CO2,
            "cef_p_st",
            "share_st",
            "passenger_train_capacity",
        )
        add(
            PASSENGER,
            NOX,
            "nef_p_st",
            "share_st",
            "passenger_train_capacity",
        )
        add(
            PASSENGER,
            ENERGY,
            "ecf_p_st",
            "share_st",
            "passenger_train_capacity",
        )

    def set_scenario_parameters(self, config, config_key: str):
        _scenario_parameters = config.get(config_key, [])

        if len(_scenario_parameters) == 0:
            return
        else:
            return _scenario_parameters

    def _initialize_scenario_parameters_tape(self, data_handler: InitDataHandler, name: str):
        dtype, data = data_handler.ensure_ftype(name, FileType.CSV)
        csv: pd.DataFrame = pd.read_csv(data)
        self.scenario_parameters_tape = CsvTape()
        self.scenario_parameters_tape.initialize(csv)
        self.scenario_parameters_tape.proceed_to(Moment(0))

    def initialize_coefficients(self, data_handler: InitDataHandler, name: str):
        dtype, data = data_handler.ensure_ftype(name, FileType.CSV)
        csv: pd.DataFrame = pd.read_csv(data)
        self.coefficients_tape.initialize(csv)

    def build_state(self, state: TrackedState, dataset_name, schema: AttributeSchema):
        config = self.config
        entity_name = model_util.modality_link_entities[self.modality]
        self.segments = state.register_entity_group(
            dataset_name=dataset_name,
            entity=TransportSegments(name=entity_name),
        )
        # also add our attributes
        self.ec_attr = state.register_attribute(
            dataset_name,
            entity_name,
            schema.get_spec(
                config.get("energy_consumption_attribute", DEFAULT_ENERGY_CONSUMPTION_ATTR),
                default_data_type=DataType(float),
            ),
            flags=PUB,
        )

        self.co2_attr = state.register_attribute(
            dataset_name,
            entity_name,
            schema.get_spec(
                config.get("co2_emission_attribute", DEFAULT_CO2_EMISSION_ATTR),
                default_data_type=DataType(float),
            ),
            flags=PUB,
        )

        self.nox_attr = state.register_attribute(
            dataset_name,
            entity_name,
            schema.get_spec(
                config.get("nox_emission_attribute", DEFAULT_NOX_EMISSION_ATTR),
                default_data_type=DataType(float),
            ),
            flags=PUB,
        )

    def initialize(self, state: TrackedState):
        if (
            not self.segments.passenger_flow.is_initialized()
            and not self.segments.cargo_flow.is_initialized()
        ):
            raise NotReady

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        self._proceed_tapes(moment)
        if not self._coefficient_or_flow_changes():
            return self.next_time()

        self.reset_values()
        self._add_contributions_for(self.segments.cargo_flow, CARGO)
        self._add_contributions_for(self.segments.passenger_flow, PASSENGER)

        return self.next_time()

    def _proceed_tapes(self, moment: Moment):
        self.coefficients_tape.proceed_to(moment)
        if self.scenario_parameters_tape is not None:
            self.scenario_parameters_tape.proceed_to(moment)

    def _coefficient_or_flow_changes(self) -> bool:
        return (
            self.scenario_parameters_tape.has_update()
            or self.coefficients_tape.has_update()
            or self.segments.passenger_flow.has_changes()
            or self.segments.cargo_flow.has_changes()
        )

    def next_time(self) -> t.Optional[Moment]:
        tape_list = [self.coefficients_tape]
        if self.scenario_parameters_tape is not None:
            tape_list.append(self.scenario_parameters_tape)

        valid_time_found = False
        min_time = 1.0e12
        for tape in tape_list:
            next_time = tape.get_next_timestamp()
            if next_time is None:
                continue
            min_time = min(min_time, next_time.timestamp)
            valid_time_found = True

        if not valid_time_found:
            return None
        return Moment(min_time)

    def reset_values(self):
        self.ec_attr[:] = 0
        self.co2_attr[:] = 0
        self.nox_attr[:] = 0

    def _add_contributions_for(self, flow: UniformAttribute, flow_category: str):
        if not flow.is_initialized():
            return
        self._add_contributions(
            self.co2_attr, flow, self.segments.length, flow_category, CO2, multiplier=1.0e-6
        )
        self._add_contributions(
            self.nox_attr, flow, self.segments.length, flow_category, NOX, multiplier=1.0e-6
        )
        self._add_contributions(
            self.ec_attr, flow, self.segments.length, flow_category, ENERGY, multiplier=1.0e-3
        )

    def _add_contributions(
        self,
        output: UniformAttribute,
        flows: UniformAttribute,
        lengths: UniformAttribute,
        category: str,
        kpi: str,
        multiplier: float = 1,
    ):
        scenario_multiplier = self._compute_scenario_multiplier(
            category=category
        )  # some factor from our other tape

        for factors in self.coefficients_tape[(category, kpi)]:
            if self.modality != "tracks" and category == CARGO:
                f0, f1, f2, f3 = factors
                base_coeff = f0 * f1 * f2 * f3
            elif self.modality == "roads" and category == PASSENGER:
                # passenger vehicles do not have effective load factor
                f0, f1, f2 = factors
                base_coeff = f0 * f1 * f2
            elif self.modality == "tracks" and category == CARGO:
                f0, f1 = factors
                # flow is in tonne for cargo train, kpi factors are also based on tkm
                base_coeff = f0 * f1
            else:
                f0, f1, f2 = factors
                # flow is in the number of passengers, passenger trains do not have effective load
                # factor, kpi factors are based on vkm
                base_coeff = f0 * f1 / f2
            coefficient_times_share = base_coeff * multiplier * scenario_multiplier
            output.array += flows.array * lengths.array * coefficient_times_share

    def _compute_scenario_multiplier(self, category: str) -> float:
        scenario_multiplier = 1.0
        if self.scenario_parameters_tape is None:
            return scenario_multiplier
        if category == CARGO and self._cargo_scenario_parameters is not None:
            for i, param in enumerate(self._cargo_scenario_parameters):
                parameter_multiplier = self.scenario_parameters_tape[param]
                scenario_multiplier *= parameter_multiplier
        elif category == PASSENGER and self._passenger_scenario_parameters is not None:
            for i, param in enumerate(self._passenger_scenario_parameters):
                parameter_multiplier = self.scenario_parameters_tape[param]
                scenario_multiplier *= parameter_multiplier
        return scenario_multiplier


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/traffic_kpi.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/traffic_kpi.json"


def convert_v1_v2(config):
    modality, dataset = model_util.get_transport_info(config)

    rv = {
        "modality": modality,
        "dataset": dataset,
        "coefficients_dataset": config["coefficients_csv"][0],
    }

    if "scenario_parameters" in config:
        rv["scenario_parameters_dataset"] = config["scenario_parameters"][0]

    for src, tgt in (
        ("energy_consumption_property", "energy_consumption_attribute"),
        ("co2_emission_property", "co2_emission_attribute"),
        ("nox_emission_property", "nox_emission_attribute"),
    ):
        if src in config:
            rv[tgt] = config[src][1]

    for key in (
        "cargo_scenario_parameters",
        "passenger_scenario_parameters",
    ):
        if key in config:
            rv[key] = config[key]
    return rv
