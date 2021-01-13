from dataclasses import dataclass
from logging import Logger
from typing import Dict, List, Optional

import numpy as np
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from model_engine import TimeStamp
from model_engine.dataset_manager.dataset_handler import DataSet, Property
from model_engine.dataset_manager.exception import IncompleteInitializationData
from spatial_mapper.geometry import GeometryCollection, LineStringCollection, PointCollection
from spatial_mapper.mapper import Mapper
from .dataset import GeometryDataset, OverlapDataset, OverlapEntity, GeometryEntity


@dataclass
class Connection:
    from_entities: GeometryEntity
    to_entities: GeometryEntity
    from_index: int
    to_index: int


class OverlapStatus:
    def __init__(
        self,
        from_dataset: GeometryDataset,
        to_datasets: List[GeometryDataset],
        overlap_dataset: OverlapDataset,
        logger: Logger,
        distance_threshold: float,
    ) -> None:
        self._logger = logger
        self._from_dataset = from_dataset
        self._to_datasets = to_datasets
        self._overlap_dataset = overlap_dataset
        self._distance_threshold = distance_threshold

        self._check_init_ready(self._overlap_dataset)
        self._check_init_ready(self._from_dataset)
        for to_dataset in self._to_datasets:
            self._check_init_ready(to_dataset)

        self._connections: List[Connection] = []
        self._geometries: Dict[GeometryEntity, GeometryCollection] = {}

    def update(self, time_stamp: TimeStamp) -> Optional[TimeStamp]:
        if not self._connections:
            self._calculate_geometries()
            self._resolve_connections()
            self._resolve_overlap_points()

        self._publish_active_overlaps()
        return None

    def _calculate_geometries(self) -> None:
        self._geometries[self._from_dataset.entity] = self._from_dataset.get_geometry()

        for to_dataset in self._to_datasets:
            self._geometries[to_dataset.entity] = to_dataset.get_geometry()

    def _resolve_connections(self) -> None:
        if self._connections:
            return

        self._connections = []
        from_ids = []
        to_ids = []
        from_references = []
        to_references = []
        display_names = []
        connected_to_datasets = []

        for to_dataset in self._to_datasets:

            from_entities = self._from_dataset.entity
            to_entities = to_dataset.entity

            mapper = Mapper(self._geometries[to_entities])
            mapping = mapper.find_in_radius(
                self._geometries[from_entities], self._distance_threshold
            )

            for from_index, to_indices in enumerate(mapping.iterate()):
                for to_index in to_indices:
                    from_reference = from_entities.reference.data[from_index]
                    to_reference = to_entities.reference.data[to_index]

                    from_references.append(from_reference)
                    to_references.append(to_reference)
                    display_names.append(
                        self._generate_display_name(
                            self._from_dataset.name, from_reference, to_dataset.name, to_reference
                        )
                    )

                    from_ids.append(from_entities.ids[from_index])
                    to_ids.append(to_entities.ids[to_index])
                    connected_to_datasets.append(to_dataset.name)
                    self._connections.append(
                        Connection(
                            from_entities=from_entities,
                            to_entities=to_entities,
                            from_index=from_index,
                            to_index=to_index,
                        )
                    )

        overlap_entities: OverlapEntity = self._overlap_dataset[OverlapEntity]
        overlap_entities.display_name = self._fill_overlap_data(
            overlap_entities.display_name, display_names
        )
        overlap_entities.connection_from_reference = self._fill_overlap_data(
            overlap_entities.connection_from_reference, from_references
        )
        overlap_entities.connection_to_reference = self._fill_overlap_data(
            overlap_entities.connection_to_reference, to_references
        )
        overlap_entities.connection_from_id = self._fill_overlap_data(
            overlap_entities.connection_from_id, from_ids
        )
        overlap_entities.connection_to_id = self._fill_overlap_data(
            overlap_entities.connection_to_id, to_ids
        )
        overlap_entities.connection_from_dataset = self._fill_overlap_data(
            overlap_entities.connection_from_dataset, [self._from_dataset.name] * len(from_ids)
        )
        overlap_entities.connection_to_dataset = self._fill_overlap_data(
            overlap_entities.connection_to_dataset, connected_to_datasets
        )

    def _resolve_overlap_points(self):
        closest_xs = []
        closest_ys = []
        for connection in self._connections:
            from_entities = connection.from_entities
            to_entities = connection.to_entities

            from_geometry_collection = self._geometries[from_entities]
            to_geometry_collection = self._geometries[to_entities]

            from_geometry = self._get_entity_geometry(
                from_geometry_collection, connection.from_index
            )
            to_geometry = self._get_entity_geometry(to_geometry_collection, connection.to_index)

            nearest_from, nearest_to = nearest_points(from_geometry, to_geometry)
            closest_xs.append((nearest_from.x + nearest_to.x) / 2)
            closest_ys.append((nearest_from.y + nearest_to.y) / 2)

        overlap_entities: OverlapEntity = self._overlap_dataset[OverlapEntity]
        overlap_entities.x = self._fill_overlap_data(overlap_entities.x, closest_xs)
        overlap_entities.y = self._fill_overlap_data(overlap_entities.y, closest_ys)

    @staticmethod
    def _get_entity_geometry(
        geometry_collection: GeometryCollection, entity_index: int
    ) -> BaseGeometry:
        if isinstance(geometry_collection, PointCollection):
            return Point(geometry_collection.coord_seq[entity_index])
        if type(geometry_collection) is LineStringCollection:
            coords = geometry_collection.coord_seq[
                geometry_collection.indptr[entity_index] : geometry_collection.indptr[
                    entity_index + 1
                ]
            ]
            return LineString(coords)
        raise TypeError(f"Type {type(geometry_collection)} is not supported.")

    def _publish_active_overlaps(self):
        from_entities = self._from_dataset.entity
        overlap_statuses: List[bool] = []
        from_entity_overlaps = np.zeros_like(from_entities.ids, dtype=np.bool)

        for connection in self._connections:
            from_entities, to_entities = connection.from_entities, connection.to_entities
            from_active = from_entities.active_status.data[connection.from_index]
            to_active = to_entities.active_status.data[connection.to_index]
            overlap_active = from_active and to_active
            overlap_statuses.append(overlap_active)
            from_entity_overlaps[connection.from_index] |= overlap_active

        from_entities.overlap_active = from_entity_overlaps

        overlap_entities: OverlapEntity = self._overlap_dataset[OverlapEntity]
        overlap_entities.overlap_active = self._fill_overlap_data(
            overlap_entities.overlap_active, overlap_statuses
        )

    def _fill_overlap_data(self, prop: Property, data: List) -> np.ndarray:
        data = data + [prop.undefined] * (
            len(self._overlap_dataset[OverlapEntity].ids) - len(data)
        )

        return np.array(data)

    @staticmethod
    def _check_init_ready(dataset: DataSet) -> None:
        if not dataset.is_complete_for_init(check_undefined=False):
            raise IncompleteInitializationData()
        dataset.reset_track_update()

    @staticmethod
    def _generate_display_name(
        from_dataset_name: str, from_reference: str, to_dataset_name: str, to_reference: str
    ) -> str:
        return (
            f"Overlap from {from_dataset_name} reference {from_reference}"
            f" to {to_dataset_name} reference {to_reference}"
        )
