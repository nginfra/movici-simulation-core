from __future__ import annotations

import dataclasses
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.attribute import (
    INIT,
    PUB,
    SUB,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.network import Network, NetworkEntities
from movici_simulation_core.utils.moment import Moment


class ShortestPathModel(TrackedModel, name="shortest_path"):
    cost_factor: UniformAttribute
    entity_groups: NetworkEntities
    network: t.Optional[Network] = None
    calculators: t.List[NetworkCalculator]
    no_update_shortest_path: bool = False

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        dataset, segments = self.config["transport_segments"][0]
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
            output_attr = self.entity_groups["virtual_nodes"].register_attribute(
                schema.get_spec(conf["output"], default_data_type=DataType(float, csr=True)),
                flags=PUB,
            )
            self.calculators.append(
                calc_class(input_attribute=input_attr, output_attribute=output_attr)
            )

    def initialize(self, **_):
        self.network = Network(**self.entity_groups, cost_factor=self.cost_factor.array)
        for calculator in self.calculators:
            calculator.network = self.network

    def update(self, **_) -> t.Optional[Moment]:

        if self.no_update_shortest_path:
            weights = self.cost_factor.array
        else:
            self.network.update_cost_factor(self.cost_factor.array)
            weights = None

        for calculator in self.calculators:
            calculator.update(weights)


@dataclasses.dataclass
class NetworkCalculator:
    input_attribute: UniformAttribute
    output_attribute: CSRAttribute
    network: t.Optional[Network] = None

    def update(self, weights=None):
        raise NotImplementedError


class SumCalculator(NetworkCalculator):
    def update(self, weights=None):
        result = self.network.all_shortest_paths_sum(self.input_attribute.array)
        self.output_attribute.csr.update_from_matrix(result)


class WeightedAverageCalculator(NetworkCalculator):
    def update(self, weights=None):
        no_path_found = self.output_attribute.options.special
        result = self.network.all_shortest_paths_weighted_average(
            self.input_attribute.array, weights=weights, no_path_found=no_path_found
        )
        self.output_attribute.csr.update_from_matrix(result)


CALCULATORS: t.Dict[str, t.Type[NetworkCalculator]] = {
    "sum": SumCalculator,
    "weighted_average": WeightedAverageCalculator,
}
