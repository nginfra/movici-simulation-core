import typing as t

import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import PropertySpec, attributes_from_dict
from movici_simulation_core.data_tracker.property import UniformProperty
from movici_simulation_core.data_tracker.state import TrackedState
from ...model_connector.init_data import InitDataHandler, FileType
from movici_simulation_core.models.traffic_kpi.coefficients_tape import CsvTape
from movici_simulation_core.utils.moment import Moment
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
        super().__init__(model_config)
        self.flow_entities = []
        self.flow_types = []
        self.od_entities = []
        self.od_types = []
        self.coefficients_tape = CsvTape()

    def setup(self, state: TrackedState, init_data_handler: InitDataHandler, **_):
        config = self.config
        flow_entities = config.get("flow_entities", [])
        flow_types = config.get("flow_types", [])
        for flow_entity, flow_type in zip(flow_entities, flow_types):
            self.flow_entities.append(
                state.register_entity_group(
                    dataset_name=flow_entity[0],
                    entity=FlowEntityGroup(name=flow_entity[1]),
                )
            )
            self.flow_types.append(flow_type)

        od_entities = config.get("od_entities", [])
        od_types = config.get("od_types", [])
        for od_entity, od_type in zip(od_entities, od_types):
            self.od_entities.append(
                state.register_entity_group(
                    dataset_name=od_entity[0],
                    entity=ODEntityGroup(name=od_entity[1]),
                )
            )
            self.od_types.append(od_type)

        self.initialize_coefficients(data_handler=init_data_handler, name=config["parameters"][0])

    def initialize(self, state: TrackedState):
        pass

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
        from_prop: UniformProperty, to_prop: UniformProperty, od_type, tape: CsvTape
    ):
        if from_prop.is_initialized():
            coef = 0.0
            if od_type == "roads":
                coef += tape["load_capacity_truck_medium"] * tape["share_truck_medium"]
                coef += tape["load_capacity_tractor_light"] * tape["share_tractor_light"]
                coef += tape["load_capacity_tractor_heavy"] * tape["share_tractor_heavy"]
            elif od_type == "waterways":
                coef += tape["load_capacity_rhc_vessel"] * tape["share_rhc_vessel"]
                coef += tape["load_capacity_large_vessel"] * tape["share_large_vessel"]
            elif od_type == "tracks":
                coef += tape["load_capacity_train_electric"] * tape["share_train_electric"]
                coef += tape["load_capacity_train_diesel"] * tape["share_large_train_diesel"]
            else:
                raise RuntimeError(f"od_type {od_type} should be one of roads, waterways, tracks")
            to_prop[:] = from_prop.array * coef

    @staticmethod
    def _update_passenger_value(
        from_prop: UniformProperty, to_prop: UniformProperty, tape: CsvTape
    ):
        if from_prop.is_initialized():
            coef = tape["load_capacity_passenger_car"] * tape["share_passenger_car"]
            to_prop[:] = from_prop.array * coef

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[PropertySpec]:
        return attributes_from_dict(vars(attributes))
