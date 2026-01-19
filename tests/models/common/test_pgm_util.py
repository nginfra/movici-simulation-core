"""Tests for power grid model utility functions."""

import numpy as np

from movici_simulation_core.integrations.pgm.collections import (
    LineCollection,
    NodeCollection,
)
from movici_simulation_core.models.common.pgm_util import (
    get_links_as_lines,
    merge_line_collections,
    merge_node_collections,
)


class TestMergeNodeCollections:
    """Tests for merge_node_collections function."""

    def test_merge_two_collections(self):
        """Test merging two node collections."""
        nodes1 = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )
        nodes2 = NodeCollection(
            ids=[3, 4],
            u_rated=[20000.0, 20000.0],
        )

        result = merge_node_collections(nodes1, nodes2)

        assert len(result) == 4
        np.testing.assert_array_equal(result.ids, [1, 2, 3, 4])
        np.testing.assert_array_equal(result.u_rated, [10000.0, 10000.0, 20000.0, 20000.0])

    def test_merge_preserves_order(self):
        """Test that merge preserves order (first collection first)."""
        nodes1 = NodeCollection(ids=[100], u_rated=[380000.0])
        nodes2 = NodeCollection(ids=[1, 2], u_rated=[10000.0, 10000.0])

        result = merge_node_collections(nodes1, nodes2)

        # First collection's nodes should come first
        assert result.ids[0] == 100
        assert result.u_rated[0] == 380000.0

    def test_merge_empty_with_nonempty(self):
        """Test merging empty collection with non-empty."""
        nodes1 = NodeCollection(ids=[], u_rated=[])
        nodes2 = NodeCollection(ids=[1, 2], u_rated=[10000.0, 10000.0])

        result = merge_node_collections(nodes1, nodes2)

        assert len(result) == 2
        np.testing.assert_array_equal(result.ids, [1, 2])


class TestMergeLineCollections:
    """Tests for merge_line_collections function."""

    def test_merge_two_collections(self):
        """Test merging two line collections."""
        lines1 = LineCollection(
            ids=[1, 2],
            from_node=[10, 20],
            to_node=[11, 21],
            r1=[0.1, 0.2],
            x1=[0.05, 0.1],
            c1=[1e-9, 2e-9],
            tan1=[0.0, 0.0],
        )
        lines2 = LineCollection(
            ids=[3],
            from_node=[30],
            to_node=[31],
            r1=[0.3],
            x1=[0.15],
            c1=[3e-9],
            tan1=[0.01],
        )

        result = merge_line_collections(lines1, lines2)

        assert len(result) == 3
        np.testing.assert_array_equal(result.ids, [1, 2, 3])
        np.testing.assert_array_equal(result.from_node, [10, 20, 30])
        np.testing.assert_array_equal(result.to_node, [11, 21, 31])
        np.testing.assert_array_equal(result.r1, [0.1, 0.2, 0.3])

    def test_merge_none_with_collection(self):
        """Test merging None with a collection returns the collection."""
        lines = LineCollection(
            ids=[1],
            from_node=[10],
            to_node=[11],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
        )

        result = merge_line_collections(None, lines)

        assert result is lines

    def test_merge_collection_with_none(self):
        """Test merging collection with None returns the collection."""
        lines = LineCollection(
            ids=[1],
            from_node=[10],
            to_node=[11],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
        )

        result = merge_line_collections(lines, None)

        assert result is lines

    def test_merge_none_with_none(self):
        """Test merging None with None returns None."""
        result = merge_line_collections(None, None)

        assert result is None

    def test_merge_preserves_status(self):
        """Test that merge preserves status arrays."""
        lines1 = LineCollection(
            ids=[1],
            from_node=[10],
            to_node=[11],
            from_status=[1],
            to_status=[0],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
        )
        lines2 = LineCollection(
            ids=[2],
            from_node=[20],
            to_node=[21],
            from_status=[0],
            to_status=[1],
            r1=[0.2],
            x1=[0.1],
            c1=[2e-9],
            tan1=[0.0],
        )

        result = merge_line_collections(lines1, lines2)

        np.testing.assert_array_equal(result.from_status, [1, 0])
        np.testing.assert_array_equal(result.to_status, [0, 1])

    def test_merge_preserves_rated_current(self):
        """Test that merge preserves rated current including infinity."""
        lines1 = LineCollection(
            ids=[1],
            from_node=[10],
            to_node=[11],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
            i_n=[100.0],
        )
        lines2 = LineCollection(
            ids=[2],
            from_node=[20],
            to_node=[21],
            r1=[0.2],
            x1=[0.1],
            c1=[2e-9],
            tan1=[0.0],
            i_n=[np.inf],
        )

        result = merge_line_collections(lines1, lines2)

        assert result.i_n[0] == 100.0
        assert np.isinf(result.i_n[1])


class MockAttribute:
    """Mock attribute for testing."""

    def __init__(self, array, initialized=None, length=None):
        self._array = np.array(array) if len(array) > 0 else np.array([], dtype=np.int8)
        self._initialized = initialized if initialized is not None else len(array) > 0
        # Length can be specified separately for uninitialized attributes
        self._length = length if length is not None else len(self._array)

    @property
    def array(self):
        return self._array

    def is_initialized(self):
        return self._initialized

    def __len__(self):
        return self._length


class TestGetLinksAsLines:
    """Tests for get_links_as_lines function."""

    def test_creates_low_impedance_lines(self):
        """Test that links are converted to low-impedance lines."""

        # Create a mock link entity
        class MockLinkEntity:
            class MockIndex:
                ids = np.array([1, 2], dtype=np.int32)

            index = MockIndex()
            from_node_id = MockAttribute([100, 200])
            to_node_id = MockAttribute([101, 201])
            # Not initialized but length=2 to match entity size
            from_status = MockAttribute([], initialized=False, length=2)
            to_status = MockAttribute([], initialized=False, length=2)

        entity = MockLinkEntity()
        result = get_links_as_lines(entity)

        assert len(result) == 2
        np.testing.assert_array_equal(result.ids, [1, 2])
        np.testing.assert_array_equal(result.from_node, [100, 200])
        np.testing.assert_array_equal(result.to_node, [101, 201])

        # Check low impedance values
        assert all(result.r1 == 1e-6)
        assert all(result.x1 == 1e-6)
        assert all(result.c1 == 1e-12)
        assert all(result.tan1 == 0.0)
        assert all(np.isinf(result.i_n))

    def test_default_status_is_enabled(self):
        """Test that default status is enabled when not provided."""

        class MockLinkEntity:
            class MockIndex:
                ids = np.array([1], dtype=np.int32)

            index = MockIndex()
            from_node_id = MockAttribute([100])
            to_node_id = MockAttribute([101])
            # Not initialized but length=1 to match entity size
            from_status = MockAttribute([], initialized=False, length=1)
            to_status = MockAttribute([], initialized=False, length=1)

        entity = MockLinkEntity()
        result = get_links_as_lines(entity)

        # Default status should be 1 (enabled)
        np.testing.assert_array_equal(result.from_status, [1])
        np.testing.assert_array_equal(result.to_status, [1])

    def test_respects_provided_status(self):
        """Test that provided status values are used."""

        class MockLinkEntity:
            class MockIndex:
                ids = np.array([1, 2], dtype=np.int32)

            index = MockIndex()
            from_node_id = MockAttribute([100, 200])
            to_node_id = MockAttribute([101, 201])
            from_status = MockAttribute([1, 0])
            to_status = MockAttribute([0, 1])

        entity = MockLinkEntity()
        result = get_links_as_lines(entity)

        np.testing.assert_array_equal(result.from_status, [1, 0])
        np.testing.assert_array_equal(result.to_status, [0, 1])
