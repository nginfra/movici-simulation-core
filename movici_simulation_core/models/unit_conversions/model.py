import typing as t

import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import UniformAttribute
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSpec, attributes_from_dict
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.traffic_kpi.coefficients_tape import CsvTape
from movici_simulation_core.validate import ensure_valid_config

from ...model_connector.init_data import FileType, InitDataHandler
from . import attributes
from .entities import FlowEntityGroup, ODEntityGroup


class Model(TrackedModel, name="unit_conversions"):
    """
    Implementation of the unit conversions model.
    Reads a csv with coefficients.
    Turns values in _vehicles into tons or passengers.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    flow_entities: t.List[FlowEntityGroup]
    flow_types: t.List[str]
    od_entities: t.List[ODEntityGroup]
    od_types: t.List[str]
    coefficients_tape: t.Optional[CsvTape]

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
        self.flow_entities = []
        self.flow_types = []
        self.od_entities = []
        self.od_types = []
        self.coefficients_tape = CsvTape()

    def setup(self, state: TrackedState, init_data_handler: InitDataHandler, **_):
        config = self.config
        for conversion in config["conversions"]:
            if conversion["class"] == "od":
                self.setup_od_conversion(conversion, state)
            elif conversion["class"] == "flow":
                self.setup_flow_conversion(conversion, state)
            else:
                raise ValueError(f"unknown conversion class '{conversion['class']}'")

        self.initialize_coefficients(
            data_handler=init_data_handler, name=config["parameters_dataset"]
        )

    def setup_od_conversion(self, conversion: dict, state: TrackedState):
        dataset, entity_group = conversion["entity_group"]
        self.od_entities.append(
            state.register_entity_group(
                dataset_name=dataset,
                entity=ODEntityGroup(name=entity_group),
            )
        )
        self.od_types.append(conversion["modality"])

    def setup_flow_conversion(self, conversion: dict, state: TrackedState):
        dataset, entity_group = conversion["entity_group"]
        self.flow_entities.append(
            state.register_entity_group(
                dataset_name=dataset,
                entity=FlowEntityGroup(name=entity_group),
            )
        )
        self.flow_types.append(conversion["modality"])

    def initialize_coefficients(self, data_handler: InitDataHandler, name: str):
        dtype, data = data_handler.ensure_ftype(name, FileType.CSV)
        csv: pd.DataFrame = pd.read_csv(data)
        self.coefficients_tape.initialize(csv)

    def update(self, state: TrackedState, moment: Moment):
        self.coefficients_tape.proceed_to(moment)

        self._update_od_values()

        self._update_flow_values()

        return self.coefficients_tape.get_next_timestamp()

    def _update_od_values(self):
        for entity, od_type in zip(self.od_entities, self.od_types):
            # cargo to tons
            self._update_cargo_value(
                entity.outward_cargo_vehicle, entity.outward_cargo, od_type, self.coefficients_tape
            )
            self._update_cargo_value(
                entity.inward_cargo_vehicle, entity.inward_cargo, od_type, self.coefficients_tape
            )

            # passenger vehicles to passengers
            self._update_passenger_value(
                entity.outward_passenger_vehicle,
                entity.outward_passenger,
                self.coefficients_tape,
            )
            self._update_passenger_value(
                entity.inward_passenger_vehicle,
                entity.inward_passenger,
                self.coefficients_tape,
            )

    def _update_flow_values(self):
        for entity, flow_type in zip(self.flow_entities, self.flow_types):
            # cargo to tons
            self._update_cargo_value(
                entity.cargo_vehicle_flow, entity.cargo_flow, flow_type, self.coefficients_tape
            )
            if flow_type == "roads":
                # passenger vehicles to passengers
                self._update_passenger_value(
                    entity.passenger_vehicle_flow,
                    entity.passenger_flow,
                    self.coefficients_tape,
                )

    @staticmethod
    def _update_cargo_value(
        from_attr: UniformAttribute, to_attr: UniformAttribute, od_type, tape: CsvTape
    ):
        if from_attr.is_initialized():
            coef = 0.0
            if od_type == "roads":
                coef += tape["road_effective_load_factor"] * (
                    tape["load_capacity_truck_medium"] * tape["share_truck_medium"]
                    + tape["load_capacity_tractor_light"] * tape["share_tractor_light"]
                    + tape["load_capacity_tractor_heavy"] * tape["share_tractor_heavy"]
                )

            elif od_type == "waterways":
                coef += tape["waterway_effective_load_factor"] * (
                    tape["load_capacity_rhc"] * tape["share_rhc"]
                    + tape["load_capacity_lr"] * tape["share_lr"]
                )
            else:
                raise RuntimeError(f"od_type {od_type} should be one of roads, waterways")
            to_attr[:] = from_attr.array * coef

    @staticmethod
    def _update_passenger_value(
        from_attr: UniformAttribute, to_attr: UniformAttribute, tape: CsvTape
    ):
        if from_attr.is_initialized():
            coef = tape["load_capacity_passenger_car"] * tape["share_passenger_car"]
            to_attr[:] = from_attr.array * coef

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(attributes))


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/unit_conversions.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/unit_conversions.json"


def convert_v1_v2(config):

    return {
        "parameters_dataset": config["parameters"][0],
        "conversions": [
            *[
                {
                    "class": "od",
                    "modality": config["od_types"][i],
                    "entity_group": config["od_entities"][i],
                }
                for i in range(len(config["od_types"]))
            ],
            *[
                {
                    "class": "flow",
                    "modality": config["flow_types"][i],
                    "entity_group": config["flow_entities"][i],
                }
                for i in range(len(config["flow_types"]))
            ],
        ],
    }
