from __future__ import annotations

import itertools
import logging
import typing as t
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from ..types import EntityData, NumpyAttributeData, ValueType
from . import entity_group as eg
from . import index as index_
from .attribute import (
    OPT,
    PUBLISH,
    SUBSCRIBE,
    AttributeObject,
    AttributeOptions,
    create_empty_attribute,
    create_empty_attribute_for_data,
)
from .attribute_spec import AttributeSpec
from .data_format import extract_dataset_data
from .schema import AttributeSchema

AttributeDict = t.Dict[str, AttributeObject]

NO_TRACK_UNKNOWN = 0


class TrackedState:
    attributes: t.Dict[str, t.Dict[str, AttributeDict]]
    index: t.Dict[str, t.Dict[str, index_.Index]]
    track_unknown: int
    general: dict[str, dict]
    # registered_entity_groups contains all EntityGroup objects
    # that have been registered through TrackedState.register_entity_groups.
    # keys in this dictionary are dataset names
    #
    # Since entity_group name in a dataset (such as "area_entities") may
    # be registered through multiple EntityGroup objects (although this is
    # rare), the values in this dict are a list of EntityGroup
    registered_entity_groups: dict[str, list[eg.EntityGroup]]

    # registered_attributes contain all AttributeObjects that have been
    # explicitly registered through TrackedState.register_attribute. It
    # does not contain attributes that have been registered through
    # TrackedState.register_entity_group. On registration, we
    # automatically deduplicate, so we have only one AttributeObject
    # per dataset_name, entity_group_name, attribute_name combination
    registered_attributes: dict[tuple[str, str, str], AttributeObject]

    def __init__(
        self,
        schema: t.Optional[AttributeSchema] = None,
        logger: t.Optional[logging.Logger] = None,
        track_unknown=NO_TRACK_UNKNOWN,
    ):
        """

        :param logger: a logging.Logger instance
        :param track_unknown: a union of flags (eg PUB|SUB) that will be used to track
        attributes present in updates, but not yet registered to the state. by default (ie. no
        flags are given) these attributes will not be tracked
        """
        self.attributes = {}
        self.index = {}
        self.logger = logger
        self.schema = schema or AttributeSchema()
        self.general = {}
        self.registered_entity_groups = {}
        self.registered_attributes = {}

        if isinstance(track_unknown, bool):
            track_unknown = track_unknown * OPT
        self.track_unknown = track_unknown

    def log(self, level, message):
        if self.logger is not None:
            self.logger.log(level, message)

    def register_dataset(
        self,
        dataset_name: str,
        entities: t.Sequence[t.Union[t.Type[eg.EntityGroup], eg.EntityGroup]],
    ) -> t.List[eg.EntityGroup]:
        if dataset_name in self.attributes:
            raise ValueError(f"dataset '{dataset_name}' already exists")
        return [self.register_entity_group(dataset_name, entity) for entity in entities]

    def register_entity_group(
        self, dataset_name, entity: t.Union[t.Type[eg.EntityGroupT], eg.EntityGroupT]
    ) -> eg.EntityGroupT:
        """

        :rtype: object
        """
        if isinstance(entity, type) and issubclass(entity, eg.EntityGroup):
            entity = entity()
        if entity.__entity_name__ is None:
            raise ValueError("EntityGroup must have __entity_name__ defined")
        ensure_path(self.attributes, (dataset_name, entity.__entity_name__))
        for field in entity.all_attributes().values():
            self._register_attribute(
                dataset_name=dataset_name,
                entity_name=entity.__entity_name__,
                spec=field.spec,
                flags=field.flags,
                rtol=field.rtol,
                atol=field.atol,
            )
        entity.register(StateProxy(self, dataset_name, entity.__entity_name__))
        self.registered_entity_groups.setdefault(dataset_name, []).append(entity)
        return entity

    def register_attribute(
        self,
        dataset_name: str,
        entity_name: str,
        spec: AttributeSpec,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
    ) -> AttributeObject:
        attribute = self._register_attribute(
            dataset_name=dataset_name,
            entity_name=entity_name,
            spec=spec,
            flags=flags,
            rtol=rtol,
            atol=atol,
        )
        self.registered_attributes[(dataset_name, entity_name, spec.name)] = attribute
        return attribute

    def _register_attribute(
        self,
        dataset_name: str,
        entity_name: str,
        spec: AttributeSpec,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
    ) -> AttributeObject:
        target = ensure_path(self.attributes, (dataset_name, entity_name))

        if spec.name in target:
            attr = target[spec.name]
        else:
            attr = create_empty_attribute(
                spec.data_type,
                rtol=rtol,
                atol=atol,
                options=AttributeOptions(enum_name=spec.enum_name),
            )
            attr.index = self.get_index(dataset_name, entity_name)
            target[spec.name] = attr
        attr.flags |= flags

        return attr

    def _get_entity_group(self, dataset_name, entity_type: str) -> t.Optional[AttributeDict]:
        try:
            return self.attributes[dataset_name][entity_type]
        except KeyError:
            return None

    def is_ready_for(self, flag: int):
        """
        flag: one of REQUIRED, INITIALIZE
        """
        return all(
            attr.is_initialized()
            for attr in self.registered_attributes.values()
            if flag & attr.flags
        ) and all(
            entity_group.is_ready_for(flag)
            for entity_group in itertools.chain.from_iterable(
                self.registered_entity_groups.values()
            )
        )

    def iter_attributes(
        self,
    ) -> t.Generator[t.Tuple[str, str, str, AttributeObject]]:
        for datasetname, entity_type, attributes in self.iter_entities():
            yield from (
                (datasetname, entity_type, name, attr) for name, attr in attributes.items()
            )

    def all_attributes(self):
        return [attr for _, _, _, attr in self.iter_attributes()]

    def iter_entities(self) -> t.Iterable[t.Tuple[str, str, AttributeDict]]:
        yield from (
            (dataset_name, entity_type, attributes)
            for dataset_name, entity in self.attributes.items()
            for entity_type, attributes in entity.items()
        )

    def iter_datasets(self) -> t.Iterable[t.Tuple[str, t.Dict[str, AttributeDict]]]:
        yield from self.attributes.items()

    def reset_tracked_changes(self, flags):
        if flags not in (SUBSCRIBE, PUBLISH):
            raise ValueError("flag must be SUBSCRIBE and/or PUBLISH")
        reset_tracked_changes(self.all_attributes(), flags)

    def get_data_mask(self):
        pub = defaultdict(dict)
        sub = defaultdict(dict)
        for dataset_name, entity_name, attributes in self.iter_entities():
            pub_filter = self._get_entity_mask(attributes, flags=PUBLISH)
            if pub_filter:
                pub[dataset_name][entity_name] = pub_filter

            sub_filter = self._get_entity_mask(attributes, flags=SUBSCRIBE)

            if sub_filter:
                sub[dataset_name][entity_name] = sub_filter
        return {"pub": dict(pub), "sub": dict(sub)}

    @staticmethod
    def _get_entity_mask(attributes: AttributeDict, flags: int):
        return list(filter_attrs(attributes, flags).keys())

    def generate_update(self, flags=PUBLISH):
        rv = defaultdict(dict)
        for dataset_name, entity_type, attributes in self.iter_entities():
            index = self.get_index(dataset_name, entity_type)
            data = EntityDataHandler(attributes, index, schema=self.schema).generate_update(flags)
            if data:
                rv[dataset_name][entity_type] = data
        return dict(rv)

    def receive_update(self, update: t.Dict, is_initial=False, process_undefined=False):
        general_section = update.pop("general", None) or {}  # {"general": None} should yield {}
        for dataset_name, dataset_data in extract_dataset_data(update):
            for entity_name, entity_data in dataset_data.items():
                if self.track_unknown != 0:
                    self.register_entity_group(dataset_name, eg.EntityGroup(entity_name))
                if (entity_group := self._get_entity_group(dataset_name, entity_name)) is None:
                    continue
                index = self.get_index(dataset_name, entity_name)
                handler = EntityDataHandler(
                    entity_group,
                    index,
                    self.track_unknown,
                    process_undefined=process_undefined,
                    schema=self.schema,
                )
                handler.receive_update(entity_data, is_initial)
            self.process_general_section(dataset_name, general_section)

    def process_general_section(self, dataset_name: str, general_section: dict):
        enums = general_section.pop("enum", {})
        specials = parse_special_values(general_section)
        self.general.setdefault(dataset_name, {}).update(general_section)
        for current_dataset, entity_name, name, attr in self.iter_attributes():
            if current_dataset != dataset_name:
                continue
            if (special_value := specials.get(entity_name, {}).get(name)) is not None:
                if attr.options.special not in (None, special_value):
                    self.log(
                        logging.WARNING,
                        f"Special value already set for {dataset_name}/{entity_name}/{name}",
                    )
                else:
                    attr.options.special = special_value

            if (enum := enums.get(attr.options.enum_name)) is not None:
                if attr.options.enum_values not in (None, enum):
                    self.log(
                        logging.WARNING,
                        f"Enum already set for {dataset_name}/{entity_name}/{name}",
                    )
                attr.options.enum_values = enum

    def get_attribute(self, dataset_name: str, entity_type: str, name: str):
        try:
            return self.attributes[dataset_name][entity_type][name]
        except KeyError as e:
            raise ValueError(f"Attribute '{name}' not available") from e

    def get_index(self, dataset_name: str, entity_type: str):
        target = ensure_path(self.index, (dataset_name,))
        try:
            return target[entity_type]
        except KeyError:
            index = index_.Index()
            target[entity_type] = index
            return index

    def has_changes(self) -> bool:
        return any(attr.has_changes() for _, _, _, attr in self.iter_attributes())

    def to_dict(self):
        rv = defaultdict(dict)
        for dataset_name, entity_type, attributes in self.iter_entities():
            index = self.get_index(dataset_name, entity_type)
            data = EntityDataHandler(attributes, index, schema=self.schema).to_dict()
            if data:
                rv[dataset_name][entity_type] = data
        return dict(rv)


def parse_special_values(
    general_section: dict, special_keys: t.Iterable = ("no_data", "special")
) -> t.Dict[str, t.Dict[str, ValueType]]:
    all_specials: t.Dict[str, t.Any] = {}
    for key in special_keys:
        if special_section := general_section.pop(key, None):
            all_specials.update(special_section)

    rv = defaultdict(dict)
    for k, v in all_specials.items():
        entity_type, attribute = k.split(".", maxsplit=1)
        rv[entity_type][attribute] = v

    return dict(rv)


class EntityDataHandler:
    def __init__(
        self,
        attributes: AttributeDict,
        index: index_.Index,
        track_unknown: t.Union[int, bool] = 0,
        process_undefined=False,
        schema: AttributeSchema | None = None,
    ):
        self.attributes = attributes
        self.index = index
        self.track_unknown = track_unknown
        self.process_undefined = process_undefined
        self.schema = schema

    def receive_update(self, entity_data: EntityData, is_initial=False):
        """Update the entity state with new external update data. The first time this is called,
        it will initialize the entity group, and set all the entity ids. Any future updates may not
        contain any additional entities
        """
        if "id" not in entity_data:
            raise ValueError("Invalid data, no ids provided")
        if is_initial:
            self.initialize(entity_data)
        else:
            self._process_new_ids(entity_data)
            self._apply_update(entity_data)

    def initialize(self, data: EntityData):
        self.index.set_ids(data["id"]["data"])
        for attr in self.attributes.values():
            attr.initialize(len(self.index))
        self._apply_update(data)
        reset_tracked_changes(self.attributes.values())

    def _process_new_ids(self, entity_data: EntityData):
        ids = entity_data["id"]["data"]
        new_ids = ids[self.index[ids] == -1]
        self.index.add_ids(new_ids)
        for attr in self.attributes.values():
            attr.resize(len(self.index))

    def _apply_update(self, entity_data: EntityData):
        ids = entity_data["id"]["data"]
        for name, data in entity_data.items():
            if name == "id":
                continue
            if (attr := self.attributes.get(name)) is None and self.track_unknown:
                attr = self._register_new_attribute(name, data)
            if attr is None:
                continue
            if not attr.has_data():
                attr.initialize(len(self.index))
            attr.update(data, self.index[ids], process_undefined=self.process_undefined)

    def _register_new_attribute(self, name: str, data: NumpyAttributeData):
        spec = self.schema.get_spec(name) if self.schema is not None else None
        options = AttributeOptions(enum_name=spec.enum_name if spec else None)
        attr = create_empty_attribute_for_data(data, len(self.index), options=options)
        attr.index = self.index
        attr.flags |= self.track_unknown
        self.attributes[name] = attr
        return attr

    def generate_update(self, flags=PUBLISH):
        rv: t.Dict[str, dict] = defaultdict(dict)
        all_changes = self._get_all_changed_mask(flags)

        if not np.any(all_changes):
            return rv

        rv["id"] = {"data": self.index.ids[all_changes]}
        for name, attr in filter_attrs(self.attributes, flags).items():
            if not np.any(attr.changed):
                continue
            data = attr.generate_update(mask=all_changes)

            rv[name] = data
        return dict(rv)

    def to_dict(self):
        return {
            "id": {"data": self.index.ids},
            **{name: attr.to_dict() for name, attr in self.attributes.items()},
        }

    def _get_all_changed_mask(self, flags: int):
        all_changes = np.zeros(len(self.index), dtype=bool)
        for attr in filter_attrs(self.attributes, flags).values():
            changes = attr.changed
            if not np.any(attr.changed):
                continue
            all_changes |= changes
        return all_changes


FilterAttrT = t.TypeVar("FilterAttrT", t.Iterable[AttributeObject], AttributeDict)


def filter_attrs(attributes: FilterAttrT, flags: int = 0) -> FilterAttrT:
    """Return attributes where any of the `flags` match one of the `Attribute.flags`"""
    if isinstance(attributes, dict):
        return {key: attr for key, attr in attributes.items() if attr.flags & flags}
    return [attr for attr in attributes if attr.flags & flags]


def reset_tracked_changes(attributes: t.Iterable[AttributeObject], flags: t.Optional[int] = None):
    attrs = filter_attrs(attributes, flags) if flags is not None else attributes
    for attr in attrs:
        if attr.has_data():
            attr.reset()


@dataclass(frozen=True)
class StateProxy:
    state: TrackedState
    dataset_name: str
    entity_type: str

    def get_attribute(self, name: str):
        return self.state.get_attribute(self.dataset_name, self.entity_type, name)

    def get_index(self):
        return self.state.get_index(self.dataset_name, self.entity_type)

    def register_attribute(self, spec: AttributeSpec, flags: int = 0, rtol=1e-5, atol=1e-8):
        return self.state.register_attribute(
            self.dataset_name, self.entity_type, spec=spec, flags=flags, rtol=rtol, atol=atol
        )


def ensure_path(d: dict, path: t.Sequence[str]):
    if not path:
        return d
    key, *rest = path
    if key not in d:
        d[key] = {}
    return ensure_path(d[key], rest)
