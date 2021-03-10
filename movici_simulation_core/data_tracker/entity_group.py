from __future__ import annotations
import typing as t

import numpy as np

from .index import Index
from .property import PropertyField
from .types import PropertyIdentifier

if t.TYPE_CHECKING:
    from .state import StateProxy


class EntityGroup:
    state: StateProxy = None
    properties: t.Dict[PropertyIdentifier, PropertyField] = {}
    __entity_name__: t.Optional[str] = None

    def __init__(self, name: str = None):
        if name is not None:
            self.__entity_name__ = name

    def __init_subclass__(cls, **kwargs):
        cls.__entity_name__ = kwargs.get("name", cls.__entity_name__)
        fields = tuple(obj for obj in vars(cls).values() if isinstance(obj, PropertyField))
        cls.properties = {}
        for field in fields:
            if field.key in cls.properties:
                raise ValueError(f"Duplicate property for EntityGroup '{field.full_name}'")
            cls.properties[field.key] = field

    def __len__(self):
        return len(self.index)

    def __eq__(self, other):
        if not isinstance(other, EntityGroup):
            return NotImplemented
        return self._eq_key() == other._eq_key()

    def __hash__(self):
        return hash(self._eq_key())

    def _eq_key(self):
        return type(self), self.state, self.__entity_name__

    def get_indices(self, ids: t.Sequence[int]) -> np.ndarray:
        if not len(self.index):
            raise RuntimeError(f"EntityGroup {self.__entity_name__} doesn't have any ids")
        return self.index[ids]

    def register(self, state: StateProxy):
        self.state = state

    def get_property(self, identifier: PropertyIdentifier):
        return self.state.get_property(identifier)

    @property
    def index(self) -> Index:
        return self.state.get_index()
