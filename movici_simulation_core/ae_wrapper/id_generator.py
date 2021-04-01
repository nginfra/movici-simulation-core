from typing import Sequence, Union

import numpy as np
from pandas.core.indexes.base import InvalidIndexError

from movici_simulation_core.data_tracker.index import Index


class IdGenerator:
    """
    Since aequilibrae has a fixed structure for ids
    we have to be able to convert between our ids and aequilibrae ids
    """

    def __init__(self):
        self.index = Index()

    def get_new_ids(self, original_ids: Union[np.ndarray, Sequence]) -> np.ndarray:
        try:
            self.index.add_ids(original_ids)
            return self.index[original_ids] + 1
        except InvalidIndexError:
            raise ValueError("Index is non unique")

    def query_new_ids(self, original_ids: Union[np.ndarray, Sequence]) -> np.ndarray:
        return self.index[original_ids] + 1

    def query_original_ids(self, new_ids: Union[np.ndarray, Sequence]) -> np.ndarray:
        if not isinstance(new_ids, np.ndarray):
            new_ids = np.array(new_ids)
        return self.index.ids[new_ids - 1]
