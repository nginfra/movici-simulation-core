from __future__ import annotations

import functools
import typing as t
from dataclasses import dataclass, field

import numpy as np
from movici_geo_query import GeoQuery, QueryResult

from movici_simulation_core import TrackedState
from movici_simulation_core.core.attribute import PUB, SUB, AttributeObject, get_undefined_array
from movici_simulation_core.core.data_type import DataType
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.csr import row_wise_max, row_wise_min, row_wise_sum
from movici_simulation_core.models.common.entity_groups import (
    GeometryEntity,
    GridCellEntity,
    LineEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.models.generic_model.common import ValidationError
from movici_simulation_core.models.udf_model.compiler import compile


def non_data_field(value, **kwargs):
    default_kwargs = dict(init=False, repr=False, compare=False, hash=False)
    return field(default=value, **{**default_kwargs, **kwargs})


class Block:
    is_updated: bool = False
    is_initialized: bool = False
    is_setup: bool = False

    def setup(self, **kwargs):
        if self.is_setup:
            return
        for source in self.get_sources():
            source.setup(**kwargs)
        self.is_setup = True

    def initialize(self, **kwargs):
        if self.is_initialized:
            return
        for source in self.get_sources():
            source.initialize(**kwargs)
        self.is_initialized = True

    def update(self, **kwargs):
        if self.is_updated:
            return
        for source in self.get_sources():
            source.update(**kwargs)

        self.is_updated = True

    def reset(self):
        self.is_updated = False

    def get_sources(self) -> t.List[Block]:
        return []

    def validate(self):
        pass

    def __init_subclass__(cls) -> None:
        # TODO: maybe we want to refactor this to a class decorator
        #   that introduces a BlockWrapper class to handle this logic
        if callable(setup_func := cls.__dict__.get("setup")):

            def setup(self, **kwargs):
                if self.is_setup:
                    return
                Block.setup(self, **kwargs)
                setup_func(self, **kwargs)

            setup.__inner__ = setup_func
            cls.setup = setup

        if callable(initialize_func := cls.__dict__.get("initialize")):

            def initialize(self, **kwargs):
                if self.is_initialized:
                    return
                Block.initialize(self, **kwargs)
                initialize_func(self, **kwargs)

            initialize.__inner__ = initialize_func
            cls.initialize = initialize
        if callable(update_func := cls.__dict__.get("update")):

            def update(self, **kwargs):
                if self.is_updated:
                    return
                Block.update(self, **kwargs)
                update_func(self, **kwargs)

            update.__inner__ = update_func
            cls.update = update


class DataBlock(Block):
    entity_group: EntityGroupBlock
    data: np.ndarray


@dataclass(unsafe_hash=True)
class InputBlock(Block):
    entity_group: EntityGroupBlock
    attribute_name: str
    attribute_object: AttributeObject = non_data_field(None)

    def setup(self, state: TrackedState, schema: AttributeSchema = None, **_):
        schema = schema or state.schema
        self.attribute_object = self.entity_group.entity_group.register_attribute(
            spec=schema.get_spec(self.attribute_name, DataType(float)),
            flags=SUB,
        )

    @property
    def data(self):
        return self.attribute_object.array

    def get_sources(self) -> t.List[Block]:
        return [self.entity_group]


@dataclass(unsafe_hash=True)
class EntityGroupBlock(Block):
    dataset: str
    entity_name: str
    geometry: str
    grid_points: t.Optional[str] = None
    entity_group: GeometryEntity = non_data_field(None)
    _spatial_index: GeoQuery = non_data_field(None)

    @property
    def spatial_index(self):
        if self._spatial_index is None:
            self._spatial_index = GeoQuery(self.entity_group.get_geometry())
        return self._spatial_index

    def setup(self, state: TrackedState, **_):
        entity_type = {
            "point": PointEntity,
            "line": LineEntity,
            "polygon": PolygonEntity,
            "cell": GridCellEntity,
        }[self.geometry]

        self.entity_group = state.register_entity_group(
            self.dataset, entity_type(self.entity_name)
        )
        if isinstance(self.entity_group, GridCellEntity):
            points = state.register_entity_group(self.dataset, PointEntity(self.grid_points))
            self.entity_group.set_points(points)

    def validate(self):
        if self.geometry == "cell" and not self.grid_points:
            raise ValidationError("grid points are required for cell geometries")


@dataclass(unsafe_hash=True)
class GeoMapBlock(Block):
    source: EntityGroupBlock
    target: EntityGroupBlock
    function: str
    distance: t.Optional[str] = None
    mapping: QueryResult = non_data_field(None)

    def initialize(self, **_):
        index = self.source.spatial_index
        func = {
            "nearest": index.nearest_to,
            "intersect": index.intersects_with,
            "overlap": index.overlaps_with,
            "distance": functools.partial(index.within_distance_of, distance=self.distance),
        }[self.function]
        self.mapping = func(self.target.entity_group.get_geometry())

    def validate(self):
        if self.function == "distance" and not self.distance:
            raise ValidationError("A value for distance is required for 'distance' geomappings")

    def get_sources(self) -> t.List[Block]:
        return [self.source, self.target]


@dataclass(unsafe_hash=True)
class GeoReduceBlock(DataBlock):
    source: DataBlock
    target: GeoMapBlock
    function: str

    @property
    def entity_group(self):
        return self.target.target

    def initialize(self, **_):
        length = len(self.entity_group.entity_group.index)
        self.data = get_undefined_array(DataType(float), length, rtol=1e-5, atol=1e-8)

    def update(self, **kwargs):
        func = {
            "min": functools.partial(row_wise_min, empty_row=np.nan),
            "max": functools.partial(row_wise_max, empty_row=np.nan),
            "sum": row_wise_sum,
        }[self.function]
        mapping = self.target.mapping
        self.data[:] = func(data=self.source.data[mapping.indices], row_ptr=mapping.row_ptr)

    def get_sources(self) -> t.List[Block]:
        return [self.source, self.target]

    def validate(self):
        if self.source.entity_group != self.target.source:
            raise ValidationError(
                "Source data must come from the same entity group as the geomap's source"
            )


@dataclass(unsafe_hash=True)
class FunctionBlock(DataBlock):
    sources: t.Dict[str, DataBlock] = field(compare=False)
    expression: str
    function: callable = non_data_field(None, init=True)

    def __post_init__(self):
        if self.function is None:
            self.function = compile(self.expression)

    @property
    def entity_group(self):
        try:
            return next(iter(self.sources.values())).entity_group
        except StopIteration:
            return None

    def validate(self):
        if not self.sources:
            raise ValidationError("function requires at least one variable")
        if len(set(s.entity_group for s in self.sources.values())) > 1:
            raise ValidationError("all variables must belong to the same entity group")

    def initialize(self, **_):
        length = len(self.entity_group.entity_group.index)
        self.data = get_undefined_array(DataType(float), length, rtol=1e-5, atol=1e-8)

    def update(self, **kwargs):
        self.data = self.function({k: s.data for k, s in self.sources.items()})

    def get_sources(self) -> t.List[Block]:
        return list(self.sources.values())


@dataclass(unsafe_hash=True)
class OutputBlock(Block):
    source: DataBlock
    attribute_name: str
    attribute_object: AttributeObject = non_data_field(None)

    @property
    def entity_group(self):
        return self.source

    def setup(self, state: TrackedState, schema=None, **_):
        schema = schema or state.schema
        self.attribute_object = self.entity_group.entity_group.register_attribute(
            spec=schema.get_spec(self.attribute_name, DataType(float)),
            flags=PUB,
        )

    def get_sources(self) -> t.List[Block]:
        return [self.source]
