"""ID mapping between Movici entity IDs and WNTR node/link names"""

from __future__ import annotations

import typing as t

import numpy as np


class IdMapper:
    """Maps between Movici integer IDs and WNTR string names

    Unlike aequilibrae, WNTR uses flexible string IDs, so we can use
    simpler string conversion. We use the format 'n{id}' for nodes
    and 'l{id}' for links to avoid conflicts.
    """

    def __init__(self):
        # Movici ID -> WNTR name
        self.movici_to_wntr: t.Dict[int, str] = {}
        # WNTR name -> Movici ID
        self.wntr_to_movici: t.Dict[str, int] = {}
        # Track entity type for each WNTR name
        self.entity_types: t.Dict[str, str] = {}

    def register_nodes(self, movici_ids: np.ndarray, entity_type: str = "junction") -> t.List[str]:
        """Register node IDs and return corresponding WNTR names

        :param movici_ids: Array of Movici entity IDs
        :param entity_type: Type of entity (junction, tank, reservoir)
        :return: List of WNTR node names
        """
        wntr_names = []
        for movici_id in movici_ids:
            movici_id = int(movici_id)
            if movici_id in self.movici_to_wntr:
                wntr_name = self.movici_to_wntr[movici_id]
            else:
                wntr_name = f"n{movici_id}"
                self.movici_to_wntr[movici_id] = wntr_name
                self.wntr_to_movici[wntr_name] = movici_id
                self.entity_types[wntr_name] = entity_type
            wntr_names.append(wntr_name)
        return wntr_names

    def register_links(self, movici_ids: np.ndarray, entity_type: str = "pipe") -> t.List[str]:
        """Register link IDs and return corresponding WNTR names

        :param movici_ids: Array of Movici entity IDs
        :param entity_type: Type of entity (pipe, pump, valve)
        :return: List of WNTR link names
        """
        wntr_names = []
        for movici_id in movici_ids:
            movici_id = int(movici_id)
            if movici_id in self.movici_to_wntr:
                wntr_name = self.movici_to_wntr[movici_id]
            else:
                wntr_name = f"l{movici_id}"
                self.movici_to_wntr[movici_id] = wntr_name
                self.wntr_to_movici[wntr_name] = movici_id
                self.entity_types[wntr_name] = entity_type
            wntr_names.append(wntr_name)
        return wntr_names

    def get_wntr_name(self, movici_id: int) -> str:
        """Get WNTR name for a Movici ID

        :param movici_id: Movici entity ID
        :return: WNTR name string
        """
        return self.movici_to_wntr[movici_id]

    def get_movici_id(self, wntr_name: str) -> int:
        """Get Movici ID for a WNTR name

        :param wntr_name: WNTR name string
        :return: Movici entity ID
        """
        return self.wntr_to_movici[wntr_name]

    def get_movici_ids(self, wntr_names: t.Iterable[str]) -> np.ndarray:
        """Get Movici IDs for multiple WNTR names

        :param wntr_names: Iterable of WNTR name strings
        :return: Array of Movici entity IDs
        """
        return np.array([self.wntr_to_movici[name] for name in wntr_names])

    def get_entity_type(self, wntr_name: str) -> str:
        """Get entity type for a WNTR name

        :param wntr_name: WNTR name string
        :return: Entity type string
        """
        return self.entity_types.get(wntr_name, "unknown")

    def has_movici_id(self, movici_id: int) -> bool:
        """Check if a Movici ID is registered

        :param movici_id: Movici entity ID
        :return: True if registered
        """
        return movici_id in self.movici_to_wntr

    def has_wntr_name(self, wntr_name: str) -> bool:
        """Check if a WNTR name is registered

        :param wntr_name: WNTR name string
        :return: True if registered
        """
        return wntr_name in self.wntr_to_movici
