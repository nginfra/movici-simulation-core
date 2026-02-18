import pytest
from jsonschema import exceptions

from movici_simulation_core.validate import (
    FromDictLookup,
    ModelConfigSchema,
    MoviciDataRefInfo,
    validate_and_migrate_config,
    validate_and_process,
)


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
    assert len(validate_and_process(instance, schema=schema)[0]) == 1


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
    ),
)
def test_movici_type_path(do_validate_and_process, entry, expected):
    instances = do_validate_and_process(entry)[0]
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


def _simple_schema(properties):
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
    }


def test_validate_and_migrate_config_converts_config():
    schema = _simple_schema(
        {
            "dataset": {"type": "string"},
        }
    )
    new_schema = _simple_schema(
        {
            "dataset_new": {"type": "string"},
        }
    )

    newer_schema = _simple_schema(
        {
            "dataset_newer": {"type": "string"},
        }
    )

    def convert_to_new(old_config: dict):
        return {"dataset_new": old_config["dataset"]}

    def convert_to_newer(config: dict):
        return {"dataset_newer": config["dataset_new"]}

    result = validate_and_migrate_config(
        {"dataset": "some_dataset"},
        versions=[
            ModelConfigSchema(schema),
            ModelConfigSchema(new_schema, convert_from_previous=convert_to_new),
            ModelConfigSchema(newer_schema, convert_from_previous=convert_to_newer),
        ],
    )
    assert result == {"dataset_newer": "some_dataset"}


@pytest.mark.parametrize(
    "versions, config, msg",
    [
        ([], {}, "versions must contain at least one"),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"a": 2j},
            "not a valid JSON-encodable object",
        ),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"invalid": "key"},
            "'invalid' was unexpected",
        ),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset_a": {"type": "string"}})),
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"invalid": "key"},
            "'invalid' was unexpected",
        ),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset_a": {"type": "string"}})),
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"dataset_a": "key"},
            "Cannot convert config without valid converter function",
        ),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"name": 1234},  # ensure that it adds a 'name' schema check
            "not of type 'string'",
        ),
        (
            [
                ModelConfigSchema(_simple_schema({"dataset": {"type": "string"}})),
            ],
            {"type": 1234},  # ensure that it adds a 'type' schema check
            "not of type 'string'",
        ),
    ],
)
def test_validate_and_migrate_config_raises(versions, config, msg):
    with pytest.raises(match=msg):
        validate_and_migrate_config(config, versions)
