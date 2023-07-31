from __future__ import annotations

import typing as t


class GenericModelException(Exception):
    pass


class IncompleteSource(GenericModelException, ValueError):
    def __init__(self, missing: t.Sequence[str]):
        super().__init__()
        self.missing = missing

    def combine(self, other: IncompleteSource) -> IncompleteSource:
        return IncompleteSource([*self.missing, *other.missing])

    def __add__(self, other) -> IncompleteSource:
        if not isinstance(other, IncompleteSource):
            return NotImplemented
        return self.combine(other)


class ValidationError(GenericModelException, ValueError):
    pass
