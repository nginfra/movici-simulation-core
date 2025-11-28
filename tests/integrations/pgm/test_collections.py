"""Tests for PGM collections."""

import numpy as np

from movici_simulation_core.integrations.pgm.collections import (
    LineCollection,
    LoadCollection,
    NodeCollection,
    NodeResult,
    SourceCollection,
)


class TestNodeCollection:
    """Tests for NodeCollection."""

    def test_create_with_arrays(self):
        """Test creating collection with numpy arrays."""
        ids = np.array([1, 2, 3], dtype=np.int32)
        u_rated = np.array([10000.0, 20000.0, 10000.0])

        nodes = NodeCollection(ids=ids, u_rated=u_rated)

        np.testing.assert_array_equal(nodes.ids, ids)
        np.testing.assert_array_equal(nodes.u_rated, u_rated)

    def test_create_with_lists(self):
        """Test creating collection with Python lists."""
        nodes = NodeCollection(ids=[1, 2, 3], u_rated=[10000.0, 20000.0, 10000.0])

        assert len(nodes) == 3
        assert nodes.ids.dtype == np.int32
        assert nodes.u_rated.dtype == np.float64

    def test_create_with_defaults(self):
        """Test creating collection with default values."""
        nodes = NodeCollection(ids=[1, 2])

        assert len(nodes) == 2
        np.testing.assert_array_equal(nodes.u_rated, [0.0, 0.0])


class TestLineCollection:
    """Tests for LineCollection."""

    def test_create_complete(self):
        """Test creating line collection with all values."""
        lines = LineCollection(
            ids=[1, 2],
            from_node=[10, 20],
            to_node=[11, 21],
            from_status=[1, 1],
            to_status=[1, 0],
            r1=[0.1, 0.2],
            x1=[0.3, 0.4],
            c1=[1e-9, 2e-9],
            tan1=[0.01, 0.02],
            i_n=[100.0, 200.0],
        )

        assert len(lines) == 2
        np.testing.assert_array_equal(lines.from_status, [1, 1])
        np.testing.assert_array_equal(lines.to_status, [1, 0])

    def test_default_status_is_enabled(self):
        """Test that default status is enabled (1)."""
        lines = LineCollection(ids=[1, 2])

        np.testing.assert_array_equal(lines.from_status, [1, 1])
        np.testing.assert_array_equal(lines.to_status, [1, 1])

    def test_default_rated_current_is_inf(self):
        """Test that default rated current is infinity."""
        lines = LineCollection(ids=[1])

        assert np.isinf(lines.i_n[0])


class TestLoadCollection:
    """Tests for LoadCollection."""

    def test_create_complete(self):
        """Test creating load collection with all values."""
        loads = LoadCollection(
            ids=[1, 2],
            node=[10, 20],
            status=[1, 1],
            type=[0, 1],  # const_power, const_impedance
            p_specified=[1000.0, 2000.0],
            q_specified=[100.0, 200.0],
        )

        assert len(loads) == 2
        np.testing.assert_array_equal(loads.p_specified, [1000.0, 2000.0])

    def test_default_type_is_const_power(self):
        """Test that default load type is const_power (0)."""
        loads = LoadCollection(ids=[1, 2])

        np.testing.assert_array_equal(loads.type, [0, 0])


class TestSourceCollection:
    """Tests for SourceCollection."""

    def test_create_with_defaults(self):
        """Test creating source with default values."""
        sources = SourceCollection(ids=[1], node=[10])

        assert len(sources) == 1
        assert sources.u_ref[0] == 1.0  # 1.0 p.u. default
        assert sources.u_ref_angle[0] == 0.0
        assert sources.sk[0] == 1e10  # Very large default
        assert sources.rx_ratio[0] == 0.1


class TestNodeResult:
    """Tests for NodeResult."""

    def test_create_with_results(self):
        """Test creating node result with calculation output."""
        result = NodeResult(
            ids=[1, 2],
            u_pu=[1.01, 0.99],
            u_angle=[0.0, -0.02],
            u=[10100.0, 9900.0],
            p=[1000.0, -500.0],
            q=[100.0, -50.0],
        )

        assert len(result) == 2
        np.testing.assert_array_equal(result.u_pu, [1.01, 0.99])
