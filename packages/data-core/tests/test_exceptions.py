from movici_data_core.exceptions import MoviciValidationError

from movici_simulation_core.validate import validate_and_process


def test_error_with_single_message():
    assert list(MoviciValidationError("some errormessage", path="some.path").iter_messages()) == [
        ("some.path", "some errormessage"),
    ]


def test_consume_error_with_prefix():
    error = MoviciValidationError(path="some.root")
    error.consume(MoviciValidationError("some errormessage", path="some.path"))
    assert list(error.iter_messages()) == [
        ("some.root.some.path", "some errormessage"),
    ]


def test_consume_jsonschema_validation_error():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "key": {
                "type": "array",
                "items": {"type": "number"},
            }
        },
    }
    obj = {"additional": "val", "key": [0, "invalid"]}
    _, errors = validate_and_process(obj, schema, return_errors=True)

    error = MoviciValidationError.from_errors(errors, path="prefix")

    assert list(m[0] for m in error.iter_messages()) == ["prefix", "prefix.key.1"]
