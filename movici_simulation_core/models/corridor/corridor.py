import typing as t

from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.property import get_undefined_array, DataType
from movici_simulation_core.models.common.entities import PointEntity
from .entities import CorridorEntity, TransportSegmentEntity, LinkEntity


class Corridor:
    def __init__(
        self,
        corridor_entity: CorridorEntity,
        transport_segments: TransportSegmentEntity,
        transport_nodes: PointEntity,
        demand_nodes: PointEntity,
        demand_links: LinkEntity,
        temp_dir: str,
    ) -> None:
        self._corridors = corridor_entity
        self._transport_segments = transport_segments
        self._transport_nodes = transport_nodes
        self._demand_nodes = demand_nodes
        self._demand_links = demand_links
        self._project: ProjectWrapper = ProjectWrapper(temp_dir, remove_existing=True)
        self._connections: t.Optional[TrackedCSRArray] = None

    def is_ready(self) -> bool:
        return self._transport_segments.is_ready()

    def update(self):
        self._update_corridors()

    def calculate_routes(self) -> None:
        self._connections: TrackedCSRArray = get_undefined_array(
            DataType(float, (), True), length=len(self._corridors)
        )
        ...
        # self._connections[:] = route_indices
        # self._corridors.line2d[:] = routes

    def _update_corridors(self):
        ...

    def shutdown(self):
        if self._project:
            self._project.close()
            self._project = None
