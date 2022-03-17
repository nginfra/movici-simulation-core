import typing as t
from dataclasses import dataclass

import numpy as np
import pandas as pd

from movici_simulation_core.models.common.csv_tape import CsvTape


@dataclass(frozen=True)
class CoefficientDefinition:
    coefficient_name: str
    share_name: str
    load_capacity: t.Optional[str] = None
    effective_load_factor: t.Optional[str] = None


class CoefficientsTape(CsvTape):
    coefficient_names: t.Dict[t.Tuple[str, str], t.List[t.Tuple[str, ...]]]
    coefficients: t.Dict

    def __init__(self):
        super().__init__()
        self.coefficient_names = {}
        self.coefficients = {}

    def add_coefficient(self, category: str, kpi: str, *coeffiencent_names):
        key = (category, kpi)
        if key not in self.coefficient_names:
            self.coefficient_names[key] = []
        self.coefficient_names[key].append(coeffiencent_names)

    def __getitem__(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        return self.get_data(key=key)

    def get_data(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        return [item[self.current_pos] for item in self.coefficients.get(key, [])]

    def initialize(self, csv: pd.DataFrame, time_column: str = "seconds"):
        super().initialize(csv, time_column)

        for key, coefficients in self.coefficient_names.items():
            if key not in self.coefficients:
                self.coefficients[key] = []
            for coeff in coefficients:

                columns = []
                for item in coeff:
                    self.assert_parameter(item)
                    columns.append(csv[item])

                self.coefficients[key].append(np.column_stack(columns))
