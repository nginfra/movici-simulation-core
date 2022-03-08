import dataclasses
import typing as t

import numba
import numpy as np
import numpy.typing as npt


@dataclasses.dataclass(frozen=True)
class IndexParams:
    block_from: np.ndarray
    block_to: np.ndarray
    block_offset: np.ndarray

    def block_count(self):
        return len(self.block_from)


# For indexing we make use of the fact that most of the time, ids are arranged in blocks of
# contiguous ids (eg [1,2,3,7,8,9]). This Index groups the ids in these blocks and stores the
# offset of the block relative to the id array. For the above example we get two blocks. The
# first block has offset=0,begin=1,end=3 and the second block has offset=3,begin=7,end=9. We now
# only have to find the block wherein the id resides. This operation is O(log(n)) (binary search)
# where n is the number of contiguous blocks. After we have found the right block, we can calculate
# idx = id - begin + offset.


class Index:
    params: IndexParams
    ids: t.Optional[np.ndarray] = None

    def __init__(self, ids: t.Optional[npt.ArrayLike] = None, raise_on_invalid=False):
        self.raise_on_invalid = raise_on_invalid
        self.add_ids(np.array([], dtype=int) if ids is None or not len(ids) else ids)

    def block_count(self):
        return self.params.block_count()

    def set_ids(self, ids: npt.ArrayLike):
        if len(self.ids):
            if not np.array_equal(self.ids, ids):
                raise ValueError("Cannot change entity ids")
        self.add_ids(ids)

    def add_ids(self, ids: npt.ArrayLike) -> None:
        if self.ids is not None and (ids is None or len(ids) == 0):
            return
        self.ids = self.ensure_unique(ids)
        self.params = build_index(self.ids)

    def ensure_unique(self, ids: npt.ArrayLike):
        ids = np.asarray(ids, dtype=int)
        candidates = np.concatenate((self.ids, ids)) if self.ids is not None else ids
        uniqs, counts = np.unique(candidates, return_counts=True)
        if np.any(counts != 1):
            raise ValueError(
                "Duplicate entries detected: " + ", ".join(str(i) for i in uniqs[counts != 1])
            )
        return candidates

    def __len__(self) -> int:
        return len(self.ids)

    def __getitem__(self, item: t.Union[int, npt.ArrayLike]) -> t.Union[int, np.ndarray]:
        if isinstance(item, (t.Sequence, np.ndarray)):
            rv = self.query_indices(item)
        else:
            rv = self.query_idx(item)

        if self.raise_on_invalid:
            if np.any(invalid := (rv == -1)):
                if isinstance(rv, np.ndarray) and rv.shape:
                    raise ValueError(f"ids {np.asarray(item)[invalid]} not found in index")
                raise ValueError(f"id {int(item)} not found in index")
        return rv

    def query_idx(self, item: int):
        return query_idx(
            self.params.block_from, self.params.block_to, self.params.block_offset, item
        )

    def query_indices(self, item: npt.ArrayLike):
        item = np.asarray(item, dtype=int)
        return query_indices(
            self.params.block_from, self.params.block_to, self.params.block_offset, item
        )


@numba.njit
def query_indices(block_from, block_to, block_offset, ids):
    result = np.empty_like(ids, dtype=np.int64)
    for i, ident in enumerate(ids):
        result[i] = query_idx(block_from, block_to, block_offset, ident)
    return result


@numba.njit
def query_idx(block_from, block_to, block_offset, ident):
    not_found = -1
    if len(block_to) == 0:
        return not_found

    candidate_block = np.searchsorted(block_to, ident)

    if candidate_block < len(block_to) and block_from[candidate_block] <= ident:
        return ident - block_from[candidate_block] + block_offset[candidate_block]

    return not_found


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
