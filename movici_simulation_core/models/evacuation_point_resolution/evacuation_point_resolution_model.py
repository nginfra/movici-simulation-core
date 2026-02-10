from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core import (
    INIT,
    OPT,
    PUB,
    AttributeSchema,
    AttributeSpec,
    DataType,
    TrackedModel,
    TrackedState,
    field,
)
from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.json_schemas import SCHEMA_PATH

Evacuation_RoadIds = AttributeSpec("evacuation.road_ids", DataType(int, csr=True))
Evacuation_LastId = AttributeSpec("evacuation.last_id", int)
Evacuation_EvacuationPointId = AttributeSpec("evacuation.evacuation_point_id", int)
MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/evacuation_point_resolution.json"
DEFAULT_SPECIAL_VALUE = -9999


class EvacuationPoints(EntityGroup):
    road_ids = field(Evacuation_RoadIds, flags=INIT)


class RoadSegments(EntityGroup):
    last_id = field(Evacuation_LastId, flags=OPT)


class EvacuatonPointResolution(TrackedModel, name="evacuation_point_resolution"):
    __model_config_schema__ = MODEL_CONFIG_SCHEMA_PATH
    evac_points: EvacuationPoints
    roads: RoadSegments
    label_mapping: t.Dict[int, int]

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.config.setdefault(
            "evacuation_points", {"entity_group": "evacuation_point_entities", "attribute": "id"}
        )
        self.config.setdefault(
            "road_segments",
            {
                "entity_group": "road_segment_entities",
                "attribute": Evacuation_EvacuationPointId.name,
            },
        )

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        dataset = self.config["dataset"]
        points = self.config["evacuation_points"]
        roads = self.config["road_segments"]

        self.evac_points = self._register_entity_group(
            state, schema, dataset, EvacuationPoints, config=points, flag=INIT
        )

        self.roads = self._register_entity_group(
            state, schema, dataset, RoadSegments, config=roads, flag=PUB
        )

    @staticmethod
    def _register_entity_group(
        state: TrackedState,
        schema: AttributeSchema,
        dataset: str,
        entity_cls: t.Type[EntityGroup],
        config: dict,
        flag: int,
    ):
        entity_group = state.register_entity_group(dataset, entity_cls(config["entity_group"]))
        if (attr := config["attribute"]) != "id":
            spec = schema.get_spec(attr, default_data_type=DataType(int))
            entity_group.register_attribute(spec, flags=flag)
        return entity_group

    def initialize(self, **_):
        if (attr := self.config["evacuation_points"]["attribute"]) != "id":
            labels = self.evac_points.get_attribute(attr).array
        else:
            labels = self.evac_points.index.ids
        self.create_label_mapping(self.evac_points.road_ids.csr, labels)

    def update(self, **_):
        target = self.roads.get_attribute(self.config["road_segments"]["attribute"])
        target_special_value = target.options.special
        if target_special_value is None:
            target_special_value = DEFAULT_SPECIAL_VALUE

        changed: np.ndarray = self.roads.last_id.changed
        if np.all(~changed):
            changed = np.full_like(self.roads.last_id, fill_value=True, dtype=bool)

        is_special = changed & self.roads.last_id.is_special()
        is_valid = changed & ~is_special & ~self.roads.last_id.is_undefined()

        last_ids = self.roads.last_id.array
        if np.any(is_valid):
            mapping_func = np.vectorize(lambda i: self.label_mapping[i])
            target[is_valid] = mapping_func(last_ids[is_valid])
        target[is_special] = target.options.special

    def create_label_mapping(
        self, road_ids: TrackedCSRArray, labels: np.ndarray
    ) -> t.Dict[int, int]:
        self.label_mapping = {}
        for idx, label in enumerate(labels):
            roads = road_ids.get_row(idx)
            for road in roads:
                self.label_mapping[road] = label

    @classmethod
    def get_schema_attributes(cls):
        return [Evacuation_LastId, Evacuation_RoadIds, Evacuation_EvacuationPointId]
