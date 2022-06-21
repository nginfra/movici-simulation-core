from __future__ import annotations

import dataclasses
import functools
import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import (
    INIT,
    PUB,
    REQUIRED,
    SUB,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.common.network import Network, NetworkEntities
from movici_simulation_core.validate import ensure_valid_config


class ShortestPathModel(TrackedModel, name="shortest_path"):
    cost_factor: UniformAttribute
    entity_groups: NetworkEntities
    network: t.Optional[Network] = None
    calculators: t.List[NetworkCalculator]
    no_update_shortest_path: bool = False

    def __init__(self, model_config):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        dataset, segments = self.config["transport_segments"]
        self.entity_groups = Network.register_required_attributes(
            state=state, dataset_name=dataset, transport_segments_name=segments
        )

        self.cost_factor = self.entity_groups["transport_links"].register_attribute(
            schema.get_spec(self.config["cost_factor"], default_data_type=float), flags=INIT
        )
        self.no_update_shortest_path = self.config.get("no_update_shortest_path", False)
        self.setup_calculators(schema)

    def setup_calculators(self, schema: AttributeSchema):
        self.calculators = []
        for conf in self.config["calculations"]:
            try:
                calc_type = conf.get("type")
                calc_class = CALCULATORS[calc_type]
            except KeyError:
                raise ValueError(f"Unknown network calculation type '{calc_type}'") from None

            input_attr = self.entity_groups["transport_links"].register_attribute(
                schema.get_spec(conf["input"], default_data_type=DataType(float)),
                flags=SUB,
            )
            if entity_resolver := self.single_source_entity_resolver(
                conf.get("single_source_entity_id"), conf.get("single_source_entity_reference")
            ):
                output_dtype = DataType(float, csr=False)
                if conf.get("singleSourceEntityReference") is not None:
                    self.entity_groups["virtual_nodes"].reference.flags |= REQUIRED
            else:
                output_dtype = DataType(float, csr=True)
            output_attr = self.entity_groups["virtual_nodes"].register_attribute(
                schema.get_spec(conf["output"], default_data_type=output_dtype),
                flags=PUB,
            )
            self.calculators.append(
                calc_class(
                    input_attribute=input_attr,
                    output_attribute=output_attr,
                    single_source_entity_resolver=entity_resolver,
                )
            )

    def initialize(self, **_):
        self.network = Network(**self.entity_groups, cost_factor=self.cost_factor.array)
        for calculator in self.calculators:
            calculator.initialize(self.network)

    def update(self, **_) -> t.Optional[Moment]:

        if self.no_update_shortest_path:
            weights = self.cost_factor.array
        else:
            self.network.update_cost_factor(self.cost_factor.array)
            weights = None

        for calculator in self.calculators:
            calculator.update(weights)

    def single_source_entity_resolver(
        self, entity_id: t.Optional[int], entity_ref: t.Optional[str]
    ):
        if entity_id is None and entity_ref is None:
            return None

        if entity_id is not None and entity_ref is not None:
            raise ValueError(
                "supply only one of 'single_source_entity_id' or 'single_source_entity_reference',"
                " not both"
            )
        if entity_id is not None:
            return functools.partial(self.resolve_entity_by_id, entity_id)
        return functools.partial(self.resolve_entity_by_ref, entity_ref)

    def resolve_entity_by_id(self, entity_id: int) -> int:
        nodes = self.entity_groups["virtual_nodes"]
        idx = nodes.index[entity_id]
        if idx == -1:
            raise ValueError(f"Entity id {entity_id} not found in {nodes.__entity_name__}")
        return entity_id

    def resolve_entity_by_ref(self, ref: str) -> int:
        nodes = self.entity_groups["virtual_nodes"]
        all_refs = nodes.reference.array
        idx = np.flatnonzero(all_refs == ref)
        if len(idx) == 0:
            raise ValueError(f"reference {ref} not found in {nodes.__entity_name__}")
        if len(idx) > 1:
            raise ValueError(f"Duplicated refencence {ref} found in {nodes.__entity_name__}")
        return nodes.index.ids[idx[0]]


@dataclasses.dataclass
class NetworkCalculator:
    input_attribute: UniformAttribute
    output_attribute: t.Union[CSRAttribute, UniformAttribute]
    single_source_entity_resolver: t.Optional[t.Callable[[], int]] = None
    network: t.Optional[Network] = None
    source_entity: t.Optional[int] = dataclasses.field(init=False, default=None)
    no_path_found: t.Optional[int] = dataclasses.field(init=False, default=None)

    def initialize(self, network: Network):
        self.network = network
        if self.single_source_entity_resolver is not None:
            self.source_entity = self.single_source_entity_resolver()
        self.no_path_found = self.output_attribute.options.special
        if self.no_path_found is None:
            self.no_path_found = -1

    def update(self, weights=None):
        raise NotImplementedError


class SumCalculator(NetworkCalculator):
    def update(self, weights=None):
        if self.source_entity is None:
            return self.update_for_all_sources()
        return self.update_for_single_source()

    def update_for_single_source(self):
        result = self.network.shortest_path_sum(
            self.source_entity, self.input_attribute.array, no_path_found=self.no_path_found
        )
        self.output_attribute.array[:] = result

    def update_for_all_sources(self):
        result = self.network.all_shortest_paths_sum(
            self.input_attribute.array, no_path_found=self.no_path_found
        )
        self.output_attribute.csr.update_from_matrix(result)


class WeightedAverageCalculator(NetworkCalculator):
    def update(self, weights=None):
        if self.source_entity is None:
            return self.update_for_all_sources(weights)
        return self.update_for_single_source(weights)

    def update_for_single_source(self, weights):
        result = self.network.shortest_path_weighted_average(
            source_node_id=self.source_entity,
            values=self.input_attribute.array,
            weights=weights,
            no_path_found=self.no_path_found,
        )
        self.output_attribute.array[:] = result

    def update_for_all_sources(self, weights):
        result = self.network.all_shortest_paths_weighted_average(
            self.input_attribute.array, weights=weights, no_path_found=self.no_path_found
        )
        self.output_attribute.csr.update_from_matrix(result)


CALCULATORS: t.Dict[str, t.Type[NetworkCalculator]] = {
    "sum": SumCalculator,
    "weighted_average": WeightedAverageCalculator,
}

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/shortest_path.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/shortest_path.json"


def convert_v1_v2(config):
    return {
        **config,
        "cost_factor": config["cost_factor"][1],
        "transport_segments": config["transport_segments"][0],
        "calculations": [
            {
                **calc,
                "input": calc["input"][1],
                "output": calc["output"][1],
            }
            for calc in config["calculations"]
        ],
    }
