import typing as t

import numpy as np
from movici_geo_query.geo_query import GeoQuery, QueryResult

from movici_simulation_core import (
    INIT,
    PUB,
    AttributeSchema,
    AttributeSpec,
    DataType,
    EntityGroup,
    Moment,
    Simulation,
    TrackedModel,
    TrackedState,
)

from ...json_schemas import SCHEMA_PATH
from ...models.common import try_get_geometry_type
from ...models.common.entity_groups import GeometryEntity, LineEntity, PolygonEntity
from ...validate import ensure_valid_config
from .aggregators import AttributeAggregator, functions


class AggregatorConfig(t.TypedDict):
    source_entity_group: t.Tuple[str, str]
    source_attribute: str
    target_attribute: str
    function: str
    source_geometry: str


class Model(TrackedModel, name="area_aggregation"):
    """Implementation of the area aggregation model"""

    output_interval: t.Optional[int]
    aggregators: t.List[AttributeAggregator]
    target_entity: t.Optional[t.Union[PolygonEntity, EntityGroup]]
    src_entities: t.List[t.Union[GeometryEntity, EntityGroup]]
    previous_timestamp: t.Optional[Moment]

    def __init__(self, config):
        config = ensure_valid_config(
            config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(config)
        self.aggregators = []
        self.target_entity = None
        self.src_entities = []
        self.output_interval = None
        self.previous_timestamp = None

    def setup(self, state: TrackedState, schema, **_):
        config = self.config
        self.parse_config(state, config, schema)

    def parse_config(self, state: TrackedState, config: t.Dict, schema: AttributeSchema):
        self.output_interval = config.get("output_interval")
        self.add_aggregators(
            state=state,
            target_entity=config["target_entity_group"],
            aggregators=config["aggregations"],
            schema=schema,
        )

    def add_aggregators(
        self,
        state: TrackedState,
        target_entity,
        aggregators: t.List[AggregatorConfig],
        schema: AttributeSchema,
    ):
        target_ds_name, target_entity_name = target_entity
        self.target_entity = state.register_entity_group(
            dataset_name=target_ds_name, entity=PolygonEntity(name=target_entity_name)
        )

        for agg in aggregators:
            src_ds_name, src_entity_name = agg["source_entity_group"]
            self.src_entities.append(
                state.register_entity_group(
                    dataset_name=src_ds_name,
                    entity=try_get_geometry_type(agg["source_geometry"])(name=src_entity_name),
                )
            )

            target_spec = schema.get_spec(agg["target_attribute"], DataType(float))
            self.ensure_uniform_attribute(target_ds_name, target_entity_name, target_spec)
            target_prop = state.register_attribute(
                dataset_name=target_ds_name,
                entity_name=target_entity_name,
                spec=target_spec,
                flags=PUB,
            )

            src_spec = schema.get_spec(agg["source_attribute"], DataType(float))
            self.ensure_uniform_attribute(target_ds_name, target_entity_name, src_spec)
            src_prop = state.register_attribute(
                dataset_name=src_ds_name, entity_name=src_entity_name, spec=src_spec, flags=INIT
            )

            func = ensure_function(agg["function"])
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
    return func


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/area_aggregation.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/area_aggregation.json"


def convert_v1_v2(config):
    rv = {
        "target_entity_group": config["target_entity_group"][0],
        "aggregations": [
            {
                "source_entity_group": config["source_entity_groups"][i],
                "source_attribute": config["source_properties"][i][1],
                "target_attribute": config["target_properties"][i][1],
                "function": config["aggregation_functions"][i],
                "source_geometry": config["source_geometry_types"][i],
            }
            for i in range(len(config["source_entity_groups"]))
        ],
    }
    if "output_interval" in config:
        rv["output_interval"] = config["output_interval"]

    return rv
