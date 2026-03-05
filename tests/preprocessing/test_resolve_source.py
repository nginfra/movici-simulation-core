"""Tests for resolve_source and MultiEntitySource."""

import pytest

from movici_simulation_core.preprocessing.data_sources import (
    DataSource,
    MultiEntitySource,
    resolve_source,
)


class DummySource(DataSource):
    def get_attribute(self, name):
        return []

    def __len__(self):
        return 0


class DummyMultiSource(MultiEntitySource):
    def __init__(self, entity_types):
        self._entity_types = entity_types
        self._sources = {et: DummySource() for et in entity_types}

    def keys(self):
        return iter(self._entity_types)

    def __getitem__(self, entity_type):
        if entity_type not in self._sources:
            raise KeyError(entity_type)
        return self._sources[entity_type]

    def __contains__(self, entity_type):
        return entity_type in self._sources


class TestResolveSource:
    def test_resolve_normal_source(self):
        source = DummySource()
        result = resolve_source("my_source", {"my_source": source})
        assert result is source

    def test_resolve_dot_notation(self):
        multi = DummyMultiSource(["nodes", "edges"])
        result = resolve_source("network.nodes", {"network": multi})
        assert result is multi["nodes"]

    def test_missing_source_raises_value_error(self):
        with pytest.raises(ValueError, match="not available"):
            resolve_source("missing", {})

    def test_missing_base_in_dot_notation_raises_value_error(self):
        with pytest.raises(ValueError, match="not available"):
            resolve_source("missing.nodes", {})

    def test_dot_on_non_multi_raises_type_error(self):
        source = DummySource()
        with pytest.raises(TypeError, match="not a multi-entity source"):
            resolve_source("src.nodes", {"src": source})

    def test_invalid_entity_type_raises_value_error(self):
        multi = DummyMultiSource(["nodes"])
        with pytest.raises(ValueError, match="not found in source"):
            resolve_source("network.bogus", {"network": multi})

    def test_bare_multi_source_raises_type_error(self):
        multi = DummyMultiSource(["nodes", "edges"])
        with pytest.raises(TypeError, match="multi-entity source"):
            resolve_source("network", {"network": multi})

    def test_bare_multi_source_error_lists_available_types(self):
        multi = DummyMultiSource(["nodes", "edges"])
        with pytest.raises(TypeError, match="edges, nodes"):
            resolve_source("network", {"network": multi})
