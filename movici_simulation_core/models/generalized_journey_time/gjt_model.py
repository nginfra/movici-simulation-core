from __future__ import annotations

import logging
import typing as t

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec, DataType
from movici_simulation_core.data_tracker.attribute import (
    PUB,
    SUB,
    CSRAttribute,
    UniformAttribute,
    field,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.attributes import (
    Transport_Capacity_Hours,
    Transport_MaxSpeed,
    Transport_PassengerVehicleFrequency,
    Transport_PassengerVehicleCapacity,
)
from movici_simulation_core.models.common.entities import (
    PointEntity,
    TransportSegmentEntity,
    VirtualLinkEntity,
)
from movici_simulation_core.models.common.model_util import safe_divide
from movici_simulation_core.models.common.network import Network, NetworkEntities
from movici_simulation_core.utils.moment import Moment
import numpy as np

from .crowdedness import crowdedness

Transport_PassengerFlow = AttributeSpec("transport.passenger_flow", data_type=float)

Transport_GeneralizedJourneyTime = AttributeSpec(
    "transport.generalized_journey_time", data_type=DataType(float, csr=True)
)

DEFAULT_TRAVEL_TIME_ATTRIBUTE = (None, "transport.passenger_average_time")
DEFAULT_DATA_TYPE = DataType(float)


class GJTVirtualLinkEntity(VirtualLinkEntity, name="virtual_link_entities"):
    max_speed = field(Transport_MaxSpeed, flags=0)
    capacity = field(Transport_Capacity_Hours, flags=0)


class TrackDemandNodeEntity(PointEntity, name="virtual_node_entities"):
    frequency = field(Transport_PassengerVehicleFrequency, flags=SUB)
    train_capacity = field(Transport_PassengerVehicleCapacity, flags=SUB)
    gjt = field(Transport_GeneralizedJourneyTime, flags=PUB)


class GJTTrackSegmentEntity(TransportSegmentEntity):
    _max_speed = field(Transport_MaxSpeed, flags=0)
    capacity = field(Transport_Capacity_Hours, flags=0)


class GJTModel(TrackedModel, name="generalized_journey_time"):
    _transport_nodes: t.Optional[PointEntity] = None
    _transport_segments: t.Optional[TransportSegmentEntity] = None
    _demand_nodes: t.Optional[TrackDemandNodeEntity] = None
    _demand_links: t.Optional[VirtualLinkEntity] = None
    _logger: t.Optional[logging.Logger] = None
    _calculator: GJTCalculator = None
    _travel_time: t.Optional[UniformAttribute]
    _passenger_flow: t.Optional[UniformAttribute]
    _network_entities: NetworkEntities

    def setup(self, state: TrackedState, schema: AttributeSchema, logger: logging.Logger, **_):
        self._logger = logger
        ds_name, segments = self.config["transport_segments"][0]
        travel_time_attr = self.config.get("travel_time", DEFAULT_TRAVEL_TIME_ATTRIBUTE)
        self._network_entities = Network.register_required_attributes(
            state,
            dataset_name=ds_name,
            transport_segments_name=segments,
            entities={
                "transport_links": GJTTrackSegmentEntity,
                "virtual_nodes": TrackDemandNodeEntity,
                "virtual_links": GJTVirtualLinkEntity,
            },
        )

        self._travel_time = state.register_attribute(
            ds_name, segments, schema.get_spec(travel_time_attr, DEFAULT_DATA_TYPE), flags=SUB
        )
        self._passenger_flow = state.register_attribute(
            ds_name, segments, Transport_PassengerFlow, flags=SUB
        )

    def initialize(self, **_):
        self._network_entities["transport_links"].ensure_ready()

        network = Network(**self._network_entities)
        self._calculator = GJTCalculator(
            network=network,
            travel_time=self._travel_time,
            passenger_flow=self._passenger_flow,
            frequency=self._network_entities["virtual_nodes"].frequency,
            train_capacity=self._network_entities["virtual_nodes"].train_capacity,
            logger=self._logger,
        )

    def update(self, **_) -> t.Optional[Moment]:
        self._calculator.update_travel_time()
        gjt = self._calculator.gjt()
        self._network_entities["virtual_nodes"].gjt.csr.update_from_matrix(gjt)

    @staticmethod
    def get_schema_attributes() -> t.List[AttributeSpec]:
        return [
            Transport_PassengerFlow,
            Transport_PassengerVehicleFrequency,
            Transport_PassengerVehicleCapacity,
            Transport_GeneralizedJourneyTime,
        ]


class GJTCalculator:
    r"""Calculates the generalized journey time (GJT) for railway traffic demand. GJT is the
    perceived travel time for passengers that is composed of the in-train-time, the average
    waiting time and penalties for traveling in crowded trains and the fact that waiting time
    "counts more" than in-vehicle time. The formula for calculating GJT is as following

    .. math:: GJT = w \cdot TT + \frac{f}{2 \cdot freq}

    where `w` is a crowdedness factor, `TT` is the in-vehicle travel time, f is a penalty factor
    for average waiting time and `freq` is the train frequency.

    This class reads the passenger flow of every track segment, and for every OD-pair
    calculates:

        * The travel-time weighted average passenger flow based on the shortest path between O
            and D
        * The capacity of the OD route based on a general train frequency on the OD-route
        * The corresponding w of the OD-route
        * The travel time based on the shortest path calculation
        * factor f (possibly as a function of travel time)
        * GJT based on the above

    """

    def __init__(
        self,
        network: Network,
        travel_time: UniformAttribute,
        passenger_flow: UniformAttribute,
        frequency: CSRAttribute,
        train_capacity: UniformAttribute,
        logger: logging.Logger = None,
    ) -> None:
        self.network = network
        self.logger = logger
        self.travel_time = travel_time
        self.passenger_flow = passenger_flow
        self.frequency = frequency
        self.train_capacity = train_capacity

    def update_travel_time(self):
        self.network.update_cost_factor(self.travel_time.array)

    def gjt(self):
        crowdedness = self.crowdedness()
        travel_time = self.network.all_shortest_paths()
        f = 1.5
        freq = self.frequency.csr.as_matrix()
        return crowdedness * travel_time + safe_divide(f, (2 * freq), fill_value=np.inf)

    def crowdedness(self):
        avg_passenger_flow = self.average_passenger_flow()
        capacity = self.frequency.csr.as_matrix() * self.train_capacity.array

        load_factor = safe_divide(avg_passenger_flow, capacity, fill_value=-1)
        return crowdedness(load_factor)

    def average_passenger_flow(self):
        ids = self.network.virtual_node_ids

        avg_passenger_flow = self.network.all_shortest_paths_weighted_average(
            values=self.passenger_flow, no_path_found=-1
        )
        if self.logger:
            for (x, y) in zip(*np.where(avg_passenger_flow == np.inf)):
                if x == y:
                    pass
                self.logger.debug(
                    f"Nodes {ids[x]}-{ids[y]} do not have a valid path between them."
                )

        return avg_passenger_flow
