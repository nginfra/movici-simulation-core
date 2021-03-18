import typing as t

import numpy as np
from model_engine import TimeStamp
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import PUB, SUB, PropertySpec
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from spatial_mapper.mapper import Mapper, Mapping

from .aggregators import functions, PropertyAggregator
from .entities import (
    PolygonEntity,
    supported_geometry_types,
    GeometryEntity,
    LineEntity,
)


class Model(TrackedBaseModel):
    """
    Implementation of the area aggregation model
    """

    output_interval: t.Optional[int]
    aggregators: t.List[PropertyAggregator]
    target_entity: t.Optional[t.Union[PolygonEntity, EntityGroup]]
    src_entities: t.List[t.Union[GeometryEntity, EntityGroup]]
    previous_timestamp: t.Optional[TimeStamp]

    def __init__(self):
        self.aggregators = []
        self.target_entity = None
        self.src_entities = []
        self.output_interval = None
        self.previous_timestamp = None

    def setup(self, state: TrackedState, config: dict, **_):
        self.check_input_lengths(config=config)
        self.parse_config(state, config)

    def parse_config(self, state: TrackedState, config: t.Dict):
        self.output_interval = config.get("output_interval")
        self.add_aggregators(
            state=state,
            source_geometries=config["source_geometry_types"],
            source_entities=config["source_entity_groups"],
            source_props=config["source_properties"],
            funcs=config["aggregation_functions"],
            target_entity=config["target_entity_group"],
            target_props=config["target_properties"],
        )

    def add_aggregators(
        self,
        state: TrackedState,
        source_geometries,
        source_entities,
        source_props,
        funcs,
        target_entity,
        target_props,
    ):
        target_ds_name, target_entity_name = target_entity[0]
        self.target_entity = state.register_entity_group(
            dataset_name=target_ds_name, entity=PolygonEntity(name=target_entity_name)
        )

        for geom, src_entity, src_prop, func, target_prop in zip(
            source_geometries, source_entities, source_props, funcs, target_props
        ):
            src_ds_name, src_entity_name = src_entity
            self.src_entities.append(
                state.register_entity_group(
                    dataset_name=src_ds_name,
                    entity=try_get_geometry_type(geom)(name=src_entity_name),
                )
            )

            target_spec = property_mapping[tuple(target_prop)]
            self.ensure_uniform_property(target_ds_name, target_entity_name, target_spec)
            target_prop = state.register_property(
                dataset_name=target_ds_name,
                entity_name=target_entity_name,
                spec=target_spec,
                flags=PUB,
            )

            src_spec = property_mapping[tuple(src_prop)]
            self.ensure_uniform_property(target_ds_name, target_entity_name, src_spec)
            src_prop = state.register_property(
                dataset_name=src_ds_name, entity_name=src_entity_name, spec=src_spec, flags=SUB
            )

            ensure_function(func)
            aggregator = PropertyAggregator(source=src_prop, target=target_prop, func=func)
            self.aggregators.append(aggregator)

    @staticmethod
    def ensure_uniform_property(ds, entity, spec: PropertySpec):
        if spec.data_type.py_type == str:
            raise ValueError(
                f"Can't aggregated property {ds}/{entity}/{spec.full_name} "
                f"as it has string type"
            )
        if spec.data_type.csr is True:
            raise ValueError(
                f"property {ds}/{entity}/{spec.full_name} in the aggregator "
                f"should be of uniform data type"
            )
        if len(spec.data_type.unit_shape):
            raise ValueError(
                f"property {ds}/{entity}/{spec.full_name} in the aggregator "
                f"should be one-dimensional"
            )

    @staticmethod
    def check_input_lengths(config):
        if len(config["target_entity_group"]) != 1 or len(config["target_entity_group"][0]) != 2:
            raise ValueError(
                "target_entity_group should have exactly 1 "
                "dataset_name and entity_group pair in a list"
            )
        keys = [
            "source_properties",
            "source_entity_groups",
            "target_properties",
            "source_geometry_types",
            "aggregation_functions",
        ]
        if any(len(config[key]) != len(config[keys[0]]) for key in keys[1:]):
            raise ValueError(
                "source_properties, source_entity_groups, target_properties, "
                "source_geometry_types, and aggregation_functions must have the same "
                "length in the model configuration"
            )

    def initialize(self, state: TrackedState):
        self.ensure_ready()
        self.resolve_mapping()

    def ensure_ready(self):
        for entity in self.src_entities:
            if isinstance(entity, LineEntity):
                if not (entity.line2d.is_initialized() or entity.line3d.is_initialized()):
                    raise NotReady

    def resolve_mapping(self):
        mappings = {}
        weights = {}

        target_polygons = self.target_entity.get_geometry()
        for src_entity in self.src_entities:
            if src_entity in mappings:
                continue
            mapping = Mapper(src_entity.get_geometry()).find_intersecting(target_polygons)
            mappings[src_entity] = mapping

            weights[src_entity] = self.calculate_weights(mapping, len(src_entity))

        for aggregator, src_entity in zip(self.aggregators, self.src_entities):
            aggregator.add_mapping(mappings[src_entity])
            aggregator.set_weights(weights[src_entity])

    @staticmethod
    def calculate_weights(mapping: Mapping, length: int):
        indices, counts = np.unique(mapping.seq, return_counts=True)
        rv = np.zeros((length,), dtype=float)
        rv[indices] = 1.0 / counts
        return rv

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        dt = 0
        if self.previous_timestamp:
            dt = time_stamp.seconds - self.previous_timestamp.seconds

        for aggregator in self.aggregators:
            aggregator.calculate(dt)

        self.previous_timestamp = time_stamp

        if self.output_interval:
            return self.get_next_timestamp(time_stamp)

    def get_next_timestamp(self, time_stamp: TimeStamp) -> TimeStamp:
        next_time = TimeStamp(seconds=(time_stamp.seconds + self.output_interval))
        # prevent infinite looping
        if next_time == time_stamp:
            next_time = time_stamp + time_stamp.scale

        return next_time


def try_get_geometry_type(geometry_type):
    try:
        return supported_geometry_types[geometry_type]
    except KeyError:
        raise ValueError(
            f"models geometry_type must be one of {[k for k in supported_geometry_types.keys()]}"
        )


def ensure_function(func):
    if func not in functions:
        raise ValueError(f"models function must be one of {[k for k in functions.keys()]}")
