import pytest

from movici_simulation_core.utils.data_mask import validate_mask, masks_overlap, filter_data

pub_sub_masks = [
    (
        {"dataset1": {"entity1": ["component/property"]}},
        {"dataset1": {"entity1": ["component/property"]}},
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
        {"dataset1": {"entity1": ["component/property"]}},
        {"dataset1": {"entity1": ["component/property2"]}},
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
    ({"dataset1": {"entity1": ["component/property"]}}, "A simple mask"),
    (
        {
            "dataset1": {
                "entity1": ["component/property", "prop1"],
                "entity2": ["component/property"],
            },
            "dataset2": {"entity1": ["component/property"]},
        },
        "A mask with multiple entries",
    ),
    ({}, "A empty dictionary, interested in nothing"),
    (None, "No mask, interested in everything"),
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
            "component": {
                "a": {"data": [1, 2, 3]},
                "b": {"data": [4, 5, 6]},
            },
        },
    }
}

test_cases = {
    "allow_all": {
        "mask": None,
        "paths_match": [
            ("dataset/entity_group/component/a/data", True),
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
            ("dataset/entity_group/component/a/data", True),
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
            ("dataset/entity_group/component/a/data", True),
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
    "component/a": {
        "mask": {"dataset": {"entity_group": ["component/a"]}},
        "paths_match": [
            ("dataset/entity_group/component/a/data", True),
            ("dataset/entity_group/component/b/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "a": {
        "mask": {"dataset": {"entity_group": ["a"]}},
        "paths_match": [
            ("dataset/entity_group/component/a/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "id": {
        "mask": {"dataset": {"entity_group": ["id"]}},
        "paths_match": [
            ("dataset/entity_group/component/a/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "component/b": {
        "mask": {"dataset": {"entity_group": ["component/b"]}},
        "paths_match": [
            ("dataset/entity_group/component/a/data", False),
            ("dataset/entity_group/component/b/data", True),
        ],
    },
    "component/a_and_component/b": {
        "mask": {
            "dataset": {"entity_group": ["component/a", "component/b"]},
        },
        "paths_match": [
            ("dataset/entity_group/component/a/data", True),
            ("dataset/entity_group/component/b/data", True),
            ("dataset/entity_group/id/data", True),
        ],
    },
    "component/c": {
        "mask": {"dataset": {"entity_group": ["component/c"]}},
        "paths_match": [
            ("dataset/entity_group/component/a/data", False),
            ("dataset/entity_group/component/b/data", False),
            ("dataset/entity_group/id/data", True),
        ],
    },
}


@pytest.mark.parametrize(
    "mask, paths_match",
    [(test["mask"], test["paths_match"]) for test in test_cases.values()],
    ids=test_cases.keys(),
)
def test_filter_data(mask, paths_match):
    result = filter_data(dataset, mask)
    assert all(has_path(result, path) == match for path, match in paths_match)
