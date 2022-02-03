import itertools
import logging
import typing as t

import numpy as np
import pandas as pd

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.attribute import (
    PUB,
    UniformAttribute,
    CSRAttribute,
    INIT,
    PUBLISH,
    SUBSCRIBE,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.model_connector.init_data import InitDataHandler, FileType
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.common.entities import (
    GeometryEntity,
    PointEntity,
)
from movici_simulation_core.models.traffic_demand_calculation.global_contributors import (
    GlobalElasticityParameter,
    ScalarParameter,
)
from movici_simulation_core.models.traffic_demand_calculation.common import (
    LocalContributor,
    GlobalContributor,
    DemandEstimation,
    LocalMapper,
)
from movici_simulation_core.models.traffic_demand_calculation.local_contributors import (
    RouteCostFactor,
    NearestValue,
    InducedDemand,
    LocalParameterInfo,
    Investment,
    InvestmentContributor,
)
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings

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
        "extended_route": InducedDemand,
    }

    def __init__(self, model_config: dict):
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
        local_contributors = self.get_local_contributors(
            settings=settings, state=state, schema=schema, logger=logger
        )
        investments = self.get_investment_contributors()

        self.demand_estimation = DemandEstimation(
            global_contributors + scenario_multipliers, local_contributors + investments
        )
        self.demand_estimation.setup(state=state, settings=settings, schema=schema, logger=logger)

    def configure_demand_nodes(self, state: TrackedState, schema: AttributeSchema):
        config = self.config
        ds_name, demand_entity = config["demand_entity"][0]
        self._demand_entity = state.register_entity_group(
            dataset_name=ds_name, entity=PointEntity(name=demand_entity)
        )
        self._demand_attribute = state.register_attribute(
            dataset_name=ds_name,
            entity_name=demand_entity,
            spec=schema.get_spec(config["demand_property"], DEFAULT_CSR_DATA_TYPE),
            flags=INIT | PUB,
            rtol=config.get("rtol", 1e-5),
            atol=config.get("atol", 1e-8),
        )

        if sum_attr_config_in := config.get("total_inward_demand_property"):
            self._total_inward_demand_attribute = state.register_attribute(
                dataset_name=ds_name,
                entity_name=demand_entity,
                spec=schema.get_spec(sum_attr_config_in, DEFAULT_DATA_TYPE),
                flags=PUB,
            )

        if sum_attr_config_out := config.get("total_outward_demand_property"):
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
        global_parameters = config.get("global_parameters", [])
        global_elasticities = config.get("global_elasticities", [])

        if len(global_parameters) == 0 and len(global_elasticities) == 0:
            return []

        if len(global_parameters) != len(global_elasticities):
            raise RuntimeError(
                "global_parameters should have the same length of global_elasticities"
            )
        self._scenario_parameters_tape = tape = self.get_global_parameters_tape(
            data_handler, config["scenario_parameters"][0]
        )
        return [
            GlobalElasticityParameter(param, tape, elasticity)
            for param, elasticity in zip(global_parameters, global_elasticities)
        ]

    @staticmethod
    def get_global_parameters_tape(data_handler: InitDataHandler, name: str) -> CsvTape:
        dtype, data = data_handler.ensure_ftype(name, FileType.CSV)
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
        settings: Settings,
        state: TrackedState,
        schema: AttributeSchema,
        logger: logging.Logger,
    ) -> t.List[LocalContributor]:
        config = self.config
        rv = []
        if "local_entity_groups" not in config or "local_properties" not in config:
            return rv

        for entity, attr, geom, mapping_type, elasticity in zip(
            config.get("local_entity_groups", []),
            config.get("local_properties", []),
            config.get("local_geometries", []),
            config.get("local_mapping_type", itertools.repeat("nearest")),
            config.get("local_elasticities", []),
        ):
            ds_name, entity_name = entity
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
                target_geometry=geom,
                target_attribute=registered_attr,
                elasticity=elasticity,
            )
            calculator = self._local_mapping_type_to_calculators_dict[mapping_type](info)
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
