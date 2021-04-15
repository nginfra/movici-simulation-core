import typing as t

from model_engine import TimeStamp, Config, DataFetcher
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.models.common import model_util
from movici_simulation_core.models.common.entities import PointEntity
from .corridor import Corridor
from .entities import (
    CorridorEntity,
    TransportSegmentEntity,
    LinkEntity,
)


class Model(TrackedBaseModel):
    """
    Implementation of the corridor model
    """

    def __init__(self):
        super(Model, self).__init__()
        self.corridor: t.Optional[Corridor] = None

    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
    ):
        corridor_entity = state.register_entity_group(
            dataset_name=config["corridors"][0], entity=CorridorEntity
        )

        transport_type = model_util.get_transport_type(config)
        transport_dataset_name = config[transport_type][0]

        transport_segments = state.register_entity_group(
            transport_dataset_name,
            TransportSegmentEntity(name=model_util.dataset_to_segments[transport_type]),
        )

        transport_nodes = state.register_entity_group(
            transport_dataset_name, PointEntity(name="transport_node_entities")
        )

        demand_nodes = state.register_entity_group(
            transport_dataset_name, PointEntity(name="virtual_node_entities")
        )

        demand_links = state.register_entity_group(
            transport_dataset_name, LinkEntity(name="virtual_link_entities")
        )

        self.corridor = Corridor(
            corridor_entity=corridor_entity,
            transport_segments=transport_segments,
            transport_nodes=transport_nodes,
            demand_nodes=demand_nodes,
            demand_links=demand_links,
            temp_dir=scenario_config.TEMP_DIR,
        )

    def initialize(self, state: TrackedState):
        if not self.corridor.is_ready():
            raise NotReady
        self.corridor.calculate_routes()

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        self.corridor.update()
        return None

    def shutdown(self):
        if self.corridor:
            self.corridor.shutdown()
