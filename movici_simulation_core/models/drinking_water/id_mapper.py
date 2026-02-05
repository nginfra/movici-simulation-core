"""ID mapping between Movici entity IDs and WNTR node/link names"""

from __future__ import annotations

import typing as t

import numpy as np


class IdMapper:
    """Maps between Movici integer IDs and WNTR string names.

    Each processor registers its entities with a type-specific prefix
    (e.g. ``"J"`` for junctions, ``"P"`` for pipes), producing WNTR
    names like ``"J5"`` or ``"P101"``.
    """

    def __init__(self):
        # Movici ID -> WNTR name
        self.movici_to_wntr: t.Dict[int, str] = {}
        # WNTR name -> Movici ID
        self.wntr_to_movici: t.Dict[str, int] = {}

    def _register_ids(self, movici_ids: np.ndarray, prefix: str) -> t.List[str]:
        """Register IDs and return corresponding WNTR names.

        :param movici_ids: Array of Movici entity IDs
        :param prefix: Prefix for WNTR names (e.g. ``"J"``, ``"P"``)
        :return: List of WNTR names
        """
        wntr_names = []
        for movici_id in movici_ids:
            movici_id = int(movici_id)
            if movici_id not in self.movici_to_wntr:
                wntr_name = f"{prefix}{movici_id}"
                self.movici_to_wntr[movici_id] = wntr_name
                self.wntr_to_movici[wntr_name] = movici_id
            wntr_names.append(self.movici_to_wntr[movici_id])
        return wntr_names

    def register_nodes(self, movici_ids: np.ndarray, prefix: str = "n") -> t.List[str]:
        """Register node IDs and return corresponding WNTR names.

        :param movici_ids: Array of Movici entity IDs
        :param prefix: Prefix for WNTR names (e.g. ``"J"`` for junctions)
        :return: List of WNTR node names
        """
        return self._register_ids(movici_ids, prefix)

    def register_links(self, movici_ids: np.ndarray, prefix: str = "l") -> t.List[str]:
        """Register link IDs and return corresponding WNTR names.

        :param movici_ids: Array of Movici entity IDs
        :param prefix: Prefix for WNTR names (e.g. ``"P"`` for pipes)
        :return: List of WNTR link names
        """
        return self._register_ids(movici_ids, prefix)

    def get_wntr_name(self, movici_id: int) -> str:
        """Get WNTR name for a Movici ID.

        :param movici_id: Movici entity ID
        :return: WNTR name string
        """
        return self.movici_to_wntr[movici_id]
