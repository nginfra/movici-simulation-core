import typing as t
from collections import deque

import numpy as np

from movici_simulation_core.core.moment import Moment, TimelineInfo
from movici_simulation_core.models.common.time_series import TimeSeries
from movici_simulation_core.models.time_window_status.dataset import (
    Connection,
    ScheduleEvent,
    TimeWindowEntity,
    TimeWindowStatusEntity,
)


class TimeWindowStatus:
    def __init__(
        self,
        source_entities: TimeWindowEntity,
        target_entities: t.List[TimeWindowStatusEntity],
        timeline_info: TimelineInfo,
    ):
        self.source_entities = source_entities
        self.target_entities = target_entities
        self.timeline_info = timeline_info
        self.schedule: t.Optional[TimeSeries[ScheduleEvent]] = None

    @property
    def self_targets(self):
        return [e for e in self.target_entities if self.source_entities.is_similiar(e)]

    @property
    def foreign_targets(self):
        return [e for e in self.target_entities if not self.source_entities.is_similiar(e)]

    def can_initialize(self):
        # can only initialize if there are no foreign target entity groups, or if the source
        # connection data is available
        return not self.foreign_targets or (
            self.source_entities.connection_to_dataset.is_initialized()
            and self.source_entities.connection_to_references.is_initialized()
        )

    def initialize(self):
        self.source_entities.initialize_connections()
        for target in self.target_entities:
            target.initialize_event_count()

        self.resolve_connections()
        self.resolve_schedule()
        self.update_statuses()

    def update(self, moment: Moment):
        if not self.schedule:
            return

        for _, event in self.schedule.pop_until(moment.timestamp):
            self.process_event(event)
        self.update_statuses()

        return Moment(self.schedule.next_time) if self.schedule.next_time is not None else None

    def resolve_connections(self):
        for entity in self.self_targets:
            for i in range(len(entity)):
                self.source_entities.add_connection(i, Connection(entity, [i]))

        for idx, dataset in enumerate(self.source_entities.connection_to_dataset.array):
            to_references = self.source_entities.connection_to_references.csr.slice([idx]).data
            for target in self.foreign_targets:
                connected_indices = np.flatnonzero(np.in1d(target.reference.array, to_references))
                if len(connected_indices) > 0:
                    self.source_entities.add_connection(idx, Connection(target, connected_indices))

    def resolve_schedule(self):
        if (
            self.source_entities.time_window_begin is None
            or self.source_entities.time_window_end is None
        ):
            self.schedule = deque()
            return

        unsorted_events: t.List[t.Tuple[int, ScheduleEvent]] = []
        defined = ~(
            self.source_entities.time_window_begin.is_undefined()
            | self.source_entities.time_window_end.is_undefined()
        )
        for i, time_window_begin, time_window_end in zip(
            np.arange(len(self.source_entities))[defined],
            self.source_entities.time_window_begin.array[defined],
            self.source_entities.time_window_end.array[defined],
        ):

            begin = self.timeline_info.string_to_timestamp(time_window_begin)
            end = self.timeline_info.string_to_timestamp(time_window_end)

            unsorted_events.append((begin, ScheduleEvent(True, i)))
            unsorted_events.append((end, ScheduleEvent(False, i)))
        self.schedule = TimeSeries(sorted(unsorted_events, key=lambda e: e[0]))

    def process_event(self, event: ScheduleEvent):
        connections = self.source_entities.connections[event.source_index]
        for connection in connections:
            target = connection.connected_entities
            target.event_count[connection.connected_indices] += 1 if event.is_start else -1

    def update_statuses(self):
        for entity_group in self.target_entities:
            entity_group.update_status()
