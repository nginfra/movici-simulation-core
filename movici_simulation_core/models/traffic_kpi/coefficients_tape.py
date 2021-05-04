import typing as t
from dataclasses import dataclass

import numpy as np
import pandas as pd

from movici_simulation_core.models.common.csv_tape import CsvTape


@dataclass(frozen=True)
class CoefficientDefinition:
    coefficient_name: str
    share_name: str
    load_capacity: str


class CoefficientsTape(CsvTape):
    coefficient_names: t.Dict[t.Tuple[str, str], t.List[CoefficientDefinition]]
    coefficients: t.Dict

    def __init__(self):
        super().__init__()
        self.coefficient_names = {}
        self.coefficients = {}

    def add_coefficient(
        self, category: str, kpi: str, coefficient_name: str, share_name: str, load_capacity: str
    ):
        key = (category, kpi)
        if key not in self.coefficient_names:
            self.coefficient_names[key] = []
        self.coefficient_names[key].append(
            CoefficientDefinition(
                coefficient_name=coefficient_name,
                share_name=share_name,
                load_capacity=load_capacity,
            )
        )

    def __getitem__(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        return self.get_data(key=key)

    def get_data(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        rv = []
        for item in self.coefficients[key]:
            rv.append(item[self.current_pos])
        return rv

    def initialize(self, csv: pd.DataFrame, time_column: str = "seconds"):
        super().initialize(csv, time_column)

        for key, definitions in self.coefficient_names.items():
            for definition in definitions:
                self.ensure_parameter(csv, definition.coefficient_name)
                self.ensure_parameter(csv, definition.share_name)
                self.ensure_parameter(csv, definition.load_capacity)

                if key not in self.coefficients:
                    self.coefficients[key] = []
                self.coefficients[key].append(
                    np.column_stack(
                        (
                            csv[definition.coefficient_name],
                            csv[definition.share_name],
                            csv[definition.load_capacity],
                        )
                    )
                )
