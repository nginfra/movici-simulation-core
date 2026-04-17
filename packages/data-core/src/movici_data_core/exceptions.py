from __future__ import annotations

import typing as t
from uuid import UUID

from jsonschema import ValidationError as JSONSchemaValidationError

from movici_simulation_core.types import FileType


class MoviciDataError(Exception):
    pass


class DatabaseAlreadyInitialized(MoviciDataError):
    pass


class DatabaseNotYetInitialized(MoviciDataError):
    pass


class InconsistentDatabase(MoviciDataError):
    pass


class InvalidResource(MoviciDataError):
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
            parts.append(f"({self.name})")
        if self.id is not None:
            parts.append(f"({self.id})")
        if self.message is not None:
            parts.append(f"[{self.message}]")
        return " ".join(parts)


class UnsupportedFileType(MoviciDataError):
    def __init__(self, filetype: FileType):
        self.filetype = filetype

    def __str__(self) -> str:
        return f"Filetype {self.filetype} is not supported for this operation"


class SerializationError(MoviciDataError):
    pass


class MoviciValidationError(MoviciDataError):
    def __init__(self, error: str | dict[str, list[str]] | None = None, path=""):
        self.path = path
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
        prefix = self.path + "." if self.path else ""
        for key, messages in self.messages.items():
            if not key:
                path = self.path
            else:
                path = prefix + key
            for message in messages:
                yield path, message

    def __str__(self):
        return "\n".join(f"{p}: {msg}" for p, msg in self.iter_messages())


class ResourceDoesNotExist(InvalidResource):
    pass


class ResourceAlreadyExists(InvalidResource):
    pass


class InvalidAction(MoviciDataError):
    def __init__(self, message: str | None = None):
        self.message = message
