from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from movici_simulation_core.core.attributes import (
    Reference,
    ConnectionProperties_ToDataset,
    ConnectionProperties_ToReferences,
)
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, UniformProperty, OPT
import typing as t


@dataclass
class Connection:
    connected_entities: t.Union[TimeWindowStatusEntity, TimeWindowEntity]
    connected_indices: t.Sequence[int]


@dataclass
class ScheduleEvent:
    is_start: bool
    source_index: int


class TimeWindowStatusEntity(EntityGroup):
    reference = field(Reference, flags=INIT)
    time_window_status: UniformProperty = None
    event_count: np.array = None

    def initialize_event_count(self):
        if self.index is None:
            raise ValueError("Not Initialized")
        self.event_count = np.zeros((len(self),), dtype=int)

    def update_status(self):
        if self.time_window_status.has_data() and self.event_count is not None:
            self.time_window_status[:] = self.event_count > 0


class TimeWindowEntity(EntityGroup):
    connection_to_dataset = field(ConnectionProperties_ToDataset, flags=OPT)
    connection_to_references = field(ConnectionProperties_ToReferences, flags=OPT)
    time_window_begin: UniformProperty = None
    time_window_end: UniformProperty = None

    connections: t.List[t.List[Connection]] = None

    def initialize_connections(self):
        if self.index is None:
            raise ValueError("Not Initialized")
        self.connections = [[] for _ in range(len(self))]

    def add_connection(self, index: int, connection: Connection):
        self.connections[index].append(connection)

    def get_connections(self, index: int):
        return self.connections[index]
