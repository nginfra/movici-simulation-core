import dataclasses
import typing as t

import numpy as np
import numpy.typing as npt


@dataclasses.dataclass(frozen=True)
class IndexParams:
    block_from: np.ndarray
    block_to: np.ndarray
    block_offset: np.ndarray


# For indexing we make use of the fact that most of the time, ids are arranged in blocks of
# contiguous ids (eg [1,2,3,7,8,9]). This Index groups the ids in these blocks and stores the
# offset of the block relative to the id array. For the above example we get two blocks. The
# first block has offset=0,begin=1,end=4 and the second block has offset=3,begin=7,end=10. the
# value for end is chosen as max+1 so that end-begin gives the block size. We now only have to
# find the block wherein the id resides. This operation is O(n) where n is the number of
# contiguous blocks. After we have found the right block, we can calculate idx = id - begin +
# offset.


class Index:
    """ """

    params: IndexParams
    ids: t.Optional[np.ndarray] = None

    def __init__(self, ids: t.Optional[npt.ArrayLike] = None, raise_on_invalid=False):
        self.raise_on_invalid = raise_on_invalid
        self.add_ids(np.array([], dtype=int) if ids is None or not len(ids) else ids)

    def set_ids(self, ids: npt.ArrayLike):
        if len(self.ids):
            if not np.array_equal(self.ids, ids):
                raise ValueError("Cannot change entity ids")
        self.add_ids(ids)

    def add_ids(self, ids: npt.ArrayLike) -> None:
        if self.ids is not None and (ids is None or len(ids) == 0):
            return
        ids = np.asarray(ids, dtype=int)
        candidates = np.concatenate((self.ids, ids)) if self.ids is not None else ids
        uniqs, counts = np.unique(candidates, return_counts=True)
        if np.any(counts != 1):
            raise ValueError(
                "Duplicate entries detected: " + ", ".join(str(i) for i in uniqs[counts != 1])
            )
        self.ids = candidates
        self.params = build_index(self.ids)

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, item: t.Union[int, npt.ArrayLike]) -> t.Union[int, np.ndarray]:
        if isinstance(item, t.Iterable):
            return self.query_indices(item)
        return self.query_idx(item)

    def query_idx(self, item: int):
        rv = query_idx(
            self.params.block_from, self.params.block_to, self.params.block_offset, item
        )
        if self.raise_on_invalid and rv == -1:
            raise ValueError(f"id {item} not found in index")
        return rv

    def query_indices(self, item: npt.ArrayLike):
        item = np.asarray(item, dtype=int)
        rv = query_indices(
            self.params.block_from, self.params.block_to, self.params.block_offset, item
        )
        if self.raise_on_invalid and np.any(invalid := (rv == -1)):
            raise ValueError(f"ids {item[invalid]} not found in index")
        return rv


# If the number of blocks is large, we may benefit from using numba. However, if the number of
# blocks is large, this is not the right approach for Index and we'd probably want to use a
# different Index data structure, such as pandas.Index


def query_indices(block_from, block_to, block_offset, ids):
    result = np.empty_like(ids, dtype=np.int64)
    for i, ident in enumerate(ids):
        result[i] = query_idx(block_from, block_to, block_offset, ident)
    return result


def query_idx(block_from, block_to, block_offset, ident):
    for begin, end, offset in zip(block_from, block_to, block_offset):
        if ident < begin:
            break
        if end < ident:
            continue
        return ident - begin + offset
    return -1


def build_index(ids: npt.ArrayLike):
    """builds indexing parameters for an ids array. For every block of contiguous ids
    it notes the range of ids in that block and the starting position of that block in
    the id array.
    """
    if len(ids) == 0:
        return IndexParams(
            np.empty((0,), dtype=np.int32),
            np.empty((0,), dtype=np.int32),
            np.empty((0,), dtype=np.int32),
        )
    ids = np.asarray(ids)

    # splits are the locations where a new block begins (other than 0)
    splits = np.flatnonzero(np.diff(ids) != 1) + 1

    # splits together with a leading 0 are the offsets (starting positions) of the blocks in
    # the id array
    block_offsets = np.concatenate((np.zeros((1,), dtype=np.int32), splits))

    block_first_values = ids[block_offsets]

    block_last_values = ids[
        np.concatenate((splits, np.full((1,), fill_value=len(ids), dtype=np.int32))) - 1
    ]

    as_sorted = np.argsort(block_first_values)

    return IndexParams(
        block_first_values[as_sorted], block_last_values[as_sorted], block_offsets[as_sorted]
    )
