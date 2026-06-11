"""Helpers for synthesising a SWMM ``.inp`` input file from a Movici dataset.

pyswmm requires an ``.inp`` file to open a :class:`~pyswmm.Simulation`. Unlike
WNTR (which builds its network model in memory), there is no supported way to
construct a SWMM model purely in code, so the simulation wrapper writes a
transient ``.inp`` describing the Movici dataset and opens the simulation on it.

:class:`InpBuilder` collects rows per ``[SECTION]`` and renders them into the
ordered, whitespace-delimited text that SWMM expects.
"""

from __future__ import annotations

import typing as t

# The order in which sections are written. SWMM is largely order-tolerant, but a
# conventional ordering keeps the synthesised file readable and diff-friendly.
SECTION_ORDER: t.Tuple[str, ...] = (
    "TITLE",
    "OPTIONS",
    "EVAPORATION",
    "RAINGAGES",
    "SUBCATCHMENTS",
    "SUBAREAS",
    "INFILTRATION",
    "JUNCTIONS",
    "OUTFALLS",
    "STORAGE",
    "CONDUITS",
    "PUMPS",
    "ORIFICES",
    "WEIRS",
    "OUTLETS",
    "XSECTIONS",
    "CURVES",
    "TIMESERIES",
    "REPORT",
    "COORDINATES",
    "VERTICES",
    "POLYGONS",
    "SYMBOLS",
)


def fmt_hms(seconds: float) -> str:
    """Format a duration in seconds as a SWMM ``HH:MM:SS`` string."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def fmt_num(value: float, max_decimals: t.Optional[int] = None) -> t.Union[int, float]:
    """Coerce a numeric value for an ``.inp`` cell, keeping full precision by default.

    Returns an ``int`` for whole values (so ``10`` rather than ``10.0``) and otherwise
    the float unchanged; the builder renders it with ``str()``, which round-trips full
    ``float64`` precision (SWMM parses ``.inp`` numbers into doubles, so nothing is
    truncated). Pass ``max_decimals`` to round for a more compact file.
    """
    fval = float(value)
    if max_decimals is not None:
        fval = round(fval, max_decimals)
    return int(fval) if fval == int(fval) else fval


class InpBuilder:
    """Collects ``.inp`` rows by section and renders the full input file."""

    def __init__(self) -> None:
        self._sections: t.Dict[str, t.List[str]] = {}

    def add(self, section: str, *cells: t.Any) -> None:
        """Append a whitespace-delimited row of *cells* to *section*."""
        row = "  ".join(str(c) for c in cells)
        self._sections.setdefault(section, []).append(row)

    def __contains__(self, section: str) -> bool:
        return bool(self._sections.get(section))

    def render(self) -> str:
        """Render all collected sections into ``.inp`` text."""
        ordered = list(SECTION_ORDER)
        # Append any sections that were added but are not in the canonical order
        for name in self._sections:
            if name not in ordered:
                ordered.append(name)

        chunks: t.List[str] = []
        for name in ordered:
            rows = self._sections.get(name)
            if not rows:
                continue
            chunks.append(f"[{name}]")
            chunks.extend(rows)
            chunks.append("")
        return "\n".join(chunks) + "\n"
