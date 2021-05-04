import typing as t

import numpy as np
import pandas as pd

from model_engine import TimeStamp, DataFetcher
from model_engine.model_driver.data_handlers import DType
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.property import PUB, SUB
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.csv_tape import CsvTape
from .entities import DemandNodeEntity


class Model(TrackedBaseModel):
    """
    Implementation of the demand estimation model.
    Reads a csv with scenario parameters.
    Calculates changes in the od matrices based on change of scenario parameters in time.

    Asgarpour, S., Konstantinos, K., Hartmann, A., and Neef, R. (2021).
    Modeling interdependent infrastructures under future scenarios. Work in Progress.
    """

    _demand_nodes: t.Optional[DemandNodeEntity]
    _scenario_parameters_tape: t.Optional[CsvTape]
    _global_parameters: t.List[str]
    _global_elasticity: t.List[float]

    _current_parameters: t.Dict[str, float]

    def setup(self, state: TrackedState, config: dict, data_fetcher: DataFetcher, **_):
        ds_name = config["transport_dataset"][0]
        self._demand_nodes = state.register_entity_group(
            dataset_name=ds_name, entity=DemandNodeEntity(name="virtual_node_entities")
        )

        self._global_parameters = config["global_parameters"]
        self._global_elasticity = config["global_elasticity"]

        if len(self._global_parameters) != len(self._global_elasticity):
            raise RuntimeError(
                "global_parameters should have the same length of global_elasticity"
            )

        self._current_parameters = {}
        self._initialize_scenario_parameters_tape(data_fetcher, config["scenario_parameters"][0])

        # We remove auto reset for SUB because
        #  we are subbing and pubbing same properties.
        self.auto_reset = PUB

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

    def update(self, state: TrackedState, time_stamp: TimeStamp):
        # We dont care about SUB changes after we are initialized
        state.reset_tracked_changes(SUB)

        self._scenario_parameters_tape.proceed_to(time_stamp)

        if not self._scenario_parameters_tape.has_update():
            return self._scenario_parameters_tape.get_next_timestamp()

        global_factor = self._calculate_global_factor()
        self._publish_demand_changes(self._demand_nodes.passenger_demand.csr, global_factor)
        self._publish_demand_changes(self._demand_nodes.cargo_demand.csr, global_factor)

        return self._scenario_parameters_tape.get_next_timestamp()

    def _calculate_global_factor(self) -> float:
        global_factor = 1
        for i, param in enumerate(self._global_parameters):
            current_param = self._scenario_parameters_tape[param]
            old_param = self._current_parameters[param]
            global_factor *= (current_param / old_param) ** (2 * self._global_elasticity[i])
            self._current_parameters[param] = current_param
        return global_factor

    @staticmethod
    def _publish_demand_changes(demand_csr: TrackedCSRArray, global_factor: float) -> None:
        for i in range(len(demand_csr.row_ptr) - 1):
            existing_demand_row = demand_csr.get_row(i)
            new_demand_row = existing_demand_row * global_factor
            if not np.array_equal(existing_demand_row, new_demand_row):
                update_csr = TrackedCSRArray(new_demand_row, [0, len(new_demand_row)])
                demand_csr.update(update_csr, np.array([i]))
