import typing as t

import numpy as np
import pandas as pd
from model_engine import TimeStamp, DataFetcher, Config
from model_engine.model_driver.data_handlers import DType
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import (
    PUB,
    SUB,
    UniformProperty,
    CSRProperty,
    INIT,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.common.entities import (
    GeometryEntity,
    PointEntity,
)
from movici_simulation_core.models.traffic_demand_calculation.local_effect_calculators import (
    LocalEffectsCalculator,
    TransportPathingValueSum,
    NearestValue,
)
from spatial_mapper.mapper import Mapper, Mapping

# seconds, entity_id, multiplier
Investment = t.Tuple[int, int, float]


class Model(TrackedBaseModel):
    """
    Implementation of the demand estimation model.
    Reads a csv with scenario parameters.
    Calculates changes in the od matrices based on change of scenario parameters in time.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    _demand_property: CSRProperty
    _demand_entity: GeometryEntity
    _total_inward_demand_property: t.Optional[UniformProperty] = None
    _total_outward_demand_property: t.Optional[UniformProperty] = None

    _scenario_parameters_tape: t.Optional[CsvTape] = None
    _global_parameters: t.List[str]
    _global_elasticities: t.List[float]

    _local_factor_calculators: t.List[LocalEffectsCalculator]

    _investments: t.List
    _investment_idx: int

    _new_timesteps_first_update: bool = True

    _current_parameters: t.Dict[str, float]

    _local_mapping_type_to_calculators_dict = {
        "nearest": NearestValue,
        "route": TransportPathingValueSum,
    }

    def setup(
        self,
        state: TrackedState,
        config: dict,
        scenario_config: Config,
        data_fetcher: DataFetcher,
        **_,
    ):
        self.set_demand_entity(config, state)

        self.setup_local_calculators(config=config, scenario_config=scenario_config, state=state)
        self.set_global_parameters(config, data_fetcher)

        self._investments = config.get("investment_multipliers", [])
        self._investment_idx = 0

        # We remove auto reset for SUB because
        #  we are subbing and pubbing same properties.
        self.auto_reset = PUB

    def set_demand_entity(self, config, state):
        ds_name, demand_entity = config["demand_entity"][0]
        self._demand_entity = state.register_entity_group(
            dataset_name=ds_name, entity=PointEntity(name=demand_entity)
        )
        prop_spec = property_mapping[tuple(config["demand_property"])]
        self._demand_property = state.register_property(
            dataset_name=ds_name,
            entity_name=demand_entity,
            spec=prop_spec,
            flags=INIT | PUB,
            rtol=config.get("rtol", 1e-5),
            atol=config.get("atol", 1e-8),
        )

        sum_prop_config_in = config.get("total_inward_demand_property")
        if sum_prop_config_in:
            sum_prop_spec = property_mapping[tuple(sum_prop_config_in)]
            self._total_inward_demand_property = state.register_property(
                dataset_name=ds_name,
                entity_name=demand_entity,
                spec=sum_prop_spec,
                flags=PUB,
            )

        sum_prop_config_out = config.get("total_outward_demand_property")
        if sum_prop_config_out:
            sum_prop_spec = property_mapping[tuple(sum_prop_config_out)]
            self._total_outward_demand_property = state.register_property(
                dataset_name=ds_name,
                entity_name=demand_entity,
                spec=sum_prop_spec,
                flags=PUB,
            )

    def set_global_parameters(self, config, data_fetcher):
        self._current_parameters = {}
        self._global_parameters = config.get("global_parameters", [])
        self._global_elasticities = config.get("global_elasticities", [])

        if len(self._global_parameters) == 0 and len(self._global_elasticities) == 0:
            return

        if len(self._global_parameters) != len(self._global_elasticities):
            raise RuntimeError(
                "global_parameters should have the same length of global_elasticities"
            )
        self._initialize_scenario_parameters_tape(data_fetcher, config["scenario_parameters"][0])

    def setup_local_calculators(self, config: dict, scenario_config: Config, state: TrackedState):
        self._local_factor_calculators = []

        if "local_entity_groups" not in config or "local_properties" not in config:
            return

        local_prop_is_iterative = config.get(
            "local_prop_is_iterative", [True] * len(config["local_entity_groups"])
        )
        mapping_type = config.get(
            "local_mapping_type", ["nearest"] * len(config["local_entity_groups"])
        )
        for entity, prop, geom, iterative, mapping_type, elasticity in zip(
            config["local_entity_groups"],
            config["local_properties"],
            config["local_geometries"],
            local_prop_is_iterative,
            mapping_type,
            config["local_elasticities"],
        ):
            ds_name, entity_name = entity
            prop_spec = property_mapping[tuple(prop)]

            registered_prop = state.register_property(
                dataset_name=ds_name,
                entity_name=entity_name,
                spec=prop_spec,
                flags=INIT,
                atol=1e-8 if iterative else float("inf"),
            )

            calculator = self._local_mapping_type_to_calculators_dict[mapping_type]()
            calculator.setup(
                state=state,
                prop=registered_prop,
                ds_name=ds_name,
                entity_name=entity_name,
                geom=geom,
                elasticity=elasticity,
                scenario_config=scenario_config,
            )
            self._local_factor_calculators.append(calculator)

    def _initialize_scenario_parameters_tape(self, data_fetcher: DataFetcher, name: str):
        dtype, data = data_fetcher.get(name)
        if dtype != DType.CSV:
            raise RuntimeError("Given non-csv as CSV input")
        csv: pd.DataFrame = pd.read_csv(data)
        self._scenario_parameters_tape = CsvTape()
        self._scenario_parameters_tape.initialize(csv)
        self._scenario_parameters_tape.proceed_to(TimeStamp(0))

    def initialize(self, state: TrackedState):
        for param in self._global_parameters:
            self._current_parameters[param] = self._scenario_parameters_tape[param]

        self._initialize_local_calculators()

        demand_matrix = self._get_matrix(self._demand_property.csr)
        self._update_demand_sum(demand_matrix)

    def _initialize_local_calculators(self):
        mappings: t.Dict[EntityGroup, Mapping] = {}

        demand_geometry = self._demand_entity.get_geometry()

        for calculator in self._local_factor_calculators:
            entity = calculator.get_target_entity()
            # This works as the hash for an EntityGroup is customized
            if entity in mappings:
                mapping = mappings[entity]
            else:
                mapping = Mapper(entity.get_geometry()).find_nearest(demand_geometry)
                mappings[entity] = mapping
            calculator.initialize(mapping.seq)

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        self._proceed_tapes(time_stamp)

        if not self._any_changes() and not self._new_timesteps_first_update:
            state.reset_tracked_changes(SUB)
            self._new_timesteps_first_update = False
            return TimeStamp(time=time_stamp.time + 1)

        multiplication_factor = self._compute_multiplication_factor(time_stamp)

        demand_matrix = self._get_matrix(self._demand_property.csr)
        demand_matrix *= multiplication_factor

        # Reset our PUB | INIT which is also SUB underwater before we publish results
        state.reset_tracked_changes(SUB)

        self._set_demands(demand_matrix, self._demand_property.csr)
        self._update_demand_sum(demand_matrix)

        self._new_timesteps_first_update = False

        return self._get_next_timestep_from_tapes()

    def _proceed_tapes(self, time_stamp: TimeStamp):
        if self._scenario_parameters_tape is not None:
            self._scenario_parameters_tape.proceed_to(time_stamp)

    def _compute_multiplication_factor(self, time_stamp: TimeStamp):
        global_factor = 1.0
        if (
            self._scenario_parameters_tape is not None
            and self._scenario_parameters_tape.has_update()
        ):
            global_factor = self._calculate_global_factor()
        matrix_dimension = self._demand_property.csr.size
        multiplication_factor = np.full(
            shape=(matrix_dimension, matrix_dimension), fill_value=global_factor, dtype=np.float64
        )
        self._add_local_property_effects_to_factor(multiplication_factor)
        self._add_investments_to_factor(time_stamp, multiplication_factor)
        return multiplication_factor

    def _get_next_timestep_from_tapes(self) -> t.Optional[TimeStamp]:
        if self._scenario_parameters_tape is None:
            return None
        return self._scenario_parameters_tape.get_next_timestamp()

    def new_time(self, state: TrackedState, time_stamp: TimeStamp):
        self._new_timesteps_first_update = True

    def _any_changes(self) -> False:
        if (
            self._scenario_parameters_tape is not None
            and self._scenario_parameters_tape.has_update()
        ):
            return True
        for calculator in self._local_factor_calculators:
            if calculator.property_has_changes():
                return True
        return False

    def _add_local_property_effects_to_factor(self, multiplication_factor: np.ndarray):
        for calculator in self._local_factor_calculators:
            calculator.update_matrix(
                multiplication_factor, force_update=self._new_timesteps_first_update
            )

    def _add_investments_to_factor(self, timestamp: TimeStamp, multiplication_factor: np.ndarray):
        while not self._investment_idx >= len(self._investments):
            next_investment = self._investments[self._investment_idx]
            if next_investment[0] <= timestamp.seconds:
                idx = self._demand_entity.index[[next_investment[1]]]
                multiplication_factor[idx] *= next_investment[2]
                multiplication_factor[:, idx] *= next_investment[2]
            else:
                break
            self._investment_idx += 1

    def _calculate_global_factor(self) -> float:
        global_factor = 1.0
        for i, param in enumerate(self._global_parameters):
            current_param = self._scenario_parameters_tape[param]
            old_param = self._current_parameters[param]
            global_factor *= (current_param / old_param) ** (2 * self._global_elasticities[i])
            self._current_parameters[param] = current_param
        return global_factor

    @staticmethod
    def _set_demands(demand_matrix: np.ndarray, demand_csr: TrackedCSRArray) -> None:
        for i in range(demand_csr.size):
            update_csr = TrackedCSRArray(demand_matrix[i], [0, demand_csr.size])
            demand_csr.update(update_csr, np.array([i]))

    def _update_demand_sum(self, demand_matrix: np.ndarray):
        if self._total_outward_demand_property is not None:
            self._total_outward_demand_property[:] = np.sum(demand_matrix, axis=1)

        if self._total_inward_demand_property is not None:
            self._total_inward_demand_property[:] = np.sum(demand_matrix, axis=0)

    @staticmethod
    def _get_matrix(csr_array: TrackedCSRArray):
        matrix = []
        for i in range(csr_array.size):
            matrix.append(csr_array.get_row(i))
        return np.stack(matrix)

    def shutdown(self, state: TrackedState) -> None:
        for calculator in self._local_factor_calculators:
            calculator.shutdown()
