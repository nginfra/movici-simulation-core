import typing as t

import numba
import numpy as np
import pandas as pd
from model_engine import TimeStamp, DataFetcher
from model_engine.model_driver.data_handlers import DType
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray, TrackedArray
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
from movici_simulation_core.models.common.entities import GeometryEntity, PointEntity
from movici_simulation_core.models.overlap_status.model import try_get_geometry_type
from spatial_mapper.mapper import Mapper


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

    _local_elasticities: t.List[float]
    _local_entities: t.List[t.Union[GeometryEntity, EntityGroup]]
    _local_properties: t.List[UniformProperty]
    _local_closest_entity_index: t.List[np.ndarray]
    _prev_timestep_local_properties: t.List[TrackedArray]

    _current_parameters: t.Dict[str, float]

    def setup(self, state: TrackedState, config: dict, data_fetcher: DataFetcher, **_):
        self.set_demand_entity(config, state)

        self.set_local_parameters(config, state)
        self.set_global_parameters(config, data_fetcher)

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
        self._global_parameters = config["global_parameters"]
        self._global_elasticities = config["global_elasticities"]

        if len(self._global_parameters) != len(self._global_elasticities):
            raise RuntimeError(
                "global_parameters should have the same length of global_elasticities"
            )
        self._current_parameters = {}
        self._initialize_scenario_parameters_tape(data_fetcher, config["scenario_parameters"][0])

    def set_local_parameters(self, config, state):
        self._local_entities = []
        self._local_properties = []
        self._local_elasticities = []

        if "local_entity_groups" not in config:
            return

        for entity, prop, geom in zip(
            config["local_entity_groups"],
            config["local_properties"],
            config["local_geometries"],
        ):
            ds_name, entity_name = entity
            self._local_entities.append(
                state.register_entity_group(
                    dataset_name=ds_name,
                    entity=try_get_geometry_type(geom)(name=entity_name),
                )
            )
            prop_spec = property_mapping[tuple(prop)]
            self._local_properties.append(
                state.register_property(
                    dataset_name=ds_name,
                    entity_name=entity_name,
                    spec=prop_spec,
                    flags=INIT,
                )
            )
        self._local_elasticities = config["local_elasticities"]

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

        point_geom_mapper = Mapper(self._demand_entity.get_geometry())
        self._local_closest_entity_index = []
        for entity in self._local_entities:
            # todo do this whole thing twice
            mapping = point_geom_mapper.find_nearest(entity.get_geometry())
            self._local_closest_entity_index.append(mapping.seq)

        self._initialize_state()

    def _initialize_state(self):
        self._prev_timestep_local_properties = []
        for prop in self._local_properties:
            self._prev_timestep_local_properties.append(prop.array.copy())

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        self._scenario_parameters_tape.proceed_to(time_stamp)
        demand_matrix = self._get_matrix(self._demand_property.csr)
        if not self._any_changes():
            state.reset_tracked_changes(SUB)
            self._update_demand_sum(demand_matrix)
            return self._scenario_parameters_tape.get_next_timestamp()

        global_factor = 1
        if self._scenario_parameters_tape.has_update():
            global_factor = self._calculate_global_factor()

        matrix_dimension = self._demand_property.csr.size
        multiplication_factor = np.full(
            shape=(matrix_dimension, matrix_dimension), fill_value=global_factor
        )

        multiplication_factor = self._add_local_property_effects_to_factor(multiplication_factor)
        demand_matrix *= multiplication_factor

        # Reset our PUB | INIT which is also SUB underwater before we publish results
        state.reset_tracked_changes(SUB)

        self._update_demands(demand_matrix, self._demand_property.csr)

        self._update_demand_sum(demand_matrix)

        return self._scenario_parameters_tape.get_next_timestamp()

    def _any_changes(self) -> False:
        if self._scenario_parameters_tape.has_update():
            return True
        for prop in self._local_properties:
            if prop.has_changes():
                return True
        return False

    def _add_local_property_effects_to_factor(
        self, multiplication_factor: np.ndarray
    ) -> np.ndarray:
        for prop_idx, (elasticity, prop, closest_entity_index) in enumerate(
            zip(self._local_elasticities, self._local_properties, self._local_closest_entity_index)
        ):
            if not prop.has_changes():
                continue

            update_multiplication_factor(
                multiplication_factor,
                closest_entity_index,
                prop.array,
                self._prev_timestep_local_properties[prop_idx],
                elasticity,
            )

            self._prev_timestep_local_properties[prop_idx] = prop.array.copy()
        return multiplication_factor

    def _calculate_global_factor(self) -> float:
        global_factor = 1.0
        for i, param in enumerate(self._global_parameters):
            current_param = self._scenario_parameters_tape[param]
            old_param = self._current_parameters[param]
            global_factor *= (current_param / old_param) ** (2 * self._global_elasticities[i])
            self._current_parameters[param] = current_param
        return global_factor

    @staticmethod
    def _update_demands(demand_matrix: np.ndarray, demand_csr: TrackedCSRArray) -> None:
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


@numba.njit(cache=True)
def update_multiplication_factor(
    multiplication_factor: np.ndarray, closest_entity_index, prop, old_prop, elasticity
):
    dim_i, dim_j = multiplication_factor.shape
    for i in range(dim_i):
        for j in range(dim_j):
            i_closest = closest_entity_index[i]
            j_closest = closest_entity_index[j]

            # TODO: if this is a line, get route, get delay

            prop_i = prop[i_closest]
            old_prop_i = old_prop[i_closest]

            prop_j = prop[j_closest]
            old_prop_j = old_prop[j_closest]

            multiplication_factor[i][j] *= (
                prop_i / old_prop_i * prop_j / old_prop_j
            ) ** elasticity
