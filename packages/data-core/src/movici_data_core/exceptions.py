from __future__ import annotations

import functools
import inspect
import typing as t
from http import HTTPStatus
from uuid import UUID

from jsonschema import ValidationError as JSONSchemaValidationError

from movici_simulation_core.types import FileType


class MoviciDataError(Exception):
    __status_code__ = HTTPStatus.INTERNAL_SERVER_ERROR
    __error_message__ = "An error occured"
    __error_id__ = "generic_error"

    def payload(self) -> dict | None:
        pass


class DatabaseAlreadyInitialized(MoviciDataError):
    pass


class DatabaseNotYetInitialized(MoviciDataError):
    pass


class InconsistentDatabase(MoviciDataError):
    pass


class InvalidResource(MoviciDataError):
    __status_code__ = HTTPStatus.BAD_REQUEST
    __error_id__ = "invalid_resource"
    __error_message__ = "Invalid resource"
    id: UUID | None

    def __init__(
        self,
        resource_type: str,
        name: str | None = None,
        id: UUID | None = None,
        message: str | None = None,
    ):
        if not (name or id):
            raise ValueError("Supply at least one of name or id")
        self.resource_type = resource_type
        self.name = name
        self.id = id
        self.message = message

    def __str__(self) -> str:
        parts = [self.resource_type]
        if self.name is not None:
            parts.append(f'(name="{self.name}")')
        if self.id is not None:
            parts.append(f"(id={self.id})")
        if self.message is not None:
            parts.append(f"[{self.message}]")
        return " ".join(parts)

    def payload(self):
        return {
            "resource": self.resource_type,
            "name": self.name,
            "id": str(self.id) if self.id is not None else None,
            "message": self.message or self.__error_message__,
        }


class InvalidID(MoviciDataError):
    __status_code__ = HTTPStatus.NOT_FOUND
    __error_id__ = "id_not_found"

    def __init__(self, id: t.Any):
        self.id = id

    def payload(self) -> dict | None:
        return {"message": f"ID {self.id} is not a valid id "}


class UnsupportedFileType(MoviciDataError):
    __status_code__ = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    __error_id__ = "unsupported_media_type"

    def __init__(self, filetype: FileType):
        self.filetype = filetype

    def payload(self):
        return {
            "message": f"Filetype {self.filetype.default_extension}"
            " is not supported for this operation"
        }


class DeserializationError(MoviciDataError):
    __status_code__ = HTTPStatus.BAD_REQUEST
    __error_id__ = "invalid_data"
    __error_message__ = "Error while reading data"


class MoviciValidationError(MoviciDataError):
    __status_code__ = HTTPStatus.UNPROCESSABLE_ENTITY
    __error_id__ = "validation_error"
    __error_message__ = "Valdation error"

    def __init__(self, error: str | dict[str, list[str]] | None = None, path: str | int = ""):
        self.path = str(path)
        if isinstance(error, str):
            error = {"": [error]}
        self.messages: dict[str, list[str]] = error or {}

    @classmethod
    def from_errors(
        cls,
        errors: t.Sequence[JSONSchemaValidationError | MoviciValidationError]
        | JSONSchemaValidationError
        | MoviciValidationError,
        path="",
    ):
        result = MoviciValidationError(path=path)
        result.consume(errors)
        return result

    def consume(
        self,
        errors: t.Sequence[JSONSchemaValidationError | MoviciValidationError]
        | JSONSchemaValidationError
        | MoviciValidationError,
    ):
        if isinstance(errors, (JSONSchemaValidationError, MoviciValidationError)):
            return self.consume([errors])
        for error in errors:
            if isinstance(error, JSONSchemaValidationError):
                path = ".".join(str(p) for p in error.path)
                messages = self.messages.setdefault(path, [])
                messages.append(error.message)
            if isinstance(error, MoviciValidationError):
                self.messages.update(error.as_dict())

    def as_dict(self):
        result = {}
        for k, msg in self.iter_messages():
            result.setdefault(k, []).append(msg)
        return result

    def iter_messages(self):
        prefix = f"{str(self.path)}." if self.path else ""
        for key, messages in self.messages.items():
            if not key:
                path = self.path
            else:
                path = prefix + key
            for message in messages:
                yield path, message

    def __str__(self):
        return "\n".join(f"{p}: {msg}" for p, msg in self.iter_messages())

    def payload(self):
        return {
            "messages": self.as_dict(),
        }


class ResourceDoesNotExist(InvalidResource):
    __status_code__ = HTTPStatus.NOT_FOUND
    __error_id__ = "not_found"
    __error_message__ = "Resource not found"


class ResourceAlreadyExists(InvalidResource):
    __status_code__ = HTTPStatus.CONFLICT
    __error_id__ = "duplicate_error"
    __error_message__ = "Resource already exists"


class InvalidAction(MoviciDataError):
    __status_code__ = HTTPStatus.BAD_REQUEST
    __error_id__ = "invalid_action"

    def __init__(self, message: str = "Invalid action"):
        self.message = message

    def payload(self) -> dict | None:
        return {"message": self.message}


T = t.TypeVar("T")


class map_errors:
    """A decorator to catch certain exceptions and reraise them as a different exception

    :param mapping: a mapping between exceptions or exception types and a callable per exception
       or exception type. The callable must accept the same arguments as the decorated method
       except the ``self`` argument
    """

    def __init__(
        self,
        mapping: t.Mapping[
            type[Exception], Exception | type[Exception] | t.Callable[..., Exception]
        ],
    ):
        self.mapping = mapping

    def __call__(self, func: T) -> T:
        if inspect.iscoroutinefunction(func):
            return self.wrap_async(func)
        return t.cast(T, self.wrap(func))

    def wrap(self, func):
        @functools.wraps(func)
        def _wrapped(inst, *args, **kwargs):
            try:
                return func(inst, *args, **kwargs)
            except Exception as e:
                raise self._map_error(e, args, kwargs) from e

        return _wrapped

    def wrap_async(self, func):
        @functools.wraps(func)
        async def _wrapped(inst, *args, **kwargs):
            try:
                return await func(inst, *args, **kwargs)
            except Exception as e:
                raise self._map_error(e, args, kwargs) from e
            except BaseException:
                raise

        return _wrapped

    def _map_error(
        self, exc: type[Exception] | Exception, args, kwargs
    ) -> type[Exception] | Exception:
        exc_type = type(exc) if isinstance(exc, Exception) else exc
        if exc_type in self.mapping:
            mapped = self.mapping[exc_type]
            if callable(mapped):
                mapped = mapped(*args, **kwargs)
            return mapped
        return exc
