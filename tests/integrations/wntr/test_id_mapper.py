"""Tests for IdMapper"""

import numpy as np
import pytest

from movici_simulation_core.integrations.wntr.id_mapper import IdMapper


class TestIdMapper:
    def test_register_nodes(self):
        mapper = IdMapper()
        movici_ids = np.array([100, 200, 300])

        wntr_names = mapper.register_nodes(movici_ids, entity_type="junction")

        assert wntr_names == ["n100", "n200", "n300"]
        assert mapper.get_wntr_name(100) == "n100"
        assert mapper.get_movici_id("n100") == 100
        assert mapper.get_entity_type("n100") == "junction"

    def test_register_links(self):
        mapper = IdMapper()
        movici_ids = np.array([1, 2, 3])

        wntr_names = mapper.register_links(movici_ids, entity_type="pipe")

        assert wntr_names == ["l1", "l2", "l3"]
        assert mapper.get_wntr_name(1) == "l1"
        assert mapper.get_movici_id("l1") == 1
        assert mapper.get_entity_type("l1") == "pipe"

    def test_register_duplicate_ids(self):
        mapper = IdMapper()
        movici_ids = np.array([100, 100, 200])

        wntr_names = mapper.register_nodes(movici_ids)

        # Should return same name for duplicate IDs
        assert wntr_names == ["n100", "n100", "n200"]

    def test_get_movici_ids(self):
        mapper = IdMapper()
        movici_ids = np.array([10, 20, 30])
        wntr_names = mapper.register_nodes(movici_ids)

        result = mapper.get_movici_ids(wntr_names)

        np.testing.assert_array_equal(result, movici_ids)

    def test_has_methods(self):
        mapper = IdMapper()
        mapper.register_nodes(np.array([100]))

        assert mapper.has_movici_id(100)
        assert not mapper.has_movici_id(999)
        assert mapper.has_wntr_name("n100")
        assert not mapper.has_wntr_name("n999")
