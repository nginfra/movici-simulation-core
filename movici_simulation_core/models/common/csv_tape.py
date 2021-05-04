import typing as t

import numpy as np
import pandas as pd

from model_engine import TimeStamp


class CsvTape:
    def __init__(self):
        self.timeline: np.ndarray = np.empty(0)  # integer timeline
        self.parameters: t.Dict[str, np.ndarray] = {}
        self.current_time: int = 0
        self.current_pos: int = -1
        self.last_pos: int = -1

    def __getitem__(self, key: str) -> float:
        return self.get_data(key=key)

    def initialize(self, csv: pd.DataFrame, time_column: str = "seconds"):
        self.timeline = self._create_timeline(csv[time_column])

        for column in csv.columns:
            self.parameters[column] = np.array(csv[column])

    def get_data(self, key: str) -> float:
        return self.parameters[key][self.current_pos]

    @staticmethod
    def ensure_parameter(csv, parameter_name):
        if parameter_name not in csv:
            raise RuntimeError(f"Parameter {parameter_name} not found in supplied csv")

    def proceed_to(self, timestamp: TimeStamp):
        self.current_time = timestamp.time
        self.last_pos = self.current_pos
        self.current_pos = self._get_current_pos()

    def _get_current_pos(self):
        return np.searchsorted(self.timeline, self.current_time, side="right") - 1

    def has_update(self):
        changed = self.last_pos != self.current_pos
        return changed

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
        next_pos = self.current_pos + 1

        if next_pos >= len(self.timeline):
            return None

        return TimeStamp(self.timeline[next_pos])
