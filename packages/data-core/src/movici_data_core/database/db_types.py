import datetime
import re
import uuid
from collections.abc import Sequence

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type or MSSQL's UNIQUEIDENTIFIER,
    otherwise uses CHAR(32), storing as stringified hex values.

    source: https://docs.sqlalchemy.org/en/20/core/custom_types.html#backend-agnostic-guid-type
    """

    impl = CHAR
    cache_ok = True

    _default_type = CHAR(36)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        elif dialect.name == "mssql":
            return dialect.type_descriptor(UNIQUEIDENTIFIER())
        else:
            return dialect.type_descriptor(self._default_type)

    def process_bind_param(self, value, dialect):
        if value is None or dialect.name in ("postgresql", "mssql"):
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class TZDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo or value.tzinfo.utcoffset(value) is None:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


class JSONTuple(TypeDecorator):
    impl = JSON
    cache_ok = True

    def __init__(self, *args, length: int | None = None, **kwargs):
        self.length = length
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not isinstance(value, Sequence):
                raise TypeError("must be a sequence")
            if self.length is not None and len(value) != self.length:
                raise TypeError(f"must be of length {self.length}")
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = tuple(value)
        return value


class RegexMatchingString(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, *args, pattern: str | re.Pattern, **kwargs):
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return value

        if not isinstance(value, str):
            raise TypeError("must be a str")
        if not re.match(self.pattern, value):
            raise ValueError(f"value {value} did not match the required pattern")
        return value

    def process_result_value(self, value, dialect):
        return value
