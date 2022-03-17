from __future__ import annotations

import itertools
import typing as t

import numpy as np

from movici_simulation_core.core.attribute_spec import AttributeSpec

from . import state as state_
from .attribute import AttributeField, PropertyField
from .index import Index
from ..types import AttributeIdentifier
from ..utils import lifecycle


@lifecycle.has_deprecations
class EntityGroup:
    state: state_.StateProxy = None
    attributes: t.Dict[str, AttributeField] = {}
    __entity_name__: t.Optional[str] = None

    def __init__(self, name: str = None):
        if name is not None:
            self.__entity_name__ = name

    def __init_subclass__(cls, **kwargs):
        cls.__entity_name__ = kwargs.get("name", cls.__entity_name__)
        # TODO: PropertyField is deprecated
        cls.attributes = {
            key: value
            for key, value in vars(cls).items()
            if isinstance(value, (PropertyField, AttributeField))
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

    def register(self, state: state_.StateProxy):
        self.state = state

    def get_attribute(self, identifier: AttributeIdentifier):
        return self.state.get_attribute(identifier)

    def register_attribute(self, spec: AttributeSpec, flags: int = 0, rtol=0.00001, atol=1e-8):
        return self.state.register_attribute(spec, flags, rtol, atol)

    @lifecycle.deprecated(alternative="EntityGroup.get_attribute")
    def get_property(self, identifier: AttributeIdentifier):
        return self.get_attribute(identifier)

    @classmethod
    def all_attributes(cls) -> t.Dict[str, AttributeField]:
        bases = [c for c in cls.__mro__ if issubclass(c, EntityGroup)]
        return dict(itertools.chain.from_iterable(b.attributes.items() for b in reversed(bases)))

    @lifecycle.deprecated(alternative="EntityGroup.all_attributes")
    @classmethod
    def all_properties(cls) -> t.Dict[str, AttributeField]:
        return cls.all_attributes()

    @property
    def index(self) -> Index:
        return self.state.get_index()

    @property
    def dataset_name(self):
        return self.state.dataset_name


EntityGroupT = t.TypeVar("EntityGroupT", bound=EntityGroup)
