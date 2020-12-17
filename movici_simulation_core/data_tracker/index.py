import typing as t

import numpy as np
import pandas as pd


class Index:
    index: pd.Index

    def __init__(self, ids: t.Union[None, np.ndarray, t.Sequence] = None):
        self.ids = np.asarray([], dtype=int)
        self.index = pd.Index([])
        if ids is not None:
            self.add_ids(ids)

    def add_ids(self, ids: np.ndarray) -> None:
        self.ids = np.concatenate((self.ids, ids))
        self.index = pd.Index(self.ids)

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, item) -> np.ndarray:
        return self.index.get_indexer(item)
