"""ID generator for mapping between Movici and Power Grid Model IDs.

Power-grid-model uses int32 IDs that must be unique globally across all
component types. This module provides bidirectional mapping between
Movici entity IDs and PGM component IDs.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from movici_simulation_core.core import Index


class ComponentIdManager:
    """Manages globally unique IDs for all component types.

    Power-grid-model requires unique IDs across ALL component types, not just
    within each type. This class maintains a global counter and per-type
    parallel arrays for bidirectional ID translation.
    """

    def __init__(self) -> None:
        self._next_id = 0
        self._movici_ids: dict[str, np.ndarray] = {}
        self._pgm_ids: dict[str, np.ndarray] = {}
        self._index_cache: dict[str, Index] = {}

    def register_ids(self, component_type: str, movici_ids: npt.ArrayLike) -> np.ndarray:
        """Register Movici IDs for a component type with globally unique PGM IDs.

        :param component_type: PGM component type name.
        :param movici_ids: Array of Movici entity IDs.
        :returns: Array of globally unique PGM IDs.
        """
        movici_ids = np.asarray(movici_ids, dtype=np.int32)
        n = len(movici_ids)

        pgm_ids = np.arange(self._next_id, self._next_id + n, dtype=np.int32)
        self._next_id += n

        if component_type in self._movici_ids:
            self._movici_ids[component_type] = np.concatenate(
                [self._movici_ids[component_type], movici_ids]
            )
            self._pgm_ids[component_type] = np.concatenate(
                [self._pgm_ids[component_type], pgm_ids]
            )
        else:
            self._movici_ids[component_type] = movici_ids.copy()
            self._pgm_ids[component_type] = pgm_ids.copy()

        # Invalidate cached index
        self._index_cache.pop(component_type, None)

        return pgm_ids

    def _get_index(self, component_type: str) -> Index:
        """Get or build the Index for forward lookups on a component type."""
        if component_type not in self._index_cache:
            if component_type not in self._movici_ids:
                raise ValueError(f"Component type not registered: {component_type}")
            self._index_cache[component_type] = Index(self._movici_ids[component_type])
        return self._index_cache[component_type]

    def get_pgm_ids(self, component_type: str, movici_ids: npt.ArrayLike) -> np.ndarray:
        """Get PGM IDs for a component type.

        :param component_type: PGM component type name.
        :param movici_ids: Array of Movici entity IDs.
        :returns: Array of PGM IDs.
        :raises ValueError: If component type not registered or IDs not found.
        """
        movici_ids = np.asarray(movici_ids, dtype=np.int32)
        index = self._get_index(component_type)
        positions = index.query_indices(movici_ids)

        if np.any(positions == -1):
            missing = movici_ids[positions == -1]
            raise ValueError(f"Movici IDs not registered for {component_type}: {missing}")

        return self._pgm_ids[component_type][positions]

    def get_movici_ids(self, component_type: str, pgm_ids: npt.ArrayLike) -> np.ndarray:
        """Get Movici IDs for a component type.

        :param component_type: PGM component type name.
        :param pgm_ids: Array of PGM IDs.
        :returns: Array of Movici entity IDs.
        :raises ValueError: If component type not registered or IDs not found.
        """
        pgm_ids = np.asarray(pgm_ids, dtype=np.int32)
        if component_type not in self._pgm_ids:
            raise ValueError(f"Component type not registered: {component_type}")

        comp_pgm = self._pgm_ids[component_type]
        # searchsorted relies on PGM IDs being monotonically increasing,
        # which is guaranteed by register_ids using np.arange from _next_id.
        positions = np.searchsorted(comp_pgm, pgm_ids)

        # Clamp to valid range for bounds check
        clamped = np.clip(positions, 0, len(comp_pgm) - 1)
        valid = comp_pgm[clamped] == pgm_ids

        if not np.all(valid):
            missing = pgm_ids[~valid]
            raise ValueError(f"PGM IDs not found for {component_type}: {missing}")

        return self._movici_ids[component_type][positions]

    def resolve_ids(self, component_types: list[str], movici_ids: npt.ArrayLike) -> np.ndarray:
        """Vectorized lookup across multiple component types.

        For each Movici ID, tries each component type in order and fills in
        the corresponding PGM ID. Raises if any IDs remain unresolved.

        :param component_types: List of PGM component type names to search.
        :param movici_ids: Array of Movici entity IDs.
        :returns: Array of PGM IDs.
        :raises ValueError: If any IDs cannot be resolved.
        """
        movici_ids = np.asarray(movici_ids, dtype=np.int32)
        result = np.full(len(movici_ids), -1, dtype=np.int32)
        unresolved = np.ones(len(movici_ids), dtype=bool)

        for comp_type in component_types:
            if comp_type not in self._movici_ids:
                continue
            if not np.any(unresolved):
                break

            index = self._get_index(comp_type)
            candidates = movici_ids[unresolved]
            positions = index.query_indices(candidates)
            found = positions != -1

            if np.any(found):
                # Map back to original indices
                unresolved_indices = np.flatnonzero(unresolved)
                matched = unresolved_indices[found]
                result[matched] = self._pgm_ids[comp_type][positions[found]]
                unresolved[matched] = False

        if np.any(unresolved):
            bad = movici_ids[unresolved]
            raise ValueError(f"Cannot resolve Movici IDs to PGM IDs: {bad}")

        return result

    def clear(self) -> None:
        """Clear all ID mappings and reset counter."""
        self._next_id = 0
        self._movici_ids.clear()
        self._pgm_ids.clear()
        self._index_cache.clear()
