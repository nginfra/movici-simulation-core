from dataclasses import dataclass
from logging import Logger
from typing import Dict, List, Optional, Tuple, Iterable, cast

import numba
import numpy as np
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from model_engine import TimeStamp
from model_engine.dataset_manager.dataset_handler import DataSet
from model_engine.dataset_manager.exception import IncompleteInitializationData
from spatial_mapper.geometry import GeometryCollection, LineStringCollection, PointCollection
from spatial_mapper.mapper import Mapper
from .dataset import GeometryDataset, OverlapDataset, OverlapEntity, GeometryEntity


@dataclass
class Connections:
    from_indices: np.ndarray
    to_indices: np.ndarray
    overlap_indices: np.ndarray
    overlap_published: np.ndarray
    to_dataset_name: str


@dataclass
class OverlapPropertiesToPublish:
    display_name: np.ndarray
    from_reference: np.ndarray
    to_reference: np.ndarray
    from_id: np.ndarray
    to_id: np.ndarray
    from_dataset: np.ndarray
    to_dataset: np.ndarray
    overlap_active: np.ndarray
    position_x: np.ndarray
    position_y: np.ndarray

    @staticmethod
    def create(overlap_entities: OverlapEntity) -> "OverlapPropertiesToPublish":
        return OverlapPropertiesToPublish(
            display_name=overlap_entities.display_name.data.copy(),
            from_reference=overlap_entities.connection_from_reference.data.copy(),
            to_reference=overlap_entities.connection_to_reference.data.copy(),
            from_id=overlap_entities.connection_from_id.data.copy(),
            to_id=overlap_entities.connection_to_id.data.copy(),
            from_dataset=overlap_entities.connection_from_dataset.data.copy(),
            to_dataset=overlap_entities.connection_to_dataset.data.copy(),
            overlap_active=overlap_entities.overlap_active.data.copy(),
            position_x=overlap_entities.x.data.copy(),
            position_y=overlap_entities.y.data.copy(),
        )

    def update_str_array(
        self, prop: str, updated_array: np.ndarray, updated_indices: np.ndarray
    ) -> None:
        array = cast(np.ndarray, getattr(self, prop))
        if updated_array.dtype.itemsize > array.dtype.itemsize:
            new_dtype = f"<U{self._get_next_power_of_two(updated_array.itemsize//4)}"
            array = array.astype(new_dtype)
            setattr(self, prop, array)
        array[updated_indices] = updated_array

    def publish(self, overlap_entities: OverlapEntity) -> None:
        overlap_entities.display_name = self.display_name
        overlap_entities.connection_from_reference = self.from_reference
        overlap_entities.connection_to_reference = self.to_reference
        overlap_entities.connection_from_id = self.from_id
        overlap_entities.connection_to_id = self.to_id
        overlap_entities.connection_from_dataset = self.from_dataset
        overlap_entities.connection_to_dataset = self.to_dataset
        overlap_entities.x = self.position_x
        overlap_entities.y = self.position_y
        overlap_entities.overlap_active = self.overlap_active

    @staticmethod
    def _get_next_power_of_two(n):
        if n == 0:
            return 1

        log = np.log2(n)
        if int(log) == log:
            return n * 2

        return 1 << (n - 1).bit_length()


class OverlapStatus:
    default_display_name_template = (
        "Overlap from {from_dataset_name} reference {from_reference}"
        " to {to_dataset_name} reference {to_reference}"
    )

    def __init__(
        self,
        from_dataset: GeometryDataset,
        to_datasets: List[GeometryDataset],
        overlap_dataset: OverlapDataset,
        logger: Logger,
        distance_threshold: float,
        display_name_template: Optional[str],
    ) -> None:
        self._logger = logger
        self._from_dataset = from_dataset
        self._to_datasets = to_datasets
        self._overlap_dataset = overlap_dataset
        self._distance_threshold = distance_threshold
        self.display_name_template = display_name_template

        self._check_init_ready(self._overlap_dataset)
        self._check_init_ready(self._from_dataset)
        for to_dataset in self._to_datasets:
            self._check_init_ready(to_dataset)

        self._connections: Dict[GeometryEntity, Connections] = {}
        self._geometries: Dict[GeometryEntity, GeometryCollection] = {}
        self._overlap_dataset_length: int = len(self._overlap_dataset[OverlapEntity].ids)
        self._next_overlap_index: int = 0

    def update(self, time_stamp: TimeStamp) -> Optional[TimeStamp]:
        if not self._connections:
            self._calculate_geometries()
            self._resolve_connections()

        self._publish_active_overlaps()
        return None

    def _calculate_geometries(self) -> None:
        self._geometries[self._from_dataset.entity] = self._from_dataset.get_geometry()

        for to_dataset in self._to_datasets:
            self._geometries[to_dataset.entity] = to_dataset.get_geometry()

    def _resolve_connections(self) -> None:
        self._connections = {}
        for to_dataset in self._to_datasets:

            from_entities = self._from_dataset.entity
            to_entities = to_dataset.entity

            mapper = Mapper(self._geometries[to_entities])
            mapping = mapper.find_in_radius(
                self._geometries[from_entities], self._distance_threshold
            )

            from_indices = []
            to_indices = []

            for from_index, mapping_to_indices in enumerate(mapping.iterate()):
                from_indices += [from_index] * len(mapping_to_indices)
                to_indices += mapping_to_indices.tolist()

            self._connections[to_entities] = Connections(
                from_indices=np.array(from_indices),
                to_indices=np.array(to_indices),
                overlap_indices=np.full_like(from_indices, -1),
                overlap_published=np.full_like(from_indices, False, dtype=np.bool),
                to_dataset_name=to_dataset.name,
            )

    def _publish_connections(
        self,
        from_entities: GeometryEntity,
        to_entities: GeometryEntity,
        connections: Connections,
        overlap_active: np.ndarray,
        to_publish: OverlapPropertiesToPublish,
    ) -> None:

        new_overlaps = np.where(overlap_active)[0]
        if new_overlaps.size == 0:
            return

        new_overlap_indices = np.arange(
            self._next_overlap_index, self._next_overlap_index + len(new_overlaps)
        )

        if new_overlap_indices[-1] >= len(to_publish.to_id):
            raise IndexError(
                f"Not enough overlap entities in {self._overlap_dataset.name} for this model."
            )

        from_indices = connections.from_indices[new_overlaps]
        to_indices = connections.to_indices[new_overlaps]

        from_ids = from_entities.ids[from_indices]
        to_ids = to_entities.ids[to_indices]

        from_reference = from_entities.reference.data[from_indices]
        to_reference = to_entities.reference.data[to_indices]
        display_name = self._generate_display_name(
            self._from_dataset.name,
            from_reference,
            from_ids,
            connections.to_dataset_name,
            to_reference,
            to_ids,
            self.display_name_template,
        )
        from_dataset = np.array([self._from_dataset.name], np.str)
        to_dataset = np.array([connections.to_dataset_name], np.str)

        to_publish.update_str_array("display_name", display_name, new_overlap_indices)
        to_publish.update_str_array("from_reference", from_reference, new_overlap_indices)
        to_publish.update_str_array("to_reference", to_reference, new_overlap_indices)
        to_publish.update_str_array("from_dataset", from_dataset, new_overlap_indices)
        to_publish.update_str_array("to_dataset", to_dataset, new_overlap_indices)

        to_publish.from_id[new_overlap_indices] = from_ids
        to_publish.to_id[new_overlap_indices] = to_ids
        to_publish.overlap_active[new_overlap_indices] = True
        connections.overlap_published[new_overlaps] = True
        connections.overlap_indices[new_overlaps] = new_overlap_indices

        self._resolve_overlap_point(
            from_entities, to_entities, from_indices, to_indices, new_overlap_indices, to_publish
        )

        self._next_overlap_index += len(new_overlaps)

    def _resolve_overlap_point(
        self,
        from_entities: GeometryEntity,
        to_entities: GeometryEntity,
        from_indices: np.ndarray,
        to_indices: np.ndarray,
        overlap_indices: np.ndarray,
        to_publish: OverlapPropertiesToPublish,
    ):
        from_geometries = self._geometries[from_entities]
        to_geometries = self._geometries[to_entities]

        for from_index, to_index, overlap_index in zip(from_indices, to_indices, overlap_indices):
            x, y = self._calculate_overlap_point(
                from_geometries,
                from_index,
                to_geometries,
                to_index,
            )
            to_publish.position_x[overlap_index] = x
            to_publish.position_y[overlap_index] = y

    @classmethod
    def _calculate_overlap_point(
        cls,
        from_geometry_collection: GeometryCollection,
        from_index: int,
        to_geometry_collection: GeometryCollection,
        to_index: int,
    ) -> Tuple[float, float]:

        from_geometry = cls._get_entity_geometry(from_geometry_collection, from_index)
        to_geometry = cls._get_entity_geometry(to_geometry_collection, to_index)

        nearest_from, nearest_to = nearest_points(from_geometry, to_geometry)
        return (nearest_from.x + nearest_to.x) / 2, (nearest_from.y + nearest_to.y) / 2

    @staticmethod
    def _get_entity_geometry(
        geometry_collection: GeometryCollection, entity_index: int
    ) -> BaseGeometry:
        if isinstance(geometry_collection, PointCollection):
            return Point(geometry_collection.coord_seq[entity_index])
        if isinstance(geometry_collection, LineStringCollection):
            coords = geometry_collection.coord_seq[
                geometry_collection.indptr[entity_index] : geometry_collection.indptr[
                    entity_index + 1
                ]
            ]
            return LineString(coords)
        raise TypeError(f"Type {type(geometry_collection)} is not supported.")

    def _publish_active_overlaps(self):
        overlap_entities: OverlapEntity = self._overlap_dataset[OverlapEntity]
        to_publish = OverlapPropertiesToPublish.create(overlap_entities)

        from_entities = self._from_dataset.entity
        from_entity_overlaps = from_entities.overlap_active.data.copy()
        from_entity_overlaps[
            from_entity_overlaps != overlap_entities.overlap_active.undefined
        ] = False

        for to_entities, connections in self._connections.items():
            self._publish_active_overlaps_for_connections(
                from_entities,
                to_entities,
                connections,
                from_entity_overlaps,
                overlap_entities,
                to_publish,
            )

        from_entities.overlap_active = from_entity_overlaps

        to_publish.publish(overlap_entities)

    def _publish_active_overlaps_for_connections(
        self,
        from_entities: GeometryEntity,
        to_entities: GeometryEntity,
        connections: Connections,
        from_entity_overlaps: np.ndarray,
        overlap_entities: OverlapEntity,
        to_publish: OverlapPropertiesToPublish,
    ) -> None:
        from_active_status = (
            from_entities.active_status.data if from_entities.active_status else None
        )
        to_active_status = to_entities.active_status.data if to_entities.active_status else None

        overlap_undefined_value = overlap_entities.overlap_active.undefined

        overlap_active = self._calculate_active_overlaps(
            from_active_status=from_active_status,
            connection_from_indices=connections.from_indices,
            to_active_status=to_active_status,
            connection_to_indices=connections.to_indices,
            undefined_value=overlap_undefined_value,
        )

        self._calculate_from_entities_overlap_status(
            overlap_active,
            connections.from_indices,
            overlap_undefined_value,
            from_entity_overlaps,
        )

        defined = overlap_active != overlap_undefined_value
        new_overlaps = np.logical_and(
            overlap_active, np.logical_not(connections.overlap_published)
        )[defined]

        self._publish_connections(
            from_entities,
            to_entities,
            connections,
            new_overlaps,
            to_publish,
        )

        published_overlap_indices = connections.overlap_indices[connections.overlap_published]
        to_publish.overlap_active[published_overlap_indices] = overlap_active[
            connections.overlap_published
        ]

    @staticmethod
    def _calculate_active_overlaps(
        from_active_status: Optional[np.ndarray],
        connection_from_indices: np.ndarray,
        to_active_status: Optional[np.ndarray],
        connection_to_indices: np.ndarray,
        undefined_value: int,
    ) -> np.ndarray:
        overlap_active = np.full_like(connection_from_indices, undefined_value, dtype=np.int8)
        if from_active_status is None:
            connection_from_active = np.ones_like(connection_from_indices, dtype=np.bool)
        else:
            connection_from_active = from_active_status[connection_from_indices]
        if to_active_status is None:
            connection_to_active = np.ones_like(connection_to_indices, dtype=np.bool)
        else:
            connection_to_active = to_active_status[connection_to_indices]

        from_active_defined = connection_from_active != undefined_value
        to_active_defined = connection_to_active != undefined_value
        defined = np.logical_and(from_active_defined, to_active_defined)

        overlap_active[defined] = np.logical_and(connection_from_active, connection_to_active)[
            defined
        ]
        return overlap_active

    @staticmethod
    def _calculate_from_entities_overlap_status(
        overlap_active, from_indices, overlap_undefined_value, from_entities_overlap_status
    ):
        from_entities_overlap_status[
            from_entities_overlap_status == overlap_undefined_value
        ] = False
        _logical_or_on_group(
            from_indices, overlap_active, overlap_undefined_value, from_entities_overlap_status
        )

    @staticmethod
    def _check_init_ready(dataset: DataSet) -> None:
        if not dataset.is_complete_for_init(check_undefined=False):
            raise IncompleteInitializationData()
        dataset.reset_track_update()

    @classmethod
    def _generate_display_name(
        cls,
        from_dataset_name: str,
        from_reference: Iterable,
        from_id: Iterable,
        to_dataset_name: str,
        to_reference: Iterable,
        to_id: Iterable,
        display_config: str = None,
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
            dtype=np.str,
        )


@numba.njit(cache=True)
def _logical_or_on_group(
    from_group_indices: np.ndarray,
    from_values: np.ndarray,
    overlap_undefined_value: int,
    target: np.ndarray,
) -> None:
    for index, value in zip(from_group_indices, from_values):
        if value != overlap_undefined_value:
            target[index] |= value
