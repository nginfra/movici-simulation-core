import numpy as np
import pytest

from movici_simulation_core.ae_wrapper.id_generator import IdGenerator


@pytest.fixture
def id_generator():
    return IdGenerator()


def test_can_get_new_ids(id_generator):
    new_ids = id_generator.get_new_ids([5, 6, 7])
    assert np.array_equal(new_ids, [1, 2, 3])

    new_ids = id_generator.get_new_ids([1, 4])
    assert np.array_equal(new_ids, [4, 5])


def test_query_original_ids(id_generator):
    new_ids = id_generator.get_new_ids([5, 6, 7])
    assert np.array_equal(new_ids, [1, 2, 3])

    original_ids = id_generator.query_original_ids([2, 1])
    assert np.array_equal(original_ids, [6, 5])

    new_ids = id_generator.get_new_ids([1, 4])
    assert np.array_equal(new_ids, [4, 5])

    original_ids = id_generator.query_original_ids([4, 5])
    assert np.array_equal(original_ids, [1, 4])


def test_query_new_ids(id_generator):
    new_ids = id_generator.get_new_ids([5, 6, 7])
    assert np.array_equal(new_ids, [1, 2, 3])

    original_ids = id_generator.query_new_ids([6, 5])
    assert np.array_equal(original_ids, [2, 1])

    new_ids = id_generator.get_new_ids([1, 4])
    assert np.array_equal(new_ids, [4, 5])

    original_ids = id_generator.query_new_ids([1, 4])
    assert np.array_equal(original_ids, [4, 5])


def test_adding_same_id_twice_raises_error(id_generator):
    id_generator.get_new_ids([5])

    with pytest.raises(ValueError):
        id_generator.get_new_ids([5])

    with pytest.raises(ValueError):
        id_generator.get_new_ids([6, 6])


def test_querying_nonexistent_id_raises(id_generator):
    with pytest.raises(ValueError):
        id_generator.query_new_ids([99])

    with pytest.raises(ValueError):
        id_generator.query_original_ids([99])
