import pytest

from movici_data_core.exceptions import MoviciValidationError, map_errors
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


class TestMapErrors:
    def test_map_errors_no_error(self):
        class A:
            @map_errors(
                (ValueError, IndexError),
            )
            def _nonraising_function(self, a):
                return a

        assert A()._nonraising_function(42) == 42

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (ValueError, IndexError),
            (TypeError, OSError),
            (KeyError, KeyError),
        ],
    )
    def test_map_errors_with_simple_rules(self, exc, expected):
        class A:
            @map_errors(
                (ValueError, IndexError),
                (TypeError, OSError),
            )
            def _raising_function(self):
                raise exc

        with pytest.raises(expected):
            A()._raising_function()

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (ValueError(42), IndexError),
            (ValueError(12), OSError),
            (KeyError, KeyError),
        ],
    )
    def test_map_errors_with_callable_conditions(self, exc, expected):
        class A:
            @map_errors(
                (lambda exc: "12" in str(exc), OSError),
                (lambda exc: "42" in str(exc), IndexError),
            )
            def _raising_function(self):
                raise exc

        with pytest.raises(expected):
            A()._raising_function()

    @pytest.mark.parametrize(
        "exc, expected",
        [
            (ValueError(42), OSError),
            (TypeError(42), IndexError),
            (TypeError(12), TypeError),
        ],
    )
    def test_map_errors_with_mixed_conditions(self, exc, expected):
        class A:
            @map_errors(
                (ValueError, OSError),
                (lambda exc: "42" in str(exc), IndexError),
            )
            def _raising_function(self):
                raise exc

        with pytest.raises(expected):
            A()._raising_function()

    def test_map_errors_with_callable_error_result(self):
        class A:
            @map_errors(
                (ValueError, lambda a: TypeError(a)),
            )
            def _raising_function(self, a):
                raise ValueError

        with pytest.raises(TypeError, match="42"):
            A()._raising_function(42)

    async def test_map_error_async_method(self):
        class A:
            @map_errors(
                (OSError, IndexError),
            )
            async def method(self, raises: bool):
                if raises:
                    raise OSError
                return 42

        assert (await A().method(False)) == 42
        with pytest.raises(IndexError):
            await A().method(True)

    def test_map_error_with_callable(self):
        class A:
            @map_errors((ValueError, lambda a: IndexError(a)))
            def method(self, a):
                raise ValueError

        with pytest.raises(IndexError, match="asdf"):
            A().method("asdf")

    def test_map_error_with_self(self):
        class A:
            def __init__(self) -> None:
                self.a = 53

            @map_errors((ValueError, lambda self: TypeError(self.a)), with_self=True)
            def method(self):
                raise ValueError

        with pytest.raises(TypeError, match="53"):
            A().method()

    async def test_map_error_with_self_async(self):
        class A:
            def __init__(self) -> None:
                self.a = 53

            @map_errors((ValueError, lambda self: TypeError(self.a)), with_self=True)
            async def method(self):
                raise ValueError

        with pytest.raises(TypeError, match="53"):
            await A().method()
