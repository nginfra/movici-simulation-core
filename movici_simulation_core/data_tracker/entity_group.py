from __future__ import annotations

import itertools
import typing as t

import numpy as np

from .index import Index
from .property import PropertyField
from ..types import PropertyIdentifier

if t.TYPE_CHECKING:
    from .state import StateProxy


class EntityGroup:
    state: StateProxy = None
    properties: t.Dict[str, PropertyField] = {}
    __entity_name__: t.Optional[str] = None

    def __init__(self, name: str = None):
        if name is not None:
            self.__entity_name__ = name

    def __init_subclass__(cls, **kwargs):
        cls.__entity_name__ = kwargs.get("name", cls.__entity_name__)
        cls.properties = {
            key: value for key, value in vars(cls).items() if isinstance(value, PropertyField)
        }

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

    def is_similiar(self, other: EntityGroup):
        return (self.dataset_name, self.__entity_name__) == (
            other.dataset_name,
            other.__entity_name__,
        )

    def get_indices(self, ids: t.Sequence[int]) -> np.ndarray:
        if not len(self.index):
            raise RuntimeError(f"EntityGroup {self.__entity_name__} doesn't have any ids")
        return self.index[ids]

    def register(self, state: StateProxy):
        self.state = state

    def get_property(self, identifier: PropertyIdentifier):
        return self.state.get_property(identifier)

    @classmethod
    def all_properties(cls) -> t.Dict[str, PropertyField]:
        bases = [c for c in cls.__mro__ if issubclass(c, EntityGroup)]
        return dict(itertools.chain.from_iterable(b.properties.items() for b in reversed(bases)))

    @property
    def index(self) -> Index:
        return self.state.get_index()

    @property
    def dataset_name(self):
        return self.state.dataset_name
