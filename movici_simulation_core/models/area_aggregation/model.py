import typing as t

import numpy as np

from movici_geo_query.geo_query import GeoQuery, QueryResult
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType, AttributeSpec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import PUB, INIT
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.entities import PolygonEntity, GeometryEntity, LineEntity
from movici_simulation_core.models.common.model_util import try_get_geometry_type
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.utils.moment import Moment
from .aggregators import functions, AttributeAggregator


class Model(TrackedModel, name="area_aggregation"):
    """Implementation of the area aggregation model"""

    output_interval: t.Optional[int]
    aggregators: t.List[AttributeAggregator]
    target_entity: t.Optional[t.Union[PolygonEntity, EntityGroup]]
    src_entities: t.List[t.Union[GeometryEntity, EntityGroup]]
    previous_timestamp: t.Optional[Moment]

    def __init__(self, config):
        super().__init__(config)
        self.aggregators = []
        self.target_entity = None
        self.src_entities = []
        self.output_interval = None
        self.previous_timestamp = None

    def setup(self, state: TrackedState, schema, **_):
        config = self.config
        self.check_input_lengths(config=config)
        self.parse_config(state, config, schema)

    def parse_config(self, state: TrackedState, config: t.Dict, schema: AttributeSchema):
        self.output_interval = config.get("output_interval")
        self.add_aggregators(
            state=state,
            source_geometries=config["source_geometry_types"],
            source_entities=config["source_entity_groups"],
            source_attrs=config["source_properties"],
            funcs=config["aggregation_functions"],
            target_entity=config["target_entity_group"],
            target_attrs=config["target_properties"],
            schema=schema,
        )

    def add_aggregators(
        self,
        state: TrackedState,
        source_geometries,
        source_entities,
        source_attrs,
        funcs,
        target_entity,
        target_attrs,
        schema: AttributeSchema,
    ):
        target_ds_name, target_entity_name = target_entity[0]
        self.target_entity = state.register_entity_group(
            dataset_name=target_ds_name, entity=PolygonEntity(name=target_entity_name)
        )

        for geom, src_entity, src_attr, func, target_attr in zip(
            source_geometries, source_entities, source_attrs, funcs, target_attrs
        ):
            src_ds_name, src_entity_name = src_entity
            self.src_entities.append(
                state.register_entity_group(
                    dataset_name=src_ds_name,
                    entity=try_get_geometry_type(geom)(name=src_entity_name),
                )
            )

            target_spec = schema.get_spec(target_attr, DataType(float))
            self.ensure_uniform_attribute(target_ds_name, target_entity_name, target_spec)
            target_prop = state.register_attribute(
                dataset_name=target_ds_name,
                entity_name=target_entity_name,
                spec=target_spec,
                flags=PUB,
            )

            src_spec = schema.get_spec(src_attr, DataType(float))
            self.ensure_uniform_attribute(target_ds_name, target_entity_name, src_spec)
            src_prop = state.register_attribute(
                dataset_name=src_ds_name, entity_name=src_entity_name, spec=src_spec, flags=INIT
            )

            ensure_function(func)
            aggregator = AttributeAggregator(source=src_prop, target=target_prop, func=func)
            self.aggregators.append(aggregator)

    @staticmethod
    def ensure_uniform_attribute(ds, entity, spec: AttributeSpec):
        if spec.data_type.py_type == str:
            raise ValueError(
                f"Can't aggregate attribute {ds}/{entity}/{spec.name} " f"as it has string type"
            )
        if spec.data_type.csr is True:
            raise ValueError(
                f"attribute {ds}/{entity}/{spec.name} in the aggregator "
                f"should be of uniform data type"
            )
        if len(spec.data_type.unit_shape):
            raise ValueError(
                f"attribute {ds}/{entity}/{spec.name} in the aggregator "
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
                entity.ensure_ready()

    def resolve_mapping(self):
        mappings = {}
        weights = {}

        target_polygons = self.target_entity.get_geometry()
        for src_entity in self.src_entities:
            # This works as the hash for an EntityGroup is customized
            if src_entity in mappings:
                continue
            mapping = GeoQuery(src_entity.get_geometry()).intersects_with(target_polygons)
            mappings[src_entity] = mapping

            weights[src_entity] = self.calculate_weights(mapping, len(src_entity))

        for aggregator, src_entity in zip(self.aggregators, self.src_entities):
            aggregator.add_mapping(mappings[src_entity])
            aggregator.set_weights(weights[src_entity])

    @staticmethod
    def calculate_weights(mapping: QueryResult, length: int):
        indices, counts = np.unique(mapping.indices, return_counts=True)
        rv = np.zeros((length,), dtype=float)
        rv[indices] = 1.0 / counts
        return rv

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        dt = 0
        if self.previous_timestamp:
            dt = moment.seconds - self.previous_timestamp.seconds

        for aggregator in self.aggregators:
            aggregator.calculate(dt)

        self.previous_timestamp = moment

        if self.output_interval:
            return self.get_next_update_moment(moment)

    def get_next_update_moment(self, moment: Moment) -> Moment:
        next_time = Moment.from_seconds(moment.seconds + self.output_interval)
        # prevent infinite looping
        if next_time == moment:
            next_time = Moment(moment.timestamp + 1)

        return next_time

    @classmethod
    def install(cls, sim: Simulation):
        sim.register_model_type("area_aggregation", cls)


def ensure_function(func):
    if func not in functions:
        raise ValueError(f"models function must be one of {[k for k in functions.keys()]}")
