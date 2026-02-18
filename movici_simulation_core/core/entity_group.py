from __future__ import annotations

import itertools
import typing as t

import numpy as np

from . import attribute
from . import state as state_
from .attribute_spec import AttributeSpec
from .index import Index


class EntityGroup:
    __entity_name__: t.Optional[str] = None
    __exclude__: t.ClassVar[t.Iterable[str] | None] = None
    __optional__: bool = False

    _state: state_.StateProxy | None = None
    _attributes: t.ClassVar[t.Dict[str, attribute.AttributeField]] = {}

    def __init__(
        self,
        name: str | None = None,
        optional: bool | None = None,
        exclude: t.Iterable[str] | None = None,
        override_exclude: t.Iterable[str] | None = None,
    ):
        if name is not None:
            self.__entity_name__ = name
        if optional is not None:
            self.__optional__ = optional

        if exclude is not None and override_exclude is not None:
            raise ValueError("Cannot supply both exclude and override_exclude arguments")

        if override_exclude is not None:
            exclude = set(override_exclude)
        else:
            exclude = set(self.__exclude__ or []) | set(exclude or [])

        all_attributes = self._all_attributes()
        non_exisiting_exclude = exclude - all_attributes.keys()
        if non_exisiting_exclude:
            raise ValueError(
                "Cannot exclude non-existing attributes for EntityGroup:"
                f" {','.join(non_exisiting_exclude)}"
            )
        self.attributes = {k: all_attributes[k] for k in all_attributes.keys() - exclude}

    def __init_subclass__(cls, **kwargs):
        cls.__entity_name__ = kwargs.get("name", cls.__entity_name__)
        cls._attributes = {
            key: value
            for key, value in vars(cls).items()
            if isinstance(value, attribute.AttributeField)
        }

    @property
    def state(self):
        if self._state is None:
            raise RuntimeError("EntityGroup must be registered to a TrackedState first")
        return self._state

    def is_ready_for(self, flag: int):
        """This method is called when TrackedState checks if this entity group is
        ready for initialization (INITIALIZE) or updates (REQUIRED). An optional
        entity group is ignored if it has no entities. When an optional entity group
        has entities, it's required attributes must be initialized (filled with data)

        :param flag: one of INITIALIZE, REQUIRED
        """
        if self.__optional__ and len(self) == 0:
            return True
        return all(
            attr.get_for(self).is_initialized()
            for attr in self.attributes.values()
            if flag & attr.flags
        )

    def __len__(self):
        return len(self.index)

    def __eq__(self, other):
        if not isinstance(other, EntityGroup):
            return NotImplemented
        return self._eq_key() == other._eq_key()

    def __hash__(self):
        return hash(self._eq_key())

    def _eq_key(self):
        return type(self), self._state, self.__entity_name__

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
        self._state = state

    def get_attribute(self, identifier: str):
        return self.state.get_attribute(identifier)

    def register_attribute(self, spec: AttributeSpec, flags: int = 0, rtol=0.00001, atol=1e-8):
        return self.state.register_attribute(spec, flags, rtol, atol)

    @classmethod
    def _all_attributes(cls) -> t.Dict[str, attribute.AttributeField]:
        bases = [c for c in cls.__mro__ if issubclass(c, EntityGroup)]
        return dict(itertools.chain.from_iterable(b._attributes.items() for b in reversed(bases)))

    @property
    def index(self) -> Index:
        return self.state.get_index()

    @property
    def dataset_name(self):
        return self.state.dataset_name


EntityGroupT = t.TypeVar("EntityGroupT", bound=EntityGroup)
