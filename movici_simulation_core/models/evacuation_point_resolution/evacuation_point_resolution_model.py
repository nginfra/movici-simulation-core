from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core import (
    INIT,
    PUB,
    SUB,
    AttributeSpec,
    DataType,
    TrackedModel,
    TrackedState,
    field,
)
from movici_simulation_core.attributes import Label
from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.attribute import OPT
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.validate import ensure_schema, validate_and_process

Evacuation_RoadIds = AttributeSpec("evacuation.road_ids", DataType(int, csr=True))
Evacuation_LastId = AttributeSpec("evacuation.last_id", int)

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/evacuation_point_resolution.json"


class EvacuationPoints(EntityGroup):
    road_ids = field(Evacuation_RoadIds, flags=INIT)
    label = field(Label, flags=OPT)


class RoadSegments(EntityGroup):
    last_id = field(Evacuation_LastId, flags=SUB)
    label = field(Label, flags=PUB)


class EvacuatonPointResolution(TrackedModel, name="evacuation_point_resolution"):
    evac_points: EvacuationPoints
    roads: RoadSegments
    label_mapping: t.Dict[int, int]

    def __init__(self, model_config: dict):
        validate_and_process(model_config, schema=ensure_schema(MODEL_CONFIG_SCHEMA_PATH))

        model_config.setdefault("evacuation_points", "evacuation_point_entities")
        model_config.setdefault("road_segments", "road_segment_entities")
        model_config.setdefault("mode", "id")
        super().__init__(model_config)

    def setup(self, state: TrackedState, **_):
        dataset = self.config["dataset"]
        points_name = self.config["evacuation_points"]
        roads_name = self.config["road_segments"]
        self.evac_points = state.register_entity_group(dataset, EvacuationPoints(points_name))
        self.roads = state.register_entity_group(dataset, RoadSegments(roads_name))

    def initialize(self, **_):
        if self.config["mode"] == "label":
            if not self.evac_points.label.is_initialized():
                raise NotReady()
            labels = self.evac_points.label.array
        else:
            labels = np.arange(len(self.evac_points))
        self.create_label_mapping(self.evac_points.road_ids.csr, labels)

    def update(self, **_):
        changed_indices = np.flatnonzero(self.roads.last_id.changed)
        if len(changed_indices) == 0:
            changed_indices = np.arange(len(self.roads))
        for idx in changed_indices:
            self.roads.label[idx] = self.label_mapping[self.roads.last_id[idx]]

    def create_label_mapping(
        self, road_ids: TrackedCSRArray, labels: np.ndarray
    ) -> t.Dict[int, int]:
        self.label_mapping = {}
        for (idx, label) in enumerate(labels):
            roads = road_ids.get_row(idx)
            for road in roads:
                self.label_mapping[road] = label

    @classmethod
    def get_schema_attributes(cls):
        return [Evacuation_LastId, Evacuation_RoadIds]
