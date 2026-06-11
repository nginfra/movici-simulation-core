import pytest

from movici_simulation_core.utils.data_mask import (
    apply_remap_to_pub_mask,
    apply_remap_to_sub_mask,
    filter_data,
    masks_overlap,
    validate_mask,
)

pub_sub_masks = [
    (
        {"dataset1": {"entity1": ["property"]}},
        {"dataset1": {"entity1": ["property"]}},
        True,
        "Two equal masks",
    ),
    (
        {"dataset1": {"entity1": ["property", "prop2"], "entity2": ["prop2"]}},
        {"dataset1": {"entity2": ["prop2"]}},
        True,
        "One mask has an extra entity",
    ),
    (
        {
            "dataset1": {"entity1": ["property"]},
            "extra_dataset": {"entity2": ["prop"]},
        },
        {"dataset1": {"entity1": ["property"]}},
        True,
        "One mask has an extra dataset",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        {"dataset1": {"entity1": ["property2"]}},
        False,
        "No matching properties",
    ),
    (
        {"dataset1": {"entity1": ["prop2"]}},
        {"dataset1": {"entity2": ["prop2"]}},
        False,
        "No matching entities",
    ),
    (
        {
            "extra_dataset": {"entity1": ["property"]},
        },
        {"dataset1": {"entity1": ["property"]}},
        False,
        "no matching datasets",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        {},
        False,
        "Emtpy dictionary wants nothing",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        None,
        True,
        "No mask wants everything",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        {"dataset1": None},
        True,
        "No mask in dataset wants everything",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        {"dataset2": None},
        False,
        "Interested in the whole dataset, but wrong dataset",
    ),
    (
        {"dataset1": {"entity1": ["property"]}},
        {"dataset1": {"entity1": None}},
        True,
        "No mask in entity group wants everything",
    ),
    (
        {},
        None,
        False,
        "Empty dictionary publishes nothing",
    ),
    (
        None,
        {},
        False,
        "Publishes everything but nothing of interest",
    ),
]


@pytest.mark.parametrize(
    ("pub", "sub", "has_match", "_"),
    pub_sub_masks,
    ids=[arg[3] for arg in pub_sub_masks],
)
def test_matching_of_datafilters(pub, sub, has_match, _):
    assert masks_overlap(pub, sub) == has_match


valid_masks = [
    ({"dataset1": {"entity1": ["property"]}}, "A simple mask"),
    (
        {
            "dataset1": {
                "entity1": ["property", "prop1"],
                "entity2": ["property"],
            },
            "dataset2": {"entity1": ["property"]},
        },
        "A mask with multiple entries",
    ),
    ({}, "A empty dictionary, matches in nothing"),
    (None, "No mask, matches everything"),
    ({"dataset": None}, "Everything from a specific data"),
    ({"dataset": {"entity_group": None}}, "A everything from an entity group"),
]

invalid_masks = [
    ([], "An empty list, must be a dictionary"),
    ({"dataset1": {}}, "Missing entities"),
    ({"dataset1": ["prop", "prop1"]}, "Attributes not under entities"),
    ({"dataset1": {"entities": []}}, "Missing attributes"),
]


@pytest.mark.parametrize(
    ("data_mask", "_"),
    valid_masks,
    ids=[arg[1] for arg in valid_masks],
)
def test_validate_valid_datafilters(data_mask, _):
    assert validate_mask(data_mask)


@pytest.mark.parametrize(
    ("data_mask", "_"),
    invalid_masks,
    ids=[arg[1] for arg in invalid_masks],
)
def test_validate_invalid_datafilters(data_mask, _):
    assert not validate_mask(data_mask)


def has_path(data: dict, path: str, sep="/") -> bool:
    current, *tail = path.split(sep, maxsplit=1)
    if not isinstance(data, dict) or current not in data:
        return False

    if not tail:
        return True
    return has_path(data[current], tail[0], sep=sep)


dataset = {
    "dataset": {
        "entity_group": {
            "id": {"data": [1, 2, 3]},
            "a": {"data": [1, 2, 3]},
            "b": {"data": [4, 5, 6]},
        },
    }
}

test_cases = {
    "allow_all": {
        "mask": None,
        "paths_match": [
            ("dataset/entity_group/a/data", True),
        ],
    },
    "allow_none": {
        "mask": {},
        "paths_match": [
            ("dataset", False),
        ],
    },
    "all_of_dataset": {
        "mask": {"dataset": None},
        "paths_match": [
            ("dataset/entity_group/a/data", True),
        ],
    },
    "all_of_other_dataset": {
        "mask": {"other_dataset": None},
        "paths_match": [
            ("dataset", False),
            ("other_dataset", False),
        ],
    },
    "all_of_entity_group": {
        "mask": {"dataset": {"entity_group": None}},
        "paths_match": [
            ("dataset/entity_group/a/data", True),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "all_of_other_group": {
        "mask": {"dataset": {"other_group": None}},
        "paths_match": [
            ("dataset/entity_group", False),
            ("dataset/other_group", False),
        ],
    },
    "a": {
        "mask": {"dataset": {"entity_group": ["a"]}},
        "paths_match": [
            ("dataset/entity_group/a/data", True),
            ("dataset/entity_group/b/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "id": {
        "mask": {"dataset": {"entity_group": ["id"]}},
        "paths_match": [
            ("dataset/entity_group/a/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "b": {
        "mask": {"dataset": {"entity_group": ["b"]}},
        "paths_match": [
            ("dataset/entity_group/a/data", False),
            ("dataset/entity_group/b/data", True),
        ],
    },
    "a_and_b": {
        "mask": {
            "dataset": {"entity_group": ["a", "b"]},
        },
        "paths_match": [
            ("dataset/entity_group/a/data", True),
            ("dataset/entity_group/b/data", True),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "c": {
        "mask": {"dataset": {"entity_group": ["c"]}},
        "paths_match": [
            ("dataset/entity_group/a/data", False),
            ("dataset/entity_group/b/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
}


dataset_with_internal = {
    "dataset": {
        "entity_group": {
            "id": {"data": [1, 2, 3]},
            "a": {"data": [1, 2, 3]},
            "a:model_a:i": {"data": [10, 20, 30]},
            "a:model_b:i": {"data": [100, 200, 300]},
        },
    }
}


def test_wildcard_skips_internal_attributes():
    """Wildcard subscribers (e.g. a data collector with ``gather_filter: "*"``) must not
    receive the per-publisher internal variants of an attribute. See issue #127."""
    result = filter_data(dataset_with_internal, None)
    assert has_path(result, "dataset/entity_group/a/data")
    assert has_path(result, "dataset/entity_group/id/data")
    assert not has_path(result, "dataset/entity_group/a:model_a:i/data")
    assert not has_path(result, "dataset/entity_group/a:model_b:i/data")


def test_entity_wildcard_skips_internal_attributes():
    """Wildcard at the entity-group level (e.g. ``{"dataset": {"entity_group": None}}``)
    also filters out ``:i`` attributes — the rule applies wherever the leaf mask is open."""
    result = filter_data(dataset_with_internal, {"dataset": {"entity_group": None}})
    assert has_path(result, "dataset/entity_group/a/data")
    assert not has_path(result, "dataset/entity_group/a:model_a:i/data")


def test_explicit_internal_subscription_returns_it():
    """If a model explicitly subscribes to an internal variant, it gets the data — this is
    the path solver helpers use after a REMAP installs a sub remap."""
    result = filter_data(
        dataset_with_internal,
        {"dataset": {"entity_group": ["a:model_a:i"]}},
    )
    assert has_path(result, "dataset/entity_group/a:model_a:i/data")
    assert not has_path(result, "dataset/entity_group/a/data")


def test_dataset_wildcard_skips_internal_attributes():
    """Wildcard at the dataset level still filters at the attribute leaf."""
    result = filter_data(dataset_with_internal, {"dataset": None})
    assert has_path(result, "dataset/entity_group/a/data")
    assert not has_path(result, "dataset/entity_group/a:model_a:i/data")


class TestApplyRemapToSubMask:
    """REMAP-time mask rewriting. See issue #127."""

    def test_replaces_originals_with_variants(self):
        mask = {"ds": {"eg": ["a", "b"]}}
        result = apply_remap_to_sub_mask(mask, {"ds": {"eg": {"a:m1:i": "a", "a:m2:i": "a"}}})
        # 'a' was replaced by its variants; 'b' (untouched by REMAP) stays.
        assert set(result["ds"]["eg"]) == {"a:m1:i", "a:m2:i", "b"}

    def test_back_propagation_keeps_canonical(self):
        mask = {"ds": {"eg": ["a"]}}
        result = apply_remap_to_sub_mask(mask, {"ds": {"eg": {"a:m1:i": "a", "a": "a"}}})
        assert set(result["ds"]["eg"]) == {"a", "a:m1:i"}

    def test_wildcard_preserved(self):
        # A wildcard subscription must remain a wildcard after REMAP — otherwise a model
        # subscribing to "everything" silently loses everything except the variants
        # mentioned in the REMAP (critical bug from the adversarial review).
        assert apply_remap_to_sub_mask(None, {"ds": {"eg": {"a:m1:i": "a"}}}) is None

    def test_empty_remap_is_noop(self):
        mask = {"ds": {"eg": ["a"]}}
        assert apply_remap_to_sub_mask(mask, None) is mask
        assert apply_remap_to_sub_mask(mask, {}) is mask

    def test_malformed_entity_group_value_raises(self):
        # A non-list, non-None entity-group entry is a programmer error elsewhere; fail
        # noisily rather than silently dropping the original data.
        with pytest.raises(ValueError, match="Malformed mask"):
            apply_remap_to_sub_mask({"ds": {"eg": "not_a_list"}}, {"ds": {"eg": {"a:m1:i": "a"}}})


class TestApplyRemapToPubMask:
    def test_replaces_originals_with_variants(self):
        result = apply_remap_to_pub_mask(
            {"ds": {"eg": ["speed"]}}, {"ds": {"eg": {"speed": "speed:m:i"}}}
        )
        assert result == {"ds": {"eg": ["speed:m:i"]}}

    def test_wildcard_preserved(self):
        assert apply_remap_to_pub_mask(None, {"ds": {"eg": {"a": "a:m:i"}}}) is None

    def test_empty_remap_is_noop(self):
        mask = {"ds": {"eg": ["a"]}}
        assert apply_remap_to_pub_mask(mask, None) is mask

    def test_malformed_entity_group_value_raises(self):
        with pytest.raises(ValueError, match="Malformed mask"):
            apply_remap_to_pub_mask({"ds": {"eg": 42}}, {"ds": {"eg": {"a": "a:m:i"}}})


@pytest.mark.parametrize(
    "mask, paths_match",
    [(test["mask"], test["paths_match"]) for test in test_cases.values()],
    ids=test_cases.keys(),
)
def test_filter_data(mask, paths_match):
    result = filter_data(dataset, mask)
    assert all(has_path(result, path) == match for path, match in paths_match)
