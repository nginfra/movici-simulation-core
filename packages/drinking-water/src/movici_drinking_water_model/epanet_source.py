"""EPANET INP file DataSource for the dataset creator, backed by WNTR."""

from __future__ import annotations

import typing as t
from pathlib import Path

import numpy as np
import wntr

from movici_simulation_core.attributes import (
    Geometry_Linestring2d,
    Geometry_X,
    Geometry_Y,
)
from movici_simulation_core.preprocessing import DataSource, MultipleEntityTypeSource
from movici_simulation_core.preprocessing.data_sources import GeometryType


class _EPANETEntitySource(DataSource):
    """DataSource for a single entity type from an EPANET INP file."""

    NODE_TYPES = frozenset({"junctions", "tanks", "reservoirs"})
    LINK_TYPES = frozenset({"pipes", "pumps", "valves"})

    def __init__(
        self,
        model: "wntr.network.WaterNetworkModel",
        entity_type: str,
    ) -> None:
        self.model = model
        self.entity_type = entity_type

    @property
    def _features(self) -> t.Iterator[t.Tuple[str, t.Any]]:
        return getattr(self.model, self.entity_type)()

    def get_attribute(self, name: str):
        result: list = []
        for _name, obj in self._features:
            if name == "name":
                result.append(_name)
            else:
                result.append(getattr(obj, name, None))
        return result

    def get_geometry(self, geometry_type: GeometryType):
        if self.entity_type in self.NODE_TYPES:
            if geometry_type != "points":
                raise ValueError(
                    f"Node entity '{self.entity_type}' only supports 'points' geometry, "
                    f"got '{geometry_type}'"
                )
            xs, ys = [], []
            for _name, node in self._features:
                if node.coordinates is None:
                    raise ValueError(f"Node '{_name}' has no coordinates")
                xs.append(node.coordinates[0])
                ys.append(node.coordinates[1])
            return {Geometry_X.name: xs, Geometry_Y.name: ys}
        if self.entity_type in self.LINK_TYPES:
            if geometry_type != "lines":
                raise ValueError(
                    f"Link entity '{self.entity_type}' only supports 'lines' geometry, "
                    f"got '{geometry_type}'"
                )
            lines = []
            for _name, link in self._features:
                start = self.model.get_node(link.start_node_name).coordinates
                end = self.model.get_node(link.end_node_name).coordinates
                if start is None or end is None:
                    raise ValueError(f"Link '{_name}' has an endpoint without coordinates")
                lines.append([[start[0], start[1]], [end[0], end[1]]])
            return {Geometry_Linestring2d.name: lines}
        raise ValueError(f"No geometry available for entity type '{self.entity_type}'")

    def get_bounding_box(self):
        if self.entity_type not in self.NODE_TYPES:
            return None
        coords = [n.coordinates for _, n in self._features if n.coordinates is not None]
        if not coords:
            return None
        xs, ys = zip(*coords)
        return (min(xs), min(ys), max(xs), max(ys))

    def __len__(self):
        return sum(1 for _ in self._features)


class EPANETSource(MultipleEntityTypeSource):
    r"""Multi-entity source for reading EPANET INP files via WNTR.

    Registered as the ``"epanet"`` source type for the dataset creator. Contains
    entity types: ``junctions``, ``tanks``, ``reservoirs``, ``pipes``, ``pumps``,
    ``valves``. Use bracket notation to access individual entity types as
    ``DataSource``\s::

        source = EPANETSource("network.inp")
        junctions = source["junctions"]
        len(junctions)
        junctions.get_attribute("elevation")

    The WNTR model is loaded lazily on first entity-type access and shared across
    sub-sources of the same ``EPANETSource`` instance.

    :param file: Path to the INP file
    """

    ENTITY_TYPES = frozenset({"junctions", "tanks", "reservoirs", "pipes", "pumps", "valves"})

    def __init__(self, file: t.Union[Path, str]) -> None:
        self.file = Path(file)
        self.model: t.Optional["wntr.network.WaterNetworkModel"] = None
        self._entity_sources: t.Dict[str, _EPANETEntitySource] = {}

    @classmethod
    def from_source_info(cls, source_info):
        """Create from a source info dictionary.

        If ``entity_type`` is present in the source info, returns a single-entity
        ``DataSource`` for that type; otherwise returns the full multi-entity
        source.
        """
        source = cls(file=source_info["path"])
        if "entity_type" in source_info:
            return source[source_info["entity_type"]]
        return source

    def keys(self) -> t.Iterable[str]:
        return iter(sorted(self.ENTITY_TYPES))

    def __getitem__(self, entity_type: str) -> _EPANETEntitySource:
        if entity_type not in self.ENTITY_TYPES:
            raise KeyError(
                f"Unknown entity type '{entity_type}', must be one of {sorted(self.ENTITY_TYPES)}"
            )
        if self.model is None:
            self.model = wntr.network.WaterNetworkModel(str(self.file))
        if entity_type not in self._entity_sources:
            self._entity_sources[entity_type] = _EPANETEntitySource(self.model, entity_type)
        return self._entity_sources[entity_type]

    def __contains__(self, entity_type) -> bool:
        return entity_type in self.ENTITY_TYPES

    def get_bounding_box(self):
        bboxes = [
            bbox for et in self.ENTITY_TYPES if (bbox := self[et].get_bounding_box()) is not None
        ]
        if not bboxes:
            return None
        bboxes_arr = np.stack(bboxes)
        return (
            float(bboxes_arr[:, 0].min()),
            float(bboxes_arr[:, 1].min()),
            float(bboxes_arr[:, 2].max()),
            float(bboxes_arr[:, 3].max()),
        )
