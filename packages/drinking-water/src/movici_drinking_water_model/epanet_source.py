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
from movici_simulation_core.preprocessing import DataSource, MultiEntitySource
from movici_simulation_core.preprocessing.data_sources import GeometryType


class _EPANETEntitySource(DataSource):
    """DataSource for a single entity type from an EPANET INP file."""

    NODE_TYPES = frozenset({"junctions", "tanks", "reservoirs"})
    LINK_TYPES = frozenset({"pipes", "pumps", "valves"})

    def __init__(
        self,
        get_model: t.Callable[[], "wntr.network.WaterNetworkModel"],
        entity_type: str,
    ) -> None:
        self._get_model = get_model
        self.entity_type = entity_type
        self._items: t.Optional[t.List[t.Tuple[str, t.Any]]] = None

    def _get_items(self) -> t.List[t.Tuple[str, t.Any]]:
        if self._items is None:
            wn = self._get_model()
            self._items = list(getattr(wn, self.entity_type)())
        return self._items

    def get_attribute(self, name: str):
        items = self._get_items()
        result: list = []
        for _name, obj in items:
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
            for _, node in self._get_items():
                if node.coordinates is None:
                    raise ValueError(f"Node '{_}' has no coordinates")
                xs.append(node.coordinates[0])
                ys.append(node.coordinates[1])
            return {Geometry_X.name: xs, Geometry_Y.name: ys}
        if self.entity_type in self.LINK_TYPES:
            if geometry_type != "lines":
                raise ValueError(
                    f"Link entity '{self.entity_type}' only supports 'lines' geometry, "
                    f"got '{geometry_type}'"
                )
            wn = self._get_model()
            lines = []
            for _name, link in self._get_items():
                start = wn.get_node(link.start_node_name).coordinates
                end = wn.get_node(link.end_node_name).coordinates
                if start is None or end is None:
                    raise ValueError(f"Link '{_name}' has an endpoint without coordinates")
                lines.append([[start[0], start[1]], [end[0], end[1]]])
            return {Geometry_Linestring2d.name: lines}
        raise ValueError(f"No geometry available for entity type '{self.entity_type}'")

    def get_bounding_box(self):
        if self.entity_type not in self.NODE_TYPES:
            return None
        coords = [n.coordinates for _, n in self._get_items() if n.coordinates is not None]
        if not coords:
            return None
        xs, ys = zip(*coords)
        return (min(xs), min(ys), max(xs), max(ys))

    def __len__(self):
        return len(self._get_items())


class EPANETSource(MultiEntitySource):
    r"""Multi-entity source for reading EPANET INP files via WNTR.

    Registered as the ``"epanet"`` source type for the dataset creator. Contains
    entity types: ``junctions``, ``tanks``, ``reservoirs``, ``pipes``, ``pumps``,
    ``valves``. Use bracket notation to access individual entity types as
    ``DataSource``\s::

        source = EPANETSource("network.inp")
        junctions = source["junctions"]
        len(junctions)
        junctions.get_attribute("elevation")

    Multiple ``EPANETSource`` instances sharing the same file path reuse a
    cached WNTR model. The cache is keyed by resolved absolute path and is
    never invalidated — edits to the file within one process are not picked up.

    :param file: Path to the INP file
    """

    _model_cache: t.ClassVar[t.Dict[str, "wntr.network.WaterNetworkModel"]] = {}

    ENTITY_TYPES = frozenset({"junctions", "tanks", "reservoirs", "pipes", "pumps", "valves"})

    def __init__(self, file: t.Union[Path, str]) -> None:
        self.file = Path(file)
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

    def _get_model(self) -> "wntr.network.WaterNetworkModel":
        key = str(self.file.resolve())
        if key not in self._model_cache:
            self._model_cache[key] = wntr.network.WaterNetworkModel(str(self.file))
        return self._model_cache[key]

    def keys(self) -> t.Iterable[str]:
        return iter(sorted(self.ENTITY_TYPES))

    def __getitem__(self, entity_type: str) -> _EPANETEntitySource:
        if entity_type not in self.ENTITY_TYPES:
            raise KeyError(
                f"Unknown entity type '{entity_type}', must be one of {sorted(self.ENTITY_TYPES)}"
            )
        if entity_type not in self._entity_sources:
            self._entity_sources[entity_type] = _EPANETEntitySource(self._get_model, entity_type)
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
