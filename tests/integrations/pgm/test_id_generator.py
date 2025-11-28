"""Tests for PGM ID generator."""

import numpy as np
import pytest

from movici_simulation_core.integrations.pgm.id_generator import (
    ComponentIdManager,
    IdGenerator,
)


class TestIdGenerator:
    """Tests for IdGenerator class."""

    def test_register_ids_returns_sequential(self):
        """Test that register_ids returns sequential PGM IDs."""
        gen = IdGenerator()
        movici_ids = np.array([100, 200, 300])

        pgm_ids = gen.register_ids(movici_ids)

        np.testing.assert_array_equal(pgm_ids, [0, 1, 2])

    def test_get_pgm_ids_after_register(self):
        """Test that get_pgm_ids returns same IDs as register_ids."""
        gen = IdGenerator()
        movici_ids = np.array([100, 200])

        registered = gen.register_ids(movici_ids)
        retrieved = gen.get_pgm_ids(movici_ids)

        np.testing.assert_array_equal(registered, retrieved)

    def test_get_pgm_ids_returns_registered(self):
        """Test that get_pgm_ids returns previously registered IDs."""
        gen = IdGenerator()
        movici_ids = np.array([100, 200, 300])
        gen.register_ids(movici_ids)

        pgm_ids = gen.get_pgm_ids(np.array([200, 100]))

        np.testing.assert_array_equal(pgm_ids, [1, 0])

    def test_get_pgm_ids_raises_on_unregistered(self):
        """Test that get_pgm_ids raises ValueError for unregistered IDs."""
        gen = IdGenerator()
        gen.register_ids(np.array([100, 200]))

        with pytest.raises(ValueError, match="not registered"):
            gen.get_pgm_ids(np.array([999]))

    def test_get_movici_ids_returns_original(self):
        """Test that get_movici_ids returns original Movici IDs."""
        gen = IdGenerator()
        movici_ids = np.array([100, 200, 300])
        gen.register_ids(movici_ids)

        result = gen.get_movici_ids(np.array([1, 2, 0]))

        np.testing.assert_array_equal(result, [200, 300, 100])

    def test_get_movici_ids_raises_on_invalid(self):
        """Test that get_movici_ids raises ValueError for invalid PGM IDs."""
        gen = IdGenerator()
        gen.register_ids(np.array([100, 200]))

        with pytest.raises(ValueError, match="out of range"):
            gen.get_movici_ids(np.array([99]))

    def test_get_movici_indices(self):
        """Test that get_movici_indices returns correct array indices."""
        gen = IdGenerator()
        movici_ids = np.array([100, 200, 300])
        gen.register_ids(movici_ids)

        # Target array has different order
        target_ids = np.array([300, 100, 200])
        pgm_ids = np.array([0, 1, 2])  # Corresponds to movici 100, 200, 300

        indices = gen.get_movici_indices(pgm_ids, target_ids)

        # Index 0 (pgm) -> movici 100 -> target index 1
        # Index 1 (pgm) -> movici 200 -> target index 2
        # Index 2 (pgm) -> movici 300 -> target index 0
        np.testing.assert_array_equal(indices, [1, 2, 0])

    def test_len_returns_registered_count(self):
        """Test that len returns number of registered IDs."""
        gen = IdGenerator()
        assert len(gen) == 0

        gen.register_ids(np.array([100, 200, 300]))
        assert len(gen) == 3

    def test_clear_removes_all_ids(self):
        """Test that clear removes all registered IDs."""
        gen = IdGenerator()
        gen.register_ids(np.array([100, 200]))
        assert len(gen) == 2

        gen.clear()
        assert len(gen) == 0


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

    def test_get_pgm_ids_raises_on_unregistered_type(self):
        """Test that get_pgm_ids raises for unregistered component type."""
        manager = ComponentIdManager()

        with pytest.raises(ValueError, match="not registered"):
            manager.get_pgm_ids("unknown", np.array([1]))

    def test_get_movici_ids_raises_on_unregistered_type(self):
        """Test that get_movici_ids raises for unregistered component type."""
        manager = ComponentIdManager()

        with pytest.raises(ValueError, match="not registered"):
            manager.get_movici_ids("unknown", np.array([1]))

    def test_clear_resets_counter_and_mappings(self):
        """Test that clear resets the global counter and all mappings."""
        manager = ComponentIdManager()
        manager.register_ids("node", np.array([100]))
        manager.register_ids("line", np.array([200]))

        manager.clear()

        # After clear, IDs should start from 0 again
        new_pgm = manager.register_ids("node", np.array([300]))
        np.testing.assert_array_equal(new_pgm, [0])
