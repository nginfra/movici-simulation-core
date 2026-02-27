"""Tests for PGM ID generator."""

import numpy as np
import pytest

from movici_simulation_core.integrations.pgm.id_generator import ComponentIdManager


class TestComponentIdManager:
    """Tests for ComponentIdManager class."""

    def test_register_ids_globally_unique(self):
        """Test that IDs are globally unique across all component types."""
        manager = ComponentIdManager()

        node_pgm = manager.register_ids("node", np.array([100, 200]))
        line_pgm = manager.register_ids("line", np.array([300, 400]))

        # Nodes get 0, 1; lines get 2, 3 (globally unique)
        np.testing.assert_array_equal(node_pgm, [0, 1])
        np.testing.assert_array_equal(line_pgm, [2, 3])

    def test_get_pgm_ids_returns_registered(self):
        """Test getting PGM IDs for specific component type."""
        manager = ComponentIdManager()
        manager.register_ids("node", np.array([100, 200]))
        manager.register_ids("line", np.array([300, 400]))

        node_pgm = manager.get_pgm_ids("node", np.array([200, 100]))
        line_pgm = manager.get_pgm_ids("line", np.array([400, 300]))

        np.testing.assert_array_equal(node_pgm, [1, 0])
        np.testing.assert_array_equal(line_pgm, [3, 2])

    def test_get_movici_ids_per_type(self):
        """Test getting Movici IDs for specific component type."""
        manager = ComponentIdManager()
        manager.register_ids("node", np.array([100, 200]))
        manager.register_ids("line", np.array([300, 400]))

        node_ids = manager.get_movici_ids("node", np.array([0, 1]))
        line_ids = manager.get_movici_ids("line", np.array([3, 2]))

        np.testing.assert_array_equal(node_ids, [100, 200])
        np.testing.assert_array_equal(line_ids, [400, 300])

    @pytest.mark.parametrize("method", ["get_pgm_ids", "get_movici_ids"])
    def test_raises_on_unregistered_type(self, method):
        """Test that lookup methods raise for unregistered component type."""
        manager = ComponentIdManager()

        with pytest.raises(ValueError, match="not registered"):
            getattr(manager, method)("unknown", np.array([1]))

    def test_clear_resets_counter_and_mappings(self):
        """Test that clear resets the global counter and all mappings."""
        manager = ComponentIdManager()
        manager.register_ids("node", np.array([100]))
        manager.register_ids("line", np.array([200]))

        manager.clear()

        # After clear, IDs should start from 0 again
        new_pgm = manager.register_ids("node", np.array([300]))
        np.testing.assert_array_equal(new_pgm, [0])
