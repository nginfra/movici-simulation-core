import typing as t
from dataclasses import dataclass

import numpy as np
from movici_geo_query.geo_query import GeoQuery
from shapely.ops import nearest_points

from movici_simulation_core.core.attribute import Attribute, UniformAttribute
from movici_simulation_core.models.common.entity_groups import GeometryEntity, LineEntity

from .dataset import OverlapEntity


@dataclass
class Connections:
    from_indices: np.ndarray
    to_indices: np.ndarray
    overlap_indices: np.ndarray
    overlap_published: np.ndarray


class OverlapStatus:
    default_display_name_template = (
        "Overlap from {from_dataset_name} reference {from_reference}"
        " to {to_dataset_name} reference {to_reference}"
    )

    def __init__(
        self,
        from_entity: GeometryEntity,
        from_check_attribute: Attribute,
        to_entities: t.List[GeometryEntity],
        to_check_attributes: t.List[Attribute],
        overlap_entity: OverlapEntity,
        distance_threshold: float,
        display_name_template: t.Optional[str],
    ) -> None:
        self._from_entity = from_entity
        self._from_check_attribute = from_check_attribute
        self._to_entities = to_entities
        self._to_check_attribute = to_check_attributes
        self._overlap_entity = overlap_entity
        self._distance_threshold = distance_threshold
        if display_name_template:
            self.display_name_template = display_name_template
        else:
            self.display_name_template = self.default_display_name_template

        self._connections: t.Optional[t.List[Connections]] = None
        self._next_overlap_index: int = 0

    def is_ready(self) -> bool:
        if isinstance(self._from_entity, LineEntity) and not self._from_entity.is_ready():
            return False

        for entity in self._to_entities:
            if isinstance(entity, LineEntity) and not entity.is_ready():
                return False

        if (
            "{to_reference}" in self.display_name_template
            or "{from_reference}" in self.display_name_template
        ):
            if not self._from_entity.reference.is_initialized():
                return False
            for entity in self._to_entities:
                if not entity.reference.is_initialized():
                    return False

        return True

    def update(self):
        self._publish_active_overlaps()

    def resolve_connections(self) -> None:
        from_geometry = self._from_entity.get_geometry()
        self._connections = []
        for to_entity in self._to_entities:
            mapper = GeoQuery(to_entity.get_geometry())
            mapping = mapper.within_distance_of(from_geometry, self._distance_threshold)

            from_indices = []
            to_indices = []

            for from_index, mapping_to_indices in enumerate(mapping.iterate()):
                from_indices += [from_index] * len(mapping_to_indices)
                to_indices += mapping_to_indices.tolist()

            self._connections.append(
                Connections(
                    from_indices=np.array(from_indices, dtype=np.int64),
                    to_indices=np.array(to_indices, dtype=np.int64),
                    overlap_indices=np.full_like(from_indices, -1, dtype=np.int64),
                    overlap_published=np.full_like(from_indices, False, dtype=bool),
                )
            )

    def _publish_connections(
        self,
        from_entity: GeometryEntity,
        to_entity: GeometryEntity,
        connections: Connections,
        overlap_active: np.ndarray,
        overlap_entity: OverlapEntity,
    ) -> None:

        new_overlaps = np.where(overlap_active)[0]
        if new_overlaps.size == 0:
            return

        new_overlap_indices = np.arange(
            self._next_overlap_index, self._next_overlap_index + len(new_overlaps)
        )

        if new_overlap_indices[-1] >= len(overlap_entity.connection_to_id):
            raise IndexError(
                f"Not enough overlap entities in {overlap_entity.state.dataset_name}"
                f" for this model."
            )

        from_indices = connections.from_indices[new_overlaps]
        from_ids = from_entity.index.ids[from_indices]
        from_reference = from_entity.reference.array[from_indices]

        to_indices = connections.to_indices[new_overlaps]
        to_ids = to_entity.index.ids[to_indices]
        to_reference = to_entity.reference.array[to_indices]

        display_name = self._generate_display_name(
            from_entity.state.dataset_name,
            from_reference,
            from_ids,
            to_entity.state.dataset_name,
            to_reference,
            to_ids,
            self.display_name_template,
        )

        overlap_entity.display_name[new_overlap_indices] = display_name
        overlap_entity.connection_from_reference[new_overlap_indices] = from_reference
        overlap_entity.connection_to_reference[new_overlap_indices] = to_reference
        overlap_entity.connection_from_dataset[
            new_overlap_indices
        ] = from_entity.state.dataset_name
        overlap_entity.connection_to_dataset[new_overlap_indices] = to_entity.state.dataset_name

        overlap_entity.connection_from_id[new_overlap_indices] = from_ids
        overlap_entity.connection_to_id[new_overlap_indices] = to_ids

        connections.overlap_published[new_overlaps] = True
        connections.overlap_indices[new_overlaps] = new_overlap_indices

        self._resolve_overlap_point(
            from_entity, to_entity, from_indices, to_indices, new_overlap_indices, overlap_entity
        )

        self._next_overlap_index += len(new_overlaps)

    def _resolve_overlap_point(
        self,
        from_entity: GeometryEntity,
        to_entity: GeometryEntity,
        from_indices: np.ndarray,
        to_indices: np.ndarray,
        overlap_indices: np.ndarray,
        overlap_entity: OverlapEntity,
    ):
        for from_index, to_index, overlap_index in zip(from_indices, to_indices, overlap_indices):
            x, y = self._calculate_overlap_point(
                from_entity,
                from_index,
                to_entity,
                to_index,
            )
            overlap_entity.x[overlap_index] = x
            overlap_entity.y[overlap_index] = y

    @classmethod
    def _calculate_overlap_point(
        cls,
        from_entity: GeometryEntity,
        from_index: int,
        to_entity: GeometryEntity,
        to_index: int,
    ) -> t.Tuple[float, float]:

        from_geometry = from_entity.get_single_geometry(from_index)
        to_geometry = to_entity.get_single_geometry(to_index)

        nearest_from, nearest_to = nearest_points(from_geometry, to_geometry)
        return (nearest_from.x + nearest_to.x) / 2, (nearest_from.y + nearest_to.y) / 2

    def _publish_active_overlaps(self):
        for to_attr, to_entity, connections in zip(
            self._to_check_attribute, self._to_entities, self._connections
        ):
            self._publish_active_overlaps_for_connection(
                from_entity=self._from_entity,
                from_check_attribute=self._from_check_attribute,
                to_entity=to_entity,
                to_check_attribute=to_attr,
                connections=connections,
                overlap_entity=self._overlap_entity,
            )

    def _publish_active_overlaps_for_connection(
        self,
        from_entity: GeometryEntity,
        from_check_attribute: t.Optional[Attribute],
        to_entity: GeometryEntity,
        to_check_attribute: t.Optional[Attribute],
        connections: Connections,
        overlap_entity: OverlapEntity,
    ) -> None:

        overlap_undefined_value = overlap_entity.overlap_active.data_type.undefined

        overlap_active = self._calculate_active_overlaps(
            from_active_status=from_check_attribute,
            connection_from_indices=connections.from_indices,
            to_active_status=to_check_attribute,
            connection_to_indices=connections.to_indices,
            undefined_value=overlap_undefined_value,
        )

        defined = overlap_active != overlap_undefined_value
        new_overlaps = np.logical_and(
            overlap_active, np.logical_not(connections.overlap_published)
        )[defined]

        self._publish_connections(
            from_entity,
            to_entity,
            connections,
            new_overlaps,
            overlap_entity,
        )

        published_overlap_indices = connections.overlap_indices[connections.overlap_published]
        self._overlap_entity.overlap_active[published_overlap_indices] = overlap_active[
            connections.overlap_published
        ]

    @staticmethod
    def _calculate_active_overlaps(
        from_active_status: t.Optional[UniformAttribute],
        connection_from_indices: np.ndarray,
        to_active_status: t.Optional[UniformAttribute],
        connection_to_indices: np.ndarray,
        undefined_value: int,
    ) -> np.ndarray:
        defined = np.ones_like(connection_from_indices, dtype=bool)
        overlap_active = np.full_like(connection_from_indices, undefined_value, dtype=np.int8)

        if from_active_status is None:
            connection_from_active = np.ones_like(connection_from_indices, dtype=bool)
        else:
            connection_from_active = from_active_status[connection_from_indices]
            defined &= ~from_active_status.is_undefined()[connection_from_indices]

        if to_active_status is None:
            connection_to_active = np.ones_like(connection_to_indices, dtype=bool)
        else:
            connection_to_active = to_active_status[connection_to_indices]
            defined &= ~to_active_status.is_undefined()[connection_to_indices]

        overlap_active[defined] = np.logical_and(connection_from_active, connection_to_active)[
            defined
        ]
        return overlap_active

    @classmethod
    def _generate_display_name(
        cls,
        from_dataset_name: str,
        from_reference: t.Iterable,
        from_id: t.Iterable,
        to_dataset_name: str,
        to_reference: t.Iterable,
        to_id: t.Iterable,
        display_config: str,
    ) -> np.ndarray:
        if display_config is None:
            display_config = cls.default_display_name_template

        return np.array(
            [
                display_config.format(
                    from_dataset_name=from_dataset_name,
                    from_reference=fr,
                    from_id=fi,
                    to_dataset_name=to_dataset_name,
                    to_reference=tr,
                    to_id=ti,
                )
                for fr, tr, fi, ti in zip(from_reference, to_reference, from_id, to_id)
            ],
            dtype=str,
        )
