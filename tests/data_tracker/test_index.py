import numpy as np
import pytest

from movici_simulation_core.core.index import Index, IndexParams, build_index, query_idx


class TestIndex:
    def test_index(self):
        index = Index([1, 2, 3])
        assert np.all(index[[1, 3]] == [0, 2])

    def test_can_add_new_ids(self):
        index = Index([1, 2, 3])
        index.add_ids([4, 5, 6])
        assert np.all(index[2, 5] == [1, 4])

    def test_non_existing_ids(self):
        index = Index()
        assert np.all(index[[1]] == [-1])

    def test_ids_must_be_unique(self):
        with pytest.raises(ValueError) as exc:
            Index([1, 2, 1])
        assert str(exc.value) == "Duplicate entries detected: 1"

    @pytest.mark.parametrize("item", [2, np.int8(2)])
    def test_get_single(self, item):
        index = Index([1, 2])
        assert index[item] == 1

    def test_index_length(self):
        assert len(Index()) == 0


class TestBlockIndex:
    @pytest.mark.parametrize(
        "ids, expected_from, expected_to, expected_offset",
        [
            ([2, 3, 4, 8, 9, 12, 13, 14], [2, 8, 12], [4, 9, 14], [0, 3, 5]),
            ([8, 9, 2, 3, 4], [2, 8], [4, 9], [2, 0]),
        ],
    )
    def test_build_index(self, ids, expected_from, expected_to, expected_offset):
        result = build_index(ids)
        np.testing.assert_array_equal(result.block_from, expected_from)
        np.testing.assert_array_equal(result.block_to, expected_to)
        np.testing.assert_array_equal(result.block_offset, expected_offset)

    @pytest.fixture
    def params(self):
        return build_index([2, 3, 4, 8, 9, 12, 13, 14])

    @pytest.mark.parametrize("ident, idx", [(2, 0), (3, 1), (9, 4), (14, 7)])
    def test_query_idx(self, params: IndexParams, ident, idx):
        assert query_idx(params.block_from, params.block_to, params.block_offset, ident) == idx

    def test_empty_index(self):
        index = build_index([])
        assert query_idx(index.block_from, index.block_to, index.block_offset, 1) == -1

    @pytest.mark.parametrize("not_found", [-1, 0, 4, 6, 10])
    def test_not_found(self, not_found):
        index = build_index([1, 2, 7, 8, 9])
        assert query_idx(index.block_from, index.block_to, index.block_offset, not_found) == -1


@pytest.mark.parametrize("query", [[1], 1])
def test_raises_when_not_found(query):
    index = Index(raise_on_invalid=True)
    with pytest.raises(ValueError):
        _ = index[query]
