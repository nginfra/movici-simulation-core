"""Tests for IdMapper"""

import numpy as np

from movici_simulation_core.models.drinking_water.id_mapper import IdMapper


class TestIdMapper:
    def test_register_nodes(self):
        mapper = IdMapper()
        movici_ids = np.array([100, 200, 300])

        wntr_names = mapper.register_nodes(movici_ids, prefix="J")

        assert wntr_names == ["J100", "J200", "J300"]
        assert mapper.get_wntr_name(100) == "J100"

    def test_register_links(self):
        mapper = IdMapper()
        movici_ids = np.array([1, 2, 3])

        wntr_names = mapper.register_links(movici_ids, prefix="P")

        assert wntr_names == ["P1", "P2", "P3"]
        assert mapper.get_wntr_name(1) == "P1"

    def test_register_duplicate_ids(self):
        mapper = IdMapper()
        movici_ids = np.array([100, 100, 200])

        wntr_names = mapper.register_nodes(movici_ids, prefix="J")

        # Should return same name for duplicate IDs
        assert wntr_names == ["J100", "J100", "J200"]
