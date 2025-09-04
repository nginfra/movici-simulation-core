import numpy as np
import numpy.typing as npt

from movici_simulation_core.core import Index


class IdGenerator:
    """
    Since aequilibrae has a fixed structure for ids
    we have to be able to convert between our ids and aequilibrae ids
    """

    def __init__(self) -> None:
        self.index = Index()

    def get_new_ids(self, original_ids: npt.ArrayLike) -> np.ndarray:
        self.index.add_ids(original_ids)
        return self.index[original_ids] + 1

    def query_new_ids(self, original_ids: npt.ArrayLike) -> np.ndarray:
        index = self.index[original_ids]
        if np.any(index == -1):
            raise ValueError(f"Original ids {original_ids} non-existent in index")
        return index + 1

    def query_original_ids(self, new_ids: npt.ArrayLike) -> np.ndarray:
        if not isinstance(new_ids, np.ndarray):
            new_ids = np.array(new_ids)
        try:
            return self.index.ids[new_ids - 1]
        except IndexError:
            raise ValueError(f"New ids {new_ids} non-existent in index")
