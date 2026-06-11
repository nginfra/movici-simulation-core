"""SWMM ``.inp`` DataSource for the Movici dataset creator.

Reads an existing SWMM ``.inp`` file and exposes its objects as Movici dataset
creator sources, mirroring :mod:`movici_drinking_water_model.epanet_source`. This
is the *authoring* counterpart to the model's runtime ``.inp`` synthesis: it lets
an existing SWMM model be imported into a Movici dataset.

The parser is intentionally dependency-free (no swmmio): it tokenises the
``[SECTION]`` blocks of the ``.inp`` and exposes scalar attributes plus point /
line / polygon geometry. Enum-like columns (shapes, types) are exposed as their
SWMM keyword strings, which the dataset creator's enum-conversion step maps to
integer indices.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core.attributes import (
    Geometry_Linestring2d,
    Geometry_Polygon2d,
    Geometry_X,
    Geometry_Y,
)
from movici_simulation_core.preprocessing import DataSource, MultipleEntityTypeSource
from movici_simulation_core.preprocessing.data_sources import GeometryType


def get_float_or_none(row: t.Sequence[str], idx: int) -> t.Optional[float]:
    """Return ``float(row[idx])`` or ``None`` if the column is absent/non-numeric."""
    if idx >= len(row):
        return None
    try:
        return float(row[idx])
    except ValueError:
        return None


def get_string_or_none(row: t.Sequence[str], idx: int) -> t.Optional[str]:
    return row[idx] if idx < len(row) else None


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


class SwmmInp:
    """A parsed SWMM ``.inp`` file: tokenised sections plus geometry maps."""

    def __init__(self, path: t.Union[str, Path]) -> None:
        self.sections: t.Dict[str, t.List[t.List[str]]] = {}
        self.coordinates: t.Dict[str, t.Tuple[float, float]] = {}
        self.symbols: t.Dict[str, t.Tuple[float, float]] = {}
        self.vertices: t.Dict[str, t.List[t.Tuple[float, float]]] = {}
        self.polygons: t.Dict[str, t.List[t.Tuple[float, float]]] = {}
        self.xsections: t.Dict[str, t.List[str]] = {}
        # curve name -> {"type": keyword|None, "points": [(x, y), ...]}
        self.curves: t.Dict[str, t.Dict[str, t.Any]] = {}
        self._parse(Path(path))

    def _parse(self, path: Path) -> None:
        current: t.Optional[str] = None
        for raw in path.read_text().splitlines():
            line = raw.split(";", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                current = line[1:-1].strip().upper()
                self.sections.setdefault(current, [])
                continue
            if current is None:
                continue
            tokens = line.split()
            if current == "COORDINATES" and len(tokens) >= 3:
                self.coordinates[tokens[0]] = (float(tokens[1]), float(tokens[2]))
            elif current == "SYMBOLS" and len(tokens) >= 3:
                self.symbols[tokens[0]] = (float(tokens[1]), float(tokens[2]))
            elif current == "VERTICES" and len(tokens) >= 3:
                self.vertices.setdefault(tokens[0], []).append(
                    (float(tokens[1]), float(tokens[2]))
                )
            elif current == "POLYGONS" and len(tokens) >= 3:
                self.polygons.setdefault(tokens[0], []).append(
                    (float(tokens[1]), float(tokens[2]))
                )
            elif current == "XSECTIONS" and tokens:
                self.xsections[tokens[0]] = tokens
            elif current == "CURVES" and tokens:
                entry = self.curves.setdefault(tokens[0], {"type": None, "points": []})
                rest = tokens[1:]
                if rest and not _is_number(rest[0]):
                    entry["type"] = rest[0]
                    rest = rest[1:]
                # remaining tokens are x y pairs (one or more per line)
                for i in range(0, len(rest) - 1, 2):
                    entry["points"].append((float(rest[i]), float(rest[i + 1])))
            else:
                self.sections[current].append(tokens)


# Records builders: each maps the tokenised rows of a section to a list of
# attribute dicts (one per object). ``name`` is always the object id.


def _xsection_attrs(inp: SwmmInp, name: str) -> dict:
    xs = inp.xsections.get(name)
    if not xs:
        return {}
    return {
        "cross_section_shape": get_string_or_none(xs, 1),
        "cross_section_geometry": [
            get_float_or_none(xs, 2) or 0.0,
            get_float_or_none(xs, 3) or 0.0,
            get_float_or_none(xs, 4) or 0.0,
            get_float_or_none(xs, 5) or 0.0,
        ],
    }


def _curve_points(inp: SwmmInp, name: t.Optional[str]) -> t.Optional[t.List[t.List[float]]]:
    """Resolve a ``[CURVES]`` name to a list of ``[x, y]`` points (CSR-compatible)."""
    if not name:
        return None
    curve = inp.curves.get(name)
    if not curve or not curve["points"]:
        return None
    return [[x, y] for (x, y) in curve["points"]]


def _junction_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("JUNCTIONS", []):
        out.append(
            {
                "name": r[0],
                "invert_elevation": get_float_or_none(r, 1),
                "max_depth": get_float_or_none(r, 2),
                "initial_depth": get_float_or_none(r, 3),
                "surcharge_depth": get_float_or_none(r, 4),
                "ponded_area": get_float_or_none(r, 5),
            }
        )
    return out


def _outfall_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("OUTFALLS", []):
        outfall_type = get_string_or_none(r, 2)
        rec = {
            "name": r[0],
            "invert_elevation": get_float_or_none(r, 1),
            "outfall_type": outfall_type,
        }
        if outfall_type and outfall_type.upper() in ("FIXED", "TIDAL", "TIMESERIES"):
            rec["fixed_stage"] = get_float_or_none(r, 3)
            rec["flap_gate"] = get_string_or_none(r, 4)
        else:
            rec["flap_gate"] = get_string_or_none(r, 3)
        out.append(rec)
    return out


def _storage_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("STORAGE", []):
        rec = {
            "name": r[0],
            "invert_elevation": get_float_or_none(r, 1),
            "max_depth": get_float_or_none(r, 2),
            "initial_depth": get_float_or_none(r, 3),
            "storage_curve_type": get_string_or_none(r, 4),
        }
        if (get_string_or_none(r, 4) or "").upper() == "FUNCTIONAL":
            rec["storage_coefficient"] = get_float_or_none(r, 5)
            rec["storage_exponent"] = get_float_or_none(r, 6)
            rec["storage_constant"] = get_float_or_none(r, 7)
        elif (get_string_or_none(r, 4) or "").upper() == "TABULAR":
            rec["storage_curve"] = _curve_points(inp, get_string_or_none(r, 5))
        out.append(rec)
    return out


def _conduit_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("CONDUITS", []):
        rec = {
            "name": r[0],
            "from_node": get_string_or_none(r, 1),
            "to_node": get_string_or_none(r, 2),
            "length": get_float_or_none(r, 3),
            "roughness": get_float_or_none(r, 4),
            "inlet_offset": get_float_or_none(r, 5),
            "outlet_offset": get_float_or_none(r, 6),
            "initial_flow": get_float_or_none(r, 7),
        }
        rec.update(_xsection_attrs(inp, r[0]))
        out.append(rec)
    return out


def _pump_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("PUMPS", []):
        curve_name = get_string_or_none(r, 3)
        rec = {
            "name": r[0],
            "from_node": get_string_or_none(r, 1),
            "to_node": get_string_or_none(r, 2),
            "startup_depth": get_float_or_none(r, 5),
            "shutoff_depth": get_float_or_none(r, 6),
            "pump_curve_type": None,
            "pump_curve": None,
        }
        if curve_name in (None, "*"):
            rec["pump_curve_type"] = "IDEAL"
        elif curve_name in inp.curves:
            rec["pump_curve_type"] = inp.curves[curve_name]["type"]
            rec["pump_curve"] = _curve_points(inp, curve_name)
        out.append(rec)
    return out


def _orifice_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("ORIFICES", []):
        rec = {
            "name": r[0],
            "from_node": get_string_or_none(r, 1),
            "to_node": get_string_or_none(r, 2),
            "orifice_type": get_string_or_none(r, 3),
            "crest_height": get_float_or_none(r, 4),
            "discharge_coefficient": get_float_or_none(r, 5),
            "flap_gate": get_string_or_none(r, 6),
        }
        xs = _xsection_attrs(inp, r[0])
        rec["orifice_shape"] = xs.get("cross_section_shape")
        rec["cross_section_geometry"] = xs.get("cross_section_geometry")
        out.append(rec)
    return out


def _weir_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("WEIRS", []):
        rec = {
            "name": r[0],
            "from_node": get_string_or_none(r, 1),
            "to_node": get_string_or_none(r, 2),
            "weir_type": get_string_or_none(r, 3),
            "crest_height": get_float_or_none(r, 4),
            "discharge_coefficient": get_float_or_none(r, 5),
            "flap_gate": get_string_or_none(r, 6),
        }
        rec["cross_section_geometry"] = _xsection_attrs(inp, r[0]).get("cross_section_geometry")
        out.append(rec)
    return out


def _outlet_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("OUTLETS", []):
        rating_type = get_string_or_none(r, 4)
        rec = {
            "name": r[0],
            "from_node": get_string_or_none(r, 1),
            "to_node": get_string_or_none(r, 2),
            "crest_height": get_float_or_none(r, 3),
            "outlet_rating_type": rating_type,
        }
        if rating_type and "TABULAR" in rating_type.upper():
            rec["rating_curve"] = _curve_points(inp, get_string_or_none(r, 5))
            rec["flap_gate"] = get_string_or_none(r, 6)
        else:
            rec["rating_coefficient"] = get_float_or_none(r, 5)
            rec["rating_exponent"] = get_float_or_none(r, 6)
            rec["flap_gate"] = get_string_or_none(r, 7)
        out.append(rec)
    return out


def _subcatchment_records(inp: SwmmInp) -> t.List[dict]:
    subareas = {r[0]: r for r in inp.sections.get("SUBAREAS", [])}
    infil = {r[0]: r for r in inp.sections.get("INFILTRATION", [])}
    out = []
    for r in inp.sections.get("SUBCATCHMENTS", []):
        name = r[0]
        rec = {
            "name": name,
            "raingage": get_string_or_none(r, 1),
            "outlet_node": get_string_or_none(r, 2),
            "area": get_float_or_none(r, 3),
            "percent_impervious": get_float_or_none(r, 4),
            "width": get_float_or_none(r, 5),
            "slope": get_float_or_none(r, 6),
        }
        sa = subareas.get(name)
        if sa:
            rec.update(
                {
                    "n_imperv": get_float_or_none(sa, 1),
                    "n_perv": get_float_or_none(sa, 2),
                    "s_imperv": get_float_or_none(sa, 3),
                    "s_perv": get_float_or_none(sa, 4),
                    "pct_zero": get_float_or_none(sa, 5),
                }
            )
        inf = infil.get(name)
        if inf:
            rec.update(
                {
                    "max_infiltration_rate": get_float_or_none(inf, 1),
                    "min_infiltration_rate": get_float_or_none(inf, 2),
                    "decay_constant": get_float_or_none(inf, 3),
                    "dry_time": get_float_or_none(inf, 4),
                }
            )
        out.append(rec)
    return out


def _raingage_records(inp: SwmmInp) -> t.List[dict]:
    out = []
    for r in inp.sections.get("RAINGAGES", []):
        out.append(
            {
                "name": r[0],
                "rainfall_format": get_string_or_none(r, 1),
                "rainfall_interval": get_string_or_none(r, 2),
            }
        )
    return out


_RECORD_BUILDERS: t.Dict[str, t.Callable[[SwmmInp], t.List[dict]]] = {
    "junctions": _junction_records,
    "outfalls": _outfall_records,
    "storage": _storage_records,
    "conduits": _conduit_records,
    "pumps": _pump_records,
    "orifices": _orifice_records,
    "weirs": _weir_records,
    "outlets": _outlet_records,
    "subcatchments": _subcatchment_records,
    "raingages": _raingage_records,
}

_NODE_TYPES = frozenset({"junctions", "outfalls", "storage"})
_LINK_TYPES = frozenset({"conduits", "pumps", "orifices", "weirs", "outlets"})


class _SWMMEntitySource(DataSource):
    """DataSource for a single entity type parsed from a SWMM ``.inp`` file."""

    def __init__(self, inp: SwmmInp, entity_type: str) -> None:
        self.inp = inp
        self.entity_type = entity_type
        self.records = _RECORD_BUILDERS[entity_type](inp)

    def get_attribute(self, name: str):
        return [rec.get(name) for rec in self.records]

    def _node_coordinate(self, node_name: str) -> t.Tuple[float, float]:
        coord = self.inp.coordinates.get(node_name)
        if coord is None:
            raise ValueError(f"Node '{node_name}' has no coordinates")
        return coord

    def get_geometry(self, geometry_type: GeometryType):
        if self.entity_type in _NODE_TYPES:
            if geometry_type != "points":
                raise ValueError(
                    f"Node entity '{self.entity_type}' only supports 'points' geometry, "
                    f"got '{geometry_type}'"
                )
            xs, ys = [], []
            for rec in self.records:
                x, y = self._node_coordinate(rec["name"])
                xs.append(x)
                ys.append(y)
            return {Geometry_X.name: xs, Geometry_Y.name: ys}

        if self.entity_type in _LINK_TYPES:
            if geometry_type != "lines":
                raise ValueError(
                    f"Link entity '{self.entity_type}' only supports 'lines' geometry, "
                    f"got '{geometry_type}'"
                )
            lines = []
            for rec in self.records:
                start = self._node_coordinate(rec["from_node"])
                end = self._node_coordinate(rec["to_node"])
                mids = self.inp.vertices.get(rec["name"], [])
                points = [list(start)] + [list(v) for v in mids] + [list(end)]
                lines.append(points)
            return {Geometry_Linestring2d.name: lines}

        if self.entity_type == "subcatchments":
            if geometry_type != "polygons":
                raise ValueError(
                    f"Subcatchment entity only supports 'polygons' geometry, got '{geometry_type}'"
                )
            polygons = []
            for rec in self.records:
                ring = [list(p) for p in self.inp.polygons.get(rec["name"], [])]
                if ring and ring[0] != ring[-1]:
                    ring.append(list(ring[0]))  # close the ring
                polygons.append(ring)
            return {Geometry_Polygon2d.name: polygons}

        if self.entity_type == "raingages":
            if geometry_type != "points":
                raise ValueError(
                    f"Rain gage entity only supports 'points' geometry, got '{geometry_type}'"
                )
            xs, ys = [], []
            for rec in self.records:
                x, y = self.inp.symbols.get(rec["name"], (0.0, 0.0))
                xs.append(x)
                ys.append(y)
            return {Geometry_X.name: xs, Geometry_Y.name: ys}

        raise ValueError(f"No geometry available for entity type '{self.entity_type}'")

    def get_bounding_box(self):
        if self.entity_type not in _NODE_TYPES:
            return None
        coords = [self.inp.coordinates.get(rec["name"]) for rec in self.records]
        coords = [c for c in coords if c is not None]
        if not coords:
            return None
        xs, ys = zip(*coords)
        return (min(xs), min(ys), max(xs), max(ys))

    def __len__(self):
        return len(self.records)


class SWMMSource(MultipleEntityTypeSource):
    r"""Multi-entity source for reading SWMM ``.inp`` files.

    Registered as the ``"swmm"`` source type for the dataset creator. Contains
    entity types: ``junctions``, ``outfalls``, ``storage``, ``conduits``,
    ``pumps``, ``orifices``, ``weirs``, ``outlets``, ``subcatchments`` and
    ``raingages``. Access individual entity types with bracket notation::

        source = SWMMSource("network.inp")
        source["junctions"].get_attribute("invert_elevation")

    The ``.inp`` file is parsed lazily on first entity-type access and shared
    across sub-sources of the same ``SWMMSource`` instance.

    :param file: Path to the ``.inp`` file
    """

    ENTITY_TYPES = frozenset(_RECORD_BUILDERS)

    def __init__(self, file: t.Union[Path, str]) -> None:
        self.file = Path(file)
        self.inp: t.Optional[SwmmInp] = None
        self._entity_sources: t.Dict[str, _SWMMEntitySource] = {}

    @classmethod
    def from_source_info(cls, source_info):
        """Create from a source info dictionary.

        If ``entity_type`` is present, returns a single-entity ``DataSource`` for
        that type; otherwise returns the full multi-entity source.
        """
        source = cls(file=source_info["path"])
        if "entity_type" in source_info:
            return source[source_info["entity_type"]]
        return source

    def keys(self) -> t.Iterable[str]:
        return iter(sorted(self.ENTITY_TYPES))

    def __getitem__(self, entity_type: str) -> _SWMMEntitySource:
        if entity_type not in self.ENTITY_TYPES:
            raise KeyError(
                f"Unknown entity type '{entity_type}', must be one of {sorted(self.ENTITY_TYPES)}"
            )
        if self.inp is None:
            self.inp = SwmmInp(self.file)
        if entity_type not in self._entity_sources:
            self._entity_sources[entity_type] = _SWMMEntitySource(self.inp, entity_type)
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
