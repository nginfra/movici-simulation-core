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
    mappings for bidirectional ID translation.
    """

    def __init__(self) -> None:
        self._next_id = 0
        # Per-type mappings: movici_id -> pgm_id
        self._movici_to_pgm: dict[str, dict[int, int]] = {}
        # Per-type mappings: pgm_id -> movici_id
        self._pgm_to_movici: dict[str, dict[int, int]] = {}

    def register_ids(self, component_type: str, movici_ids: npt.ArrayLike) -> np.ndarray:
        """Register Movici IDs for a component type with globally unique PGM IDs.

        :param component_type: PGM component type name.
        :param movici_ids: Array of Movici entity IDs.
        :returns: Array of globally unique PGM IDs.
        """
        movici_ids = np.asarray(movici_ids)
        n = len(movici_ids)

        # Allocate globally unique IDs
        pgm_ids = np.arange(self._next_id, self._next_id + n, dtype=np.int32)
        self._next_id += n

        # Initialize type mappings if needed
        if component_type not in self._movici_to_pgm:
            self._movici_to_pgm[component_type] = {}
            self._pgm_to_movici[component_type] = {}

        # Store mappings
        for movici_id, pgm_id in zip(movici_ids, pgm_ids):
            self._movici_to_pgm[component_type][int(movici_id)] = int(pgm_id)
            self._pgm_to_movici[component_type][int(pgm_id)] = int(movici_id)

        return pgm_ids

    def get_pgm_ids(self, component_type: str, movici_ids: npt.ArrayLike) -> np.ndarray:
        """Get PGM IDs for a component type.

        :param component_type: PGM component type name.
        :param movici_ids: Array of Movici entity IDs.
        :returns: Array of PGM IDs.
        :raises ValueError: If component type not registered or IDs not found.
        """
        movici_ids = np.asarray(movici_ids)
        if component_type not in self._movici_to_pgm:
            raise ValueError(f"Component type not registered: {component_type}")

        mapping = self._movici_to_pgm[component_type]
        pgm_ids = np.array([mapping.get(int(mid), -1) for mid in movici_ids], dtype=np.int32)

        if np.any(pgm_ids == -1):
            missing = movici_ids[pgm_ids == -1]
            raise ValueError(f"Movici IDs not registered for {component_type}: {missing}")

        return pgm_ids

    def get_movici_ids(self, component_type: str, pgm_ids: npt.ArrayLike) -> np.ndarray:
        """Get Movici IDs for a component type.

        :param component_type: PGM component type name.
        :param pgm_ids: Array of PGM IDs.
        :returns: Array of Movici entity IDs.
        :raises ValueError: If component type not registered or IDs not found.
        """
        pgm_ids = np.asarray(pgm_ids)
        if component_type not in self._pgm_to_movici:
            raise ValueError(f"Component type not registered: {component_type}")

        mapping = self._pgm_to_movici[component_type]
        movici_ids = np.array([mapping.get(int(pid), -1) for pid in pgm_ids], dtype=np.int32)

        if np.any(movici_ids == -1):
            missing = pgm_ids[movici_ids == -1]
            raise ValueError(f"PGM IDs not found for {component_type}: {missing}")

        return movici_ids

    def get_movici_indices(
        self, component_type: str, pgm_ids: npt.ArrayLike, target_ids: npt.ArrayLike
    ) -> np.ndarray:
        """Get entity array indices for a component type.

        :param component_type: PGM component type name.
        :param pgm_ids: Array of PGM IDs.
        :param target_ids: Array of Movici entity IDs.
        :returns: Array of indices into target_ids.
        """
        movici_ids = self.get_movici_ids(component_type, pgm_ids)
        target_index = Index()
        target_index.add_ids(target_ids)
        indices = target_index[movici_ids]
        if np.any(indices == -1):
            missing = movici_ids[indices == -1]
            raise ValueError(f"Movici IDs not found in target: {missing}")
        return indices

    def clear(self) -> None:
        """Clear all ID mappings and reset counter."""
        self._next_id = 0
        self._movici_to_pgm.clear()
        self._pgm_to_movici.clear()
