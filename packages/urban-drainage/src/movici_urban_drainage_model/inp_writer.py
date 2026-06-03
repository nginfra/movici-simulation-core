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
    "Polygons",
    "SYMBOLS",
)


def fmt_hms(seconds: float) -> str:
    """Format a duration in seconds as a SWMM ``HH:MM:SS`` string."""
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def fmt_num(value: float) -> str:
    """Format a numeric value compactly for an ``.inp`` cell."""
    fval = float(value)
    if fval == int(fval):
        return str(int(fval))
    return repr(fval)


class InpBuilder:
    """Collects ``.inp`` rows by section and renders the full input file."""

    def __init__(self) -> None:
        self._sections: t.Dict[str, t.List[str]] = {}

    def add(self, section: str, *cells: t.Any) -> None:
        """Append a whitespace-delimited row of *cells* to *section*."""
        row = "  ".join(str(c) for c in cells)
        self._sections.setdefault(section, []).append(row)

    def add_raw(self, section: str, line: str) -> None:
        """Append a pre-formatted *line* to *section*."""
        self._sections.setdefault(section, []).append(line)

    def has(self, section: str) -> bool:
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
