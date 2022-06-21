import typing as t

import numpy as np
import pandas as pd

from movici_simulation_core.core.moment import Moment, TimelineInfo, get_timeline_info


class CsvTape:
    def __init__(self, timeline_info: t.Optional[TimelineInfo] = None):
        self.timeline_info = timeline_info or get_timeline_info()
        self.timeline: np.ndarray = np.empty(0)  # integer timeline
        self.current_time: int = 0
        self.current_pos: int = -1
        self.last_pos: int = -1
        self.csv: t.Optional[pd.DataFrame] = None

    def __getitem__(self, key: str) -> float:
        return self.get_data(key=key)

    def initialize(self, csv: pd.DataFrame, time_column: str = "seconds"):
        self.csv = csv
        self.timeline = self._create_timeline(csv.pop(time_column))

    def get_data(self, key: str) -> float:
        return self.csv[key][self.current_pos]

    def assert_parameter(self, parameter_name):
        if parameter_name not in self.csv.columns:
            raise RuntimeError(f"Parameter {parameter_name} not found in supplied csv")

    def proceed_to(self, moment: Moment):
        self.current_time = moment.timestamp
        self.last_pos = self.current_pos
        self.current_pos = self._get_current_pos()

    def _get_current_pos(self):
        return np.searchsorted(self.timeline, self.current_time, side="right") - 1

    def has_update(self):
        return self.last_pos != self.current_pos

    def _create_timeline(self, timeline: pd.Series):
        timeline = timeline.apply(
            self.timeline_info.seconds_to_timestamp, convert_dtype=True
        ).array

        if not np.all(timeline[:-1] <= timeline[1:]):
            raise ValueError("Time data is not sorted.")
        return timeline

    def get_next_timestamp(self) -> t.Optional[Moment]:
        next_pos = self.current_pos + 1

        if next_pos >= len(self.timeline):
            return None

        return Moment(self.timeline[next_pos])
