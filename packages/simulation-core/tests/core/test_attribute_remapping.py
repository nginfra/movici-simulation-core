import pytest

from movici_simulation_core.core.attribute_remapping import (
    apply_remap_to_pub_mask,
    apply_remap_to_sub_mask,
)


class TestApplyRemapToSubMask:
    def test_replaces_originals_with_variants(self):
        mask = {"ds": {"eg": ["a", "b"]}}
        result = apply_remap_to_sub_mask(mask, {"ds": {"eg": {"a:m1:i": "a", "a:m2:i": "a"}}})
        # 'a' was replaced by its variants; 'b' (untouched by REMAP) stays.
        assert result is not None
        assert set(result["ds"]["eg"]) == {"a:m1:i", "a:m2:i", "b"}

    def test_back_propagation_keeps_canonical(self):
        mask = {"ds": {"eg": ["a"]}}
        result = apply_remap_to_sub_mask(mask, {"ds": {"eg": {"a:m1:i": "a", "a": "a"}}})
        assert result is not None
        assert set(result["ds"]["eg"]) == {"a", "a:m1:i"}

    @pytest.mark.parametrize(
        "data_mask, expected",
        [
            (None, None),
            ({"ds": None}, {"ds": None}),
            ({"another": None}, {"another": None, "ds": {"eg": ["a:m:i"]}}),
            ({"another": None, "ds": {"eg": ["a"]}}, {"another": None, "ds": {"eg": ["a:m:i"]}}),
            ({"ds": {"eg": ["a"], "another": None}}, {"ds": {"eg": ["a:m:i"], "another": None}}),
            ({"ds": {"eg": None}}, {"ds": {"eg": None}}),
        ],
    )
    def test_wildcards_are_preserved(self, data_mask, expected):
        # A wildcard subscription must remain a wildcard after REMAP — otherwise a model
        # subscribing to "everything" silently loses everything except the variants
        # mentioned in the REMAP
        remap = {"ds": {"eg": {"a:m:i": "a"}}}
        assert apply_remap_to_sub_mask(data_mask, remap) == expected

    def test_empty_remap_is_noop(self):
        mask = {"ds": {"eg": ["a"]}}
        assert apply_remap_to_sub_mask(mask, None) is mask
        assert apply_remap_to_sub_mask(mask, {}) is mask

    def test_malformed_entity_group_value_raises(self):
        # A non-list, non-None entity-group entry is a programmer error elsewhere; fail
        # noisily rather than silently dropping the original data.
        with pytest.raises(ValueError, match="Malformed mask"):
            apply_remap_to_sub_mask({"ds": {"eg": "not_a_list"}}, {"ds": {"eg": {"a:m1:i": "a"}}})

    def test_adds_new_attributes_to_sub_mask(self):
        result = apply_remap_to_sub_mask({}, {"ds": {"eg": {"a:m1:i": "a", "a:m2:i": "a"}}})
        assert result is not None
        assert set(result["ds"]["eg"]) == {"a:m1:i", "a:m2:i"}


class TestApplyRemapToPubMask:
    def test_replaces_originals_with_variants(self):
        result = apply_remap_to_pub_mask(
            {"ds": {"eg": ["speed"]}}, {"ds": {"eg": {"speed": "speed:m:i"}}}
        )
        assert result == {"ds": {"eg": ["speed:m:i"]}}

    @pytest.mark.parametrize(
        "data_mask, expected",
        [
            (None, None),
            ({"ds": None}, {"ds": None}),
            ({"another": None}, {"another": None}),
            ({"another": None, "ds": {"eg": ["a"]}}, {"another": None, "ds": {"eg": ["a:m:i"]}}),
            ({"ds": {"eg": None}}, {"ds": {"eg": None}}),
        ],
    )
    def test_wildcards_are_preserved(self, data_mask, expected):
        remap = {"ds": {"eg": {"a": "a:m:i"}}}
        assert apply_remap_to_pub_mask(data_mask, remap) == expected

    def test_dataset_wildcard_preserved(self):
        assert apply_remap_to_pub_mask({"ds": None}, {"ds": {"eg": {"a": "a:m:i"}}})

    def test_entity_group_wildcard_preserved(self):
        assert apply_remap_to_pub_mask(None, {"ds": {"eg": {"a": "a:m:i"}}}) is None

    def test_empty_remap_is_noop(self):
        mask = {"ds": {"eg": ["a"]}}
        assert apply_remap_to_pub_mask(mask, None) is mask

    def test_malformed_entity_group_value_raises(self):
        with pytest.raises(ValueError, match="Malformed mask"):
            apply_remap_to_pub_mask({"ds": {"eg": 42}}, {"ds": {"eg": {"a": "a:m:i"}}})
