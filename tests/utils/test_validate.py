import pytest
from jsonschema import exceptions

from movici_simulation_core.validate import FromDictLookup, MoviciDataRefInfo, validate_and_process


@pytest.fixture
def model_config_schema():
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "dataset": {"type": "string", "movici.type": "dataset"},
            "transport_segments": {
                "type": "array",
                "items": [
                    {"type": "string", "movici.type": "dataset"},
                    {"type": "string", "movici.type": "entityGroup"},
                ],
            },
            "datasets": {
                "type": "array",
                "items": {
                    "type": "string",
                    "movici.type": "dataset",
                    "movici.datasetType": "mv_network",
                },
            },
            "attribute": {"type": "string", "movici.type": "attribute"},
            "component_attribute": {
                "type": "array",
                "items": [{"type": "null"}, {"type": "string", "movici.type": "attribute"}],
            },
            "anyof_field": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "movici.type": "attribute"},
                ]
            },
        },
    }


@pytest.fixture
def do_validate_and_process(model_config_schema):
    def inner(entry):
        return validate_and_process(
            entry,
            schema=model_config_schema,
            lookup=FromDictLookup(
                datasets=[
                    {"name": "dataset", "type": "antenna_point_set"},
                    {"name": "another_dataset", "type": "mv_network"},
                ],
                entity_types=["some_entities"],
                attribute_types=[{"name": "some_attribute"}],
            ),
        )

    return inner


@pytest.mark.parametrize(
    "method, value, expected",
    [
        ("dataset", "dataset", True),
        ("dataset", "invalid", False),
        ("entity_group", "some_entities", True),
        ("entity_group", "invalid", False),
        ("attribute", "some_attribute", True),
        ("attribute", "invalid", False),
    ],
)
def test_from_dict_lookup(method, value, expected):
    lookup = FromDictLookup(
        datasets=[
            {"name": "dataset", "type": "antenna_point_set"},
            {"name": "another_dataset", "type": "mv_network"},
        ],
        entity_types=["some_entities"],
        attribute_types=[{"name": "some_attribute"}],
    )
    assert getattr(lookup, method)(value) == expected


_default_lookup = FromDictLookup(datasets=[{"name": "some_dataset", "type": "some_type"}])


@pytest.mark.parametrize(
    "lookup, dataset, type, expected",
    [
        (_default_lookup, "some_dataset", "some_type", True),
        (_default_lookup, "some_dataset", "other_type", False),
        (_default_lookup, "other_dataset", "some_type", False),
        (FromDictLookup(), "unknown", "unknown", True),
    ],
)
def test_from_dict_lookup_dataset_type(lookup, dataset, type, expected):
    assert lookup.dataset_type(dataset, type) == expected


@pytest.mark.parametrize(
    "schema, instance",
    [
        (
            {
                "anyOf": [
                    {"type": "null"},
                    {"type": "string", "movici.type": "attribute"},
                ]
            },
            "some_attribute",
        ),
        (
            {
                "anyOf": [
                    {"type": "null"},
                    {
                        "oneOf": [
                            {"type": "null"},
                            {"type": "string", "movici.type": "attribute"},
                        ]
                    },
                ]
            },
            "some_attribute",
        ),
    ],
)
def test_validate(schema, instance):
    assert len(validate_and_process(instance, schema=schema)) == 1


_valid_entries = [
    {"dataset": "dataset"},
    {"datasets": ["another_dataset"]},
    {"transport_segments": ["dataset", "some_entities"]},
    {"attribute": "some_attribute"},
    {"component_attribute": [None, "some_attribute"]},
    {"anyof_field": "some_attribute"},
]


@pytest.mark.parametrize("entry", _valid_entries)
def test_valid_movici_types(do_validate_and_process, entry):
    assert len(do_validate_and_process(entry)) > 0


@pytest.mark.parametrize(
    "entry, expected",
    zip(
        _valid_entries,
        [
            [MoviciDataRefInfo("$.dataset", "dataset", "dataset")],
            [MoviciDataRefInfo("$.datasets[0]", "dataset", "another_dataset")],
            [
                MoviciDataRefInfo("$.transport_segments[0]", "dataset", "dataset"),
                MoviciDataRefInfo("$.transport_segments[1]", "entityGroup", "some_entities"),
            ],
            [MoviciDataRefInfo("$.attribute", "attribute", "some_attribute")],
            [MoviciDataRefInfo("$.component_attribute[1]", "attribute", "some_attribute")],
            [MoviciDataRefInfo("$.anyof_field", "attribute", "some_attribute")],
        ],
        strict=False,
    ),
)
def test_movici_type_path(do_validate_and_process, entry, expected):
    instances = do_validate_and_process(entry)
    assert instances == expected


@pytest.mark.parametrize(
    "entry",
    [
        {"dataset": "invalid"},
        {"datasets": ["dataset"]},
        {"datasets": ["another_dataset", "dataset"]},
        {"transport_segments": ["another_dataset", "invalid_entities"]},
        {"attribute": "invalid_attribute"},
        {"component_attribute": ["some_component", "some_attribute"]},
    ],
)
def test_invalid_movici_types(do_validate_and_process, entry):
    with pytest.raises(exceptions.ValidationError):
        do_validate_and_process(entry)


json_paths = [
    "$.a",
    "$.attr",
    "$[0]",
    "$.some[1].complex.path[0]",
]


@pytest.mark.parametrize(
    "jsonpath,path",
    zip(
        json_paths,
        [
            ("a",),
            ("attr",),
            (0,),
            ("some", 1, "complex", "path", 0),
        ],
        strict=False,
    ),
)
def test_parse_json_path(jsonpath, path):
    info = MoviciDataRefInfo(jsonpath, "foo", "bar")
    assert info.path == path


@pytest.mark.parametrize("jsonpath", json_paths)
def test_round_trip_json_path(jsonpath):
    info = MoviciDataRefInfo(jsonpath, "foo", "bar")
    assert info.json_path == jsonpath


def test_set_value():
    val = "value"
    obj = {"some": [{"path": None}]}
    info = MoviciDataRefInfo("$.some[0].path", "foo", val)
    info.set_value(obj)
    assert obj["some"][0]["path"] == val


def test_unset_value():
    obj = {"some": [{"path": "value"}]}
    info = MoviciDataRefInfo("$.some[0].path", "foo", "bar")
    info.unset_value(obj)
    assert obj["some"][0]["path"] is None
