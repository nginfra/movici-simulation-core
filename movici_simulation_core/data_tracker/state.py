import typing as t
from collections import defaultdict
from dataclasses import dataclass
from logging import WARN

import numpy as np

from .entity_group import EntityGroup
from .index import Index
from .property import (
    SUB,
    PUB,
    INIT,
    OPT,
    create_empty_property,
    PropertySpec,
    PropertyObject,
    PropertyOptions,
    propstring,
)
from .types import PropertyIdentifier, EntityData, ComponentData, NumpyPropertyData, ValueType

PropertyDict = t.Dict[PropertyIdentifier, PropertyObject]
EntityGroupT = t.TypeVar("EntityGroupT", bound=EntityGroup)


class TrackedState:
    properties: t.Dict[str, t.Dict[str, PropertyDict]]
    index: t.Dict[str, t.Dict[str, Index]]

    def __init__(self, logger=None):
        self.properties = {}
        self.index = {}
        self.logger = logger

    def log(self, level, message):
        if self.logger is not None:
            self.logger.log(level, message)

    def register_dataset(
        self, dataset_name: str, entities: t.Sequence[t.Union[t.Type[EntityGroup], EntityGroup]]
    ) -> t.List[EntityGroup]:
        if dataset_name in self.properties:
            raise ValueError(f"dataset '{dataset_name}' already exists")
        return [self.register_entity_group(dataset_name, entity) for entity in entities]

    def register_entity_group(
        self, dataset_name, entity: t.Union[t.Type[EntityGroupT], EntityGroupT]
    ) -> EntityGroupT:
        if isinstance(entity, type) and issubclass(entity, EntityGroup):
            entity = entity()
        if entity.__entity_name__ is None:
            raise ValueError("EntityGroup must have __entity_name__ defined")
        for field in entity.all_properties().values():
            self.register_property(
                dataset_name=dataset_name,
                entity_name=entity.__entity_name__,
                spec=field.spec,
                flags=field.flags,
                rtol=field.rtol,
                atol=field.atol,
            )
        entity.register(StateProxy(self, dataset_name, entity.__entity_name__))
        return entity

    def register_property(
        self,
        dataset_name: str,
        entity_name: str,
        spec: PropertySpec,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
    ) -> PropertyObject:
        target = ensure_path(self.properties, (dataset_name, entity_name))

        if spec.key in target:
            prop = target[spec.key]
        else:
            prop = create_empty_property(
                spec.data_type,
                rtol=rtol,
                atol=atol,
                options=PropertyOptions(enum_name=spec.enum_name),
            )
            prop.index = self.get_index(dataset_name, entity_name)
            target[spec.key] = prop
        prop.flags |= flags

        return prop

    def _get_entity_group(self, dataset_name, entity_type: str) -> t.Optional[PropertyDict]:
        try:
            return self.properties[dataset_name][entity_type]
        except KeyError:
            return None

    def is_ready_for(self, flag: int):
        """
        flag: one of SUB, INIT
        """
        if not flag & (SUB | INIT):
            raise ValueError("flag must be SUB or INIT")
        flag |= INIT  # SUB also requires INIT properties to be available
        return all(
            prop.is_initialized() for _, _, _, prop in self.iter_properties() if flag & prop.flags
        )

    def iter_properties(self) -> t.Iterable[t.Tuple[str, str, PropertyIdentifier, PropertyObject]]:
        for (datasetname, entity_type, properties) in self.iter_entities():
            yield from (
                (datasetname, entity_type, identifier, prop)
                for identifier, prop in properties.items()
            )

    def all_properties(self):
        return [prop for _, _, identifier, prop in self.iter_properties()]

    def iter_entities(self) -> t.Iterable[t.Tuple[str, str, PropertyDict]]:
        yield from (
            (dataset_name, entity_type, properties)
            for dataset_name, entity in self.properties.items()
            for entity_type, properties in entity.items()
        )

    def iter_datasets(self) -> t.Iterable[t.Tuple[str, t.Dict[str, PropertyDict]]]:
        yield from self.properties.items()

    def reset_tracked_changes(self, flags):
        if not flags & (SUB | PUB):
            raise ValueError("flag must be SUB and/or PUB")
        if flags & SUB:
            flags |= INIT | OPT
        reset_tracked_changes(self.all_properties(), flags)

    def get_pub_sub_filter(self):
        pub_flags = PUB
        sub_flags = SUB | INIT | OPT
        pub = defaultdict(dict)
        sub = defaultdict(dict)
        for dataset_name, entity_name, properties in self.iter_entities():
            pub_filter = self._get_entity_filter(properties, flags=pub_flags)
            if pub_filter:
                pub[dataset_name][entity_name] = pub_filter

            sub_filter = self._get_entity_filter(properties, flags=sub_flags)
            if sub_filter:
                sub_filter["id"] = "*"
                sub[dataset_name][entity_name] = sub_filter
        return {"pub": dict(pub), "sub": dict(sub)}

    @staticmethod
    def _get_entity_filter(properties: PropertyDict, flags: int):
        rv = {}
        for (component, name), prop in filter_props(properties, flags).items():
            if component:
                if component not in rv:
                    rv[component] = {}
                rv[component][name] = "*"
            else:
                rv[name] = "*"
        return rv

    def generate_update(self, flags=PUB):
        rv = defaultdict(dict)
        for dataset_name, entity_type, properties in self.iter_entities():
            index = self.get_index(dataset_name, entity_type)
            data = EntityUpdateHandler(properties, index).generate_update(flags)
            if data:
                rv[dataset_name][entity_type] = data
        return dict(rv)

    def receive_update(self, update: t.Dict):
        general_section = update.pop("general", None) or {}

        for dataset_name, dataset_data in update.items():
            if not isinstance(dataset_data, dict):
                continue
            for entity_name, entity_data in dataset_data.items():
                if not (entity_group := self._get_entity_group(dataset_name, entity_name)):
                    continue
                index = self.get_index(dataset_name, entity_name)
                handler = EntityUpdateHandler(entity_group, index)
                handler.receive_update(entity_data)
            self.process_general_section(dataset_name, general_section)

    def process_general_section(self, dataset_name, general_section):
        enums = general_section.get("enum", {})
        specials = parse_special_values(general_section)
        for current_dataset, entity_name, identifier, prop in self.iter_properties():
            if current_dataset != dataset_name:
                continue
            if (special_value := specials.get(entity_name, {}).get(identifier)) is not None:
                if prop.options.special not in (None, special_value):
                    self.log(
                        WARN,
                        f"Special value already set for "
                        f"{dataset_name}/{entity_name}/{propstring(identifier[1], identifier[0])}",
                    )
                else:
                    prop.options.special = special_value

            if (enum := enums.get(prop.options.enum_name)) is not None:
                if prop.options.enum not in (None, enum):
                    self.log(
                        WARN,
                        f"Enum already set for "
                        f"{dataset_name}/{entity_name}/{propstring(identifier[1], identifier[0])}",
                    )
                prop.options.enum = enum

    def get_property(self, dataset_name: str, entity_type: str, identifier: PropertyIdentifier):
        try:
            return self.properties[dataset_name][entity_type][identifier]
        except KeyError as e:
            raise ValueError(f"Property '{identifier}' not available") from e

    def get_index(self, dataset_name: str, entity_type: str):
        target = ensure_path(self.index, (dataset_name,))
        try:
            return target[entity_type]
        except KeyError:
            index = Index()
            target[entity_type] = index
            return index

    def has_changes(self) -> bool:
        return any(prop.has_changes() for _, _, _, prop in self.iter_properties())


def parse_special_values(
    general_section: dict,
) -> t.Dict[str, t.Dict[PropertyIdentifier, ValueType]]:
    rv = defaultdict(dict)
    for k, v in general_section.get("special", general_section.get("no_data", {})).items():
        entity_type, component, *rest = k.split(".")
        property_name = ".".join(rest)
        rv[entity_type][(component if component else None, property_name)] = v
    return dict(rv)


class EntityUpdateHandler:
    def __init__(self, properties: PropertyDict, index: Index):
        self.properties = properties
        self.index = index

    def receive_update(self, entity_data: EntityData):
        """Update the entity state with new external update data. The first time this is called,
        it will initialize the entity group, and set all the entity ids. Any future updates may not
        contain any additional entities
        """
        if "id" not in entity_data:
            raise ValueError("Invalid data, no ids provided")
        if not self.is_initialized():
            self.initialize(entity_data)
        else:
            self._apply_update(entity_data)

    def is_initialized(self):
        return len(self.index)

    def initialize(self, data: EntityData):
        self.index.set_ids(data["id"]["data"])
        for prop in self.properties.values():
            prop.initialize(len(self.index))
        self._apply_update(data)
        reset_tracked_changes(self.properties.values())

    def _apply_update(self, entity_data: EntityData):
        ids = entity_data["id"]["data"]
        for identifier, data in iter_entity_data(entity_data):
            if identifier == (None, "id"):
                continue
            if prop := self.properties.get(identifier):
                prop.update(data, self.index[ids])

    def generate_update(self, flags=PUB):
        rv: t.Dict[str, dict] = defaultdict(dict)
        all_changes = self._get_all_changed_mask(flags)

        if not np.any(all_changes):
            return rv

        rv["id"] = {"data": self.index.ids[all_changes]}
        for (component, name), prop in filter_props(self.properties, flags).items():
            if not np.any(prop.changed):
                continue
            data = prop.generate_update(mask=all_changes)

            if component:
                rv[component][name] = data
            else:
                rv[name] = data
        return dict(rv)

    def _get_all_changed_mask(self, flags: int):
        all_changes = np.zeros(len(self.index), dtype=bool)
        for prop in filter_props(self.properties, flags).values():
            changes = prop.changed
            if not np.any(prop.changed):
                continue
            all_changes |= changes
        return all_changes


FilterPropT = t.TypeVar("FilterPropT", t.Iterable[PropertyObject], PropertyDict)


def filter_props(properties: FilterPropT, flags: int = 0) -> FilterPropT:
    """Return properties where any of the `flags` match one of the `Property.flags`"""
    if isinstance(properties, dict):
        return {key: prop for key, prop in properties.items() if prop.flags & flags}
    return [prop for prop in properties if prop.flags & flags]


def reset_tracked_changes(properties: t.Iterable[PropertyObject], flags: t.Optional[int] = None):
    props = filter_props(properties, flags) if flags is not None else properties
    for prop in props:
        if prop.has_data():
            prop.reset()


@dataclass(frozen=True)
class StateProxy:
    state: TrackedState
    dataset_name: str
    entity_type: str

    def get_property(self, identifier: PropertyIdentifier):
        return self.state.get_property(self.dataset_name, self.entity_type, identifier)

    def get_index(self):
        return self.state.get_index(self.dataset_name, self.entity_type)


def ensure_path(d: dict, path: t.Sequence[str]):
    if not path:
        return d
    key, *rest = path
    if key not in d:
        d[key] = {}
    return ensure_path(d[key], rest)


def iter_entity_data(
    data: t.Union[EntityData, ComponentData]
) -> t.Iterable[t.Tuple[PropertyIdentifier, NumpyPropertyData]]:
    yield from _iter_entity_data_helper(data, current_component=None)


def _iter_entity_data_helper(
    data: t.Union[EntityData, ComponentData], current_component=None
) -> t.Iterable[t.Tuple[PropertyIdentifier, NumpyPropertyData]]:
    for key, val in data.items():
        if "data" in val:
            # val is PropertyData
            yield ((current_component, key), val)
        else:
            # val is ComponentData
            yield from _iter_entity_data_helper(val, current_component=key)
