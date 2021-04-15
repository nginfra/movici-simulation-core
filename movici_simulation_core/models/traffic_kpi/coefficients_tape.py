import typing as t
from dataclasses import dataclass

import numpy as np
import pandas as pd
from model_engine import TimeStamp


@dataclass(frozen=True)
class CoefficientDefinition:
    coefficient_name: str
    share_name: str
    load_capacity: str


class CoefficientsTape:

    timeline: np.ndarray  # integer timeline
    coefficient_names: t.Dict[t.Tuple[str, str], t.List[CoefficientDefinition]]
    coefficients: t.Dict

    def __init__(self):
        self.current_time: int = 0
        self.coefficient_names = {}
        self.coefficients = {}
        self.timeline = np.empty(0)
        self.current_pos = -1
        self.last_pos = -1

    def __getitem__(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        return self.get_data(key=key)

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

    def initialize(self, csv: pd.DataFrame):
        # todo something else than seconds?
        self.timeline = self._create_timeline(csv["seconds"])

        for key, definitions in self.coefficient_names.items():
            for definition in definitions:
                self._ensure_coefficient(csv, definition.coefficient_name)
                self._ensure_coefficient(csv, definition.share_name)
                self._ensure_coefficient(csv, definition.load_capacity)

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

    @staticmethod
    def _ensure_coefficient(csv, coefficient_name):
        if coefficient_name not in csv:
            raise RuntimeError(f"Coefficient {coefficient_name} not found in supplied csv")

    def proceed_to(self, timestamp: TimeStamp):
        self.current_time = timestamp.time
        self.last_pos = self.current_pos
        self.current_pos = self._get_current_pos()

    def _get_current_pos(self):
        return np.searchsorted(self.timeline, self.current_time, side="right") - 1

    def has_update(self):
        changed = self.last_pos != self.current_pos
        self.last_pos = self.current_pos
        return changed

    def get_data(self, key: t.Tuple[str, str]) -> t.List[np.ndarray]:
        rv = []
        for item in self.coefficients[key]:
            rv.append(item[self.current_pos])
        return rv

    @staticmethod
    def _create_timeline(timeline: np.ndarray):
        timeline = np.array(
            [TimeStamp(seconds=timestamp).time for timestamp in timeline],
            dtype=np.int32,
        )

        if not np.all(timeline[:-1] <= timeline[1:]):
            raise ValueError("Time data in not sorted.")
        return timeline

    def get_next_timestamp(
        self,
    ) -> t.Union[TimeStamp, None]:
        next_pos = self.last_pos + 1

        if next_pos >= len(self.timeline):
            return None

        return TimeStamp(self.timeline[next_pos])
