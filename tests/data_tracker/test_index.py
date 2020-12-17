import numpy as np
from movici_simulation_core.data_tracker.index import Index


def test_index():
    index = Index([1, 2, 3])
    assert np.all(index[[1, 3]] == [0, 2])


def test_can_add_new_ids():
    index = Index([1, 2, 3])
    index.add_ids([4, 5, 6])
    assert np.all(index[2, 5] == [1, 4])


def test_non_existing_ids():
    # TODO: should this raise an error?
    index = Index()
    assert np.all(index[[1]] == [-1])
