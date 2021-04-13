import typing as t

import numpy as np
import numpy.typing as npt
import pandas as pd


class Index:
    index: pd.Index

    def __init__(self, ids: t.Optional[npt.ArrayLike] = None):
        self.ids = np.asarray([], dtype=int)
        self.index = pd.Index([])
        if ids is not None:
            self.add_ids(ids)

    def set_ids(self, ids: npt.ArrayLike):
        if len(self.ids):
            if not np.array_equal(self.ids, ids):
                raise ValueError("Cannot change entity ids")
        self.add_ids(ids)

    def add_ids(self, ids: npt.ArrayLike) -> None:
        self.ids = np.concatenate((self.ids, ids))
        self.index = pd.Index(self.ids)

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, item: t.Union[int, t.Sequence[int]]) -> np.ndarray:
        return self.index.get_indexer(item)
