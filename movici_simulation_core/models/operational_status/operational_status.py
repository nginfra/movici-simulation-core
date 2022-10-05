from __future__ import annotations

import typing as t

import numpy as np
from movici_geo_query import GeoQuery, PointGeometry, QueryResult
from movici_geo_query.geometry import Geometry

from movici_simulation_core import (
    PUB,
    SUB,
    AttributeSpec,
    TrackedModel,
    TrackedState,
    UniformAttribute,
)
from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.csr import row_wise_max
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.common.entity_groups import (
    GeometryEntity,
    GridCellEntity,
    LineEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.models.common.model_util import try_get_geometry_type
from movici_simulation_core.validate import ensure_valid_config

Flooding_WaterHeight = AttributeSpec("flooding.water_height", float)
Flooding_WaterDepth = AttributeSpec("flooding.water_depth", float)

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/operational_status.json"


class OperationalStatus(TrackedModel, name="operational_status"):
    def __init__(self, model_config: dict):
        model_config = ensure_valid_config(
            model_config,
            "1",
            {
                "1": {
                    "schema": MODEL_CONFIG_SCHEMA_PATH,
                },
            },
        )
        super().__init__(model_config)
        self.modules: t.List[StatusModule] = []

    def setup(self, state: TrackedState, **_):
        dataset, entity_group = self.config["entity_group"]
        entity_cls = try_get_geometry_type(self.config["geometry"])
        target = state.register_entity_group(dataset, entity_cls(entity_group))
        for key, cls in ALL_MODULES.items():
            if key in self.config:
                self.modules.append(cls.from_config(self.config[key], target, state))

    def initialize(self, **_):
        for module in self.modules:
            module.initialize()

    def update(self, **_):
        for module in self.modules:
            module.update()

    @classmethod
    def get_schema_attributes(cls):
        return [Flooding_WaterHeight, Flooding_WaterDepth]


class StatusModule:
    def initialize(self):
        pass

    def update(self):
        pass

    @classmethod
    def from_config(
        module_config: dict, target: GeometryEntity, state: TrackedState
    ) -> StatusModule:
        raise NotImplementedError


class FloodingStatusModule(StatusModule):
    mapping: t.Optional[QueryResult] = None
    elevation: t.Union[np.ndarray, TrackedCSRArray, None] = None
    row_ptr: t.Optional[np.ndarray] = None

    def __init__(
        self,
        cells: GridCellEntity,
        water_height: UniformAttribute,
        target: GeometryEntity,
        water_depth: UniformAttribute,
    ) -> None:
        self.cells = cells
        self.water_height = water_height
        self.target = target
        self.water_depth = water_depth

    def initialize(self):
        self.cells.ensure_ready()

        geometry: Geometry = self.target.get_geometry()
        self.mapping = GeoQuery(self.cells.get_geometry()).overlaps_with(
            PointGeometry(geometry.points)
        )
        self.row_ptr = geometry.row_ptr
        self.elevation = get_elevation(self.target)

    @classmethod
    def from_config(
        cls, module_config: dict, target: GeometryEntity, state: TrackedState
    ) -> FloodingStatusModule:
        cell_dataset, cell_entity_group = module_config["flooding_cells"]
        point_dataset, point_entity_group = module_config["flooding_points"]
        if cell_dataset != point_dataset:
            raise ValueError(
                "Flooding grid points must reside in the same dataset as the flooding cells"
            )

        cells = state.register_entity_group(cell_dataset, GridCellEntity(cell_entity_group))
        cells.set_points(
            state.register_entity_group(point_dataset, PointEntity(point_entity_group))
        )
        water_height = cells.register_attribute(Flooding_WaterHeight, SUB)
        water_depth = target.register_attribute(Flooding_WaterDepth, PUB)

        # TODO: read threshold from config to publish status
        return FloodingStatusModule(cells, water_height, target, water_depth)

    def update(self):
        wh = self.water_height[self.mapping.indices]
        max_wh = row_wise_max(
            wh, self.mapping.row_ptr, empty_row=self.water_height.options.special or -9999
        )
        wd = np.maximum(max_wh - self.elevation, 0)

        if self.row_ptr is not None:
            wd = row_wise_max(wd, self.row_ptr, empty_row=0)

        self.water_depth[:] = wd


ALL_MODULES = {"flooding": FloodingStatusModule}


def get_elevation(entity_group: t.Union[PointEntity, LineEntity, PolygonEntity]) -> np.ndarray:
    if entity_group.dimensions() != 3:
        raise ValueError(
            f"Entity group {entity_group.dataset_name}/{entity_group.__entity_name__} "
            "must have 3 dimensions in order to calculate flooding status"
        )
    if isinstance(entity_group, PointEntity):
        return entity_group.z.array
    if isinstance(entity_group, LineEntity):
        return entity_group.linestring.csr.data[:, 2]
    if isinstance(entity_group, PolygonEntity):
        return entity_group.polygon.csr.data[:, 2]
    raise ValueError(f"Unsupported entity group of type {type(entity_group).__name__}")
