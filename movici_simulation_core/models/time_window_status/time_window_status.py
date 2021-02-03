import math
from collections import deque, defaultdict
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Optional, List, Dict, cast, Deque, Set, Union

import numpy as np

from model_engine import TimeStamp
from model_engine.dataset_manager.data_entity import DataEntityHandler
from model_engine.dataset_manager.dataset_handler import DataSet
from model_engine.dataset_manager.exception import IncompleteInitializationData
from model_engine.dataset_manager.numba_functions import csr_item
from movici_simulation_core.models.time_window_status.dataset import (
    TimeWindowEntity,
    TimeWindowStatusEntity,
)


@dataclass
class Connection:
    connected_entities: Union[TimeWindowStatusEntity, TimeWindowEntity]
    connected_indices: List[int]


@dataclass
class ScheduleEvent:
    time_step: int
    is_start: bool
    connection_index: int


class TimeWindowStatus:
    def __init__(
        self,
        time_window_dataset: DataSet,
        status_datasets: List[DataSet],
        logger: Logger,
        time_reference: float,
        time_scale: float,
    ) -> None:
        self._logger = logger
        self._time_window_dataset = time_window_dataset
        self._status_datasets: Dict[str, DataSet] = {}
        for ds in status_datasets:
            self._status_datasets[ds.name] = ds

        self._time_reference = time_reference
        self._time_scale = time_scale

        self._connections: List[Connection] = []
        self._full_schedule: List[ScheduleEvent] = []
        self._schedule: Deque[ScheduleEvent] = deque()
        self._entity_statuses: Dict[
            Union[TimeWindowStatusEntity, TimeWindowEntity], Dict[int, Set[int]]
        ] = defaultdict(dict)

        self._first_update = True

        for ds in status_datasets + [time_window_dataset]:
            if not ds.is_complete_for_init():
                raise IncompleteInitializationData()
            ds.reset_track_update()

        self._window_in_same_entities = (
            len(status_datasets) == 1 and status_datasets[0] == time_window_dataset
        )

        self._resolve_connections()
        self._resolve_schedule()

    def update(self, time_stamp: TimeStamp) -> Optional[TimeStamp]:
        if self._first_update:
            self._initialize_statuses()
            self._first_update = False

        if not self._schedule:
            return

        while self._schedule and time_stamp.time >= self._schedule[0].time_step:
            self._update_statuses(self._schedule.popleft())

        self._publish_statuses()

        if not self._schedule:
            return

        return TimeStamp(time=self._schedule[0].time_step)

    def _resolve_connections(self):
        if self._connections:
            return

        connection_entities = cast(TimeWindowEntity, self._get_entity(self._time_window_dataset))

        if self._window_in_same_entities:
            for index, _ in enumerate(connection_entities.ids):
                self._connections.append(Connection(connection_entities, [index]))
                return

        for i, dataset_name in enumerate(connection_entities.connection_to_dataset.data):
            references = csr_item(
                connection_entities.connection_to_references.data,
                connection_entities.connection_to_references.indptr,
                i,
            )
            connected_entities = cast(
                TimeWindowStatusEntity, self._get_entity(self._status_datasets[dataset_name])
            )
            connected_indices = np.where(np.in1d(connected_entities.reference.data, references))[0]
            self._connections.append(Connection(connected_entities, connected_indices))

    def _resolve_schedule(self):
        time_window_entities = cast(TimeWindowEntity, self._get_entity(self._time_window_dataset))
        for i, (time_window_begin, time_window_end) in enumerate(
            zip(
                time_window_entities.time_window_begin.data,
                time_window_entities.time_window_end.data,
            )
        ):
            if (
                time_window_begin == time_window_entities.time_window_begin.undefined
                or time_window_end == time_window_entities.time_window_end.undefined
            ):
                continue

            begin = self._calculate_time_step(time_window_begin)
            end = self._calculate_time_step(time_window_end)

            self._full_schedule.append(ScheduleEvent(begin, True, i))
            self._full_schedule.append(ScheduleEvent(end, False, i))

        self._full_schedule = list(sorted(self._full_schedule, key=lambda x: x.time_step))
        for elem in self._full_schedule:
            self._schedule.append(elem)

    def _initialize_statuses(self):
        for connection in self._connections:
            status_dict = self._entity_statuses[connection.connected_entities]
            for i in connection.connected_indices:
                status_dict[i] = set()
            time_window_status = connection.connected_entities.time_window_status.data
            connection.connected_entities.time_window_status = np.zeros(
                len(time_window_status), dtype=bool
            )

    def _update_statuses(self, event: ScheduleEvent):
        connection = self._connections[event.connection_index]
        status_dict = self._entity_statuses[connection.connected_entities]
        for i in connection.connected_indices:
            if event.is_start:
                status_dict[i].add(i)
            else:
                status_dict[i].remove(i)

    def _publish_statuses(self):
        for entities, status_dict in self._entity_statuses.items():
            time_window_status = entities.time_window_status.data.copy()
            for entity_index, events in status_dict.items():
                time_window_status[entity_index] = len(events) > 0
            entities.time_window_status = time_window_status

    def _calculate_time_step(self, date: str):
        return math.ceil(
            (datetime.strptime(date, "%Y-%m-%d").timestamp() - self._time_reference)
            / self._time_scale
        )

    @staticmethod
    def _get_entity(dataset: DataSet) -> DataEntityHandler:
        return list(dataset.data.values())[0]
