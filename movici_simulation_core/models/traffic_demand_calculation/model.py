import logging
import typing as t

import numpy as np
import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import (
    INIT,
    PUB,
    PUBLISH,
    SUBSCRIBE,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector.init_data import FileType, InitDataHandler
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.common.entity_groups import GeometryEntity, PointEntity
from movici_simulation_core.models.traffic_demand_calculation.common import (
    DemandEstimation,
    GlobalContributor,
    LocalContributor,
    LocalMapper,
)
from movici_simulation_core.models.traffic_demand_calculation.global_contributors import (
    GlobalElasticityParameter,
    ScalarParameter,
)
from movici_simulation_core.models.traffic_demand_calculation.local_contributors import (
    Investment,
    InvestmentContributor,
    LocalParameterInfo,
    NearestValue,
    RouteCostFactor,
)
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

DEFAULT_DATA_TYPE = DataType(float, (), False)
DEFAULT_CSR_DATA_TYPE = DataType(float, (), True)


class TrafficDemandCalculation(TrackedModel, name="traffic_demand_calculation"):
    """
    Implementation of the demand estimation model.
    Reads a csv with scenario parameters.
    Calculates changes in the od matrices based on change of scenario parameters in time.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    auto_reset = PUBLISH

    demand_estimation: DemandEstimation
    _demand_attribute: CSRAttribute
    _demand_entity: GeometryEntity

    _total_inward_demand_attribute: t.Optional[UniformAttribute] = None
    _total_outward_demand_attribute: t.Optional[UniformAttribute] = None

    _scenario_parameters_tape: t.Optional[CsvTape] = None

    _new_timesteps_first_update: bool = True

    _local_mapping_type_to_calculators_dict: t.Dict[str, t.Type[LocalContributor]] = {
        "nearest": NearestValue,
        "route": RouteCostFactor,
    }

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
        self.update_count = 0
        self.max_iterations = model_config.get("max_iterations", 10_000_000)

    def setup(
        self,
        state: TrackedState,
        settings: Settings,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        logger: logging.Logger,
        **_,
    ):
        self.configure_demand_nodes(state, schema)

        global_contributors = self.get_global_elasticity_contributors(init_data_handler)
        scenario_multipliers = self.get_scenario_multipliers()
        local_contributors = self.get_local_contributors(state=state, schema=schema)
        investments = self.get_investment_contributors()

        self.demand_estimation = DemandEstimation(
            global_contributors + scenario_multipliers, local_contributors + investments
        )
        self.demand_estimation.setup(state=state, settings=settings, schema=schema, logger=logger)

    def configure_demand_nodes(self, state: TrackedState, schema: AttributeSchema):
        config = self.config
        ds_name, demand_entity, attribute = config["demand_path"]
        self._demand_entity = state.register_entity_group(
            dataset_name=ds_name, entity=PointEntity(name=demand_entity)
        )
        self._demand_attribute = state.register_attribute(
            dataset_name=ds_name,
            entity_name=demand_entity,
            spec=schema.get_spec(attribute, DEFAULT_CSR_DATA_TYPE),
            flags=INIT | PUB,
            rtol=config.get("rtol", 1e-5),
            atol=config.get("atol", 1e-8),
        )

        if sum_attr_config_in := config.get("total_inward_demand_attribute"):
            self._total_inward_demand_attribute = state.register_attribute(
                dataset_name=ds_name,
                entity_name=demand_entity,
                spec=schema.get_spec(sum_attr_config_in, DEFAULT_DATA_TYPE),
                flags=PUB,
            )

        if sum_attr_config_out := config.get("total_outward_demand_attribute"):
            self._total_outward_demand_attribute = state.register_attribute(
                dataset_name=ds_name,
                entity_name=demand_entity,
                spec=schema.get_spec(sum_attr_config_out, DEFAULT_DATA_TYPE),
                flags=PUB,
            )

    def get_global_elasticity_contributors(
        self, data_handler: InitDataHandler
    ) -> t.List[GlobalContributor]:
        config = self.config

        if (parameter_dataset := config.get("parameter_dataset")) is None:
            return []
        self._scenario_parameters_tape = tape = self.get_global_parameters_tape(
            data_handler, parameter_dataset
        )
        return [
            GlobalElasticityParameter(param["name"], tape, param["elasticity"])
            for param in config.get("global_parameters", [])
        ]

    @staticmethod
    def get_global_parameters_tape(data_handler: InitDataHandler, name: str) -> CsvTape:
        _, data = data_handler.ensure_ftype(name, FileType.CSV)
        csv: pd.DataFrame = pd.read_csv(data)
        tape = CsvTape()
        tape.initialize(csv)
        tape.proceed_to(Moment(0))
        return tape

    def get_scenario_multipliers(self):
        return [
            ScalarParameter(mult, self._scenario_parameters_tape)
            for mult in self.config.get("scenario_multipliers", [])
        ]

    def get_local_contributors(
        self,
        state: TrackedState,
        schema: AttributeSchema,
    ) -> t.List[LocalContributor]:
        config = self.config
        rv = []

        for parameter in config.get("local_parameters", []):
            ds_name, entity_name, attr = parameter["attribute_path"]
            attr_spec = schema.get_spec(attr, DEFAULT_DATA_TYPE)

            registered_attr = state.register_attribute(
                dataset_name=ds_name,
                entity_name=entity_name,
                spec=attr_spec,
                flags=INIT,
            )
            info = LocalParameterInfo(
                target_dataset=ds_name,
                target_entity_group=entity_name,
                target_geometry=parameter["geometry"],
                target_attribute=registered_attr,
                elasticity=parameter["elasticity"],
            )
            calculator = self._local_mapping_type_to_calculators_dict[
                parameter.get("mapping_type", "nearest")
            ](info)
            rv.append(calculator)
        return rv

    def get_investment_contributors(self):
        if investments := [Investment(*i) for i in self.config.get("investment_multipliers", [])]:
            return [InvestmentContributor(investments, self._demand_entity.index)]
        return []

    def initialize(self, state: TrackedState):
        demand_geometry = self._demand_entity.get_geometry()
        mapper = LocalMapper(demand_geometry)
        self.demand_estimation.initialize(mapper)

        demand_matrix = self._demand_attribute.csr.as_matrix()
        self._update_demand_sum(demand_matrix)

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        if self.update_count >= self.max_iterations:
            return None

        self.proceed_tape(moment)

        demand_matrix = self._demand_attribute.csr.as_matrix()
        updated = self.demand_estimation.update(
            demand_matrix, self.update_count == 0, moment=moment
        )

        # Reset SUBSCRIBE before we publish results, so that all tracked changes are attributed to
        # our model's calculation
        state.reset_tracked_changes(SUBSCRIBE)

        self._demand_attribute.csr.update_from_matrix(updated)
        self._update_demand_sum(updated)

        self.update_count += 1

        return self._get_next_moment_from_tapes()

    def proceed_tape(self, moment: Moment):
        if self._scenario_parameters_tape is not None:
            self._scenario_parameters_tape.proceed_to(moment)

    def _get_next_moment_from_tapes(self) -> t.Optional[Moment]:
        if self._scenario_parameters_tape is None:
            return None
        return self._scenario_parameters_tape.get_next_timestamp()

    def new_time(self, state: TrackedState, moment: Moment):
        self.update_count = 0

    def _update_demand_sum(self, demand_matrix: np.ndarray):
        if self._total_outward_demand_attribute is not None:
            self._total_outward_demand_attribute[:] = np.sum(demand_matrix, axis=1)

        if self._total_inward_demand_attribute is not None:
            self._total_inward_demand_attribute[:] = np.sum(demand_matrix, axis=0)

    def shutdown(self, state: TrackedState) -> None:
        self.demand_estimation.close()


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/traffic_demand_calculation.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/traffic_demand_calculation.json"


def convert_v1_v2(config):
    rv = {
        "demand_path": [*config["demand_entity"][0], config["demand_property"][1]],
        "global_parameters": [
            {
                "name": config["global_parameters"][i],
                "elasticity": config["global_elasticities"][i],
            }
            for i in range(len(config.get("global_parameters", [])))
        ],
        "local_parameters": [
            {
                "attribute_path": [
                    *config["local_entity_groups"][i],
                    config["local_properties"][i][1],
                ],
                "geometry": config["local_geometries"][i],
                "elasticity": config["local_elasticities"][i],
                "mapping_type": config["local_mapping_type"][i]
                if "local_mapping_type" in config
                else "nearest",
            }
            for i in range(len(config.get("local_entity_groups", [])))
        ],
    }
    if "scenario_parameters" in config:
        rv["parameter_dataset"] = config["scenario_parameters"][0]

    if prop := config.get("total_inward_demand_property"):
        rv["total_inward_demand_attribute"] = prop[1]
    if prop := config.get("total_outward_demand_property"):
        rv["total_outward_demand_attribute"] = prop[1]

    for key in (
        "investment_multipliers",
        "atol",
        "rtol",
        "max_iterations",
        "scenario_multipliers",
    ):
        if key in config:
            rv[key] = config[key]

    return rv
