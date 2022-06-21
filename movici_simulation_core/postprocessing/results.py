from __future__ import annotations

import abc
import dataclasses
import datetime
import re
import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core.core import (
    OPT,
    AttributeSpec,
    CSRAttribute,
    EntityInitDataFormat,
    TrackedCSRArray,
    TrackedState,
    UniformAttribute,
)
from movici_simulation_core.core.attribute import create_empty_attribute
from movici_simulation_core.core.data_format import extract_dataset_data
from movici_simulation_core.core.moment import TimelineInfo, string_to_datetime
from movici_simulation_core.core.schema import (
    DEFAULT_ROWPTR_KEY,
    AttributeSchema,
    infer_data_type_from_array,
)
from movici_simulation_core.types import EntityData, FileType


@dataclasses.dataclass
class UpdateFile:
    dataset: str
    timestamp: int
    iteration: int
    path: Path


class SimulationResults:
    def __init__(
        self,
        init_data_dir: Path,
        updates_dir: Path,
        update_pattern=r"t(?P<timestamp>\d+)_(?P<iteration>\d+)_(?P<dataset>\w+)\.json",
        attributes: t.Union[AttributeSchema, t.Sequence[AttributeSpec]] = (),
        timeline_info: TimelineInfo = None,
    ):
        self.update_pattern = update_pattern
        self.init_data_dir = init_data_dir
        self.updates_dir = updates_dir
        self.schema = (
            attributes if isinstance(attributes, AttributeSchema) else AttributeSchema(attributes)
        )
        self.data_reader = EntityInitDataFormat(self.schema)
        self.datasets: t.Dict[str, Path] = self._build_init_data_index()
        self.updates: t.Dict[str, t.List[UpdateFile]] = self._build_updates_index()
        self.timeline_info = timeline_info

    def get_dataset(self, name):
        if not (file := self.datasets.get(name)):
            raise ValueError(f"Dataset {name} not found")
        init_data = self.data_reader.loads(file.read_bytes(), FileType.JSON)
        update_files = self.updates.get(name, [])
        updates = [
            {
                "timestamp": int(upd.timestamp),
                "iteration": int(upd.iteration),
                "name": upd.dataset,
                **self.data_reader.loads(upd.path.read_bytes(), FileType.JSON),
            }
            for upd in update_files
        ]
        return ResultDataset(init_data, updates, timeline_info=self.timeline_info)

    def _build_init_data_index(self):
        return {file.stem: file for file in self.init_data_dir.glob("*.json")}

    def _build_updates_index(self):
        index = {}
        matcher = re.compile(self.update_pattern)
        for file in self.updates_dir.glob("*.json"):
            if not (match := matcher.match(file.name)):
                continue
            values = match.groupdict()
            index.setdefault(values["dataset"], []).append(UpdateFile(path=file, **values))
        for update_list in index.values():
            update_list.sort(key=lambda u: (u.timestamp, u.iteration))
        return index

    def use(self, plugin):
        self.schema.use(plugin)


class ResultDataset:
    def __init__(
        self,
        init_data: dict,
        updates: t.Iterable[t.Dict],
        timeline_info: t.Optional[TimelineInfo] = None,
    ):
        self.name = (
            init_data.get("name", None)
            or [
                key
                for key, val in init_data.items()
                if isinstance(val, dict) and key not in ("general",)
            ][0]
        )
        self.metadata = {
            k: v for k, v in init_data.items() if (k == "general" or not isinstance(v, dict))
        }
        self.state = TimeProgressingState()
        self.state.add_init_data(init_data)
        self.state.add_updates_to_timeline(updates)
        self.timeline_info = timeline_info

    def slice(
        self,
        entity_group,
        timestamp: t.Union[int, str, datetime.datetime, None] = None,
        attribute: t.Optional[str] = None,
        entity_selector=None,
        key="id",  # attribute to check `entity_id` for, for example 'id' or 'reference'
    ):
        kwargs = dict(
            timestamp=timestamp,
            attribute=attribute,
            entity_selector=entity_selector,
            key=key,
        )
        strategy = self.get_slicing_strategy(**kwargs)
        slicer = strategy(
            state=self.state,
            dataset=self.name,
            entity_group=entity_group,
            timeline_info=self.timeline_info,
        )
        return slicer.slice(**kwargs)

    @staticmethod
    def get_slicing_strategy(**kwargs):
        strategies: t.Dict[t.Type[SlicingStrategy], t.Tuple[str]] = {
            SingleTimestampSlicingStrategy: ("timestamp",),
            SingleEntitySlicingStrategy: ("entity_selector", "key"),
            SingleAttributeSlicingStrategy: ("attribute",),
        }
        valid_strategies = [
            strat
            for strat, params in strategies.items()
            if all(kwargs.get(p) is not None for p in params)
        ]
        if len(valid_strategies) == 0:
            raise ValueError("too few parameters to determine slicing strategy")
        elif len(valid_strategies) > 1:
            raise ValueError("too many parameters to determine slicing strategy")
        return valid_strategies[0]


class TimeProgressingState(TrackedState):
    def __init__(self, logger=None):
        super().__init__(logger, track_unknown=OPT)
        self.streams: t.Dict[(str, str), UpdateStream] = {}
        self.last_timestamp = None

    def add_init_data(self, init_data: t.Dict):
        self.receive_update(init_data)
        self.last_timestamp = -1

    def add_updates_to_timeline(self, updates: t.Iterable[t.Dict]):
        sorted_updates = sorted(updates, key=lambda u: (u.get("timestamp"), u.get("iteration")))
        merged_updates = self._merge_updates_at_equal_timestamp(sorted_updates)
        for update in merged_updates:
            self._add_update_to_timeline(update)

    def move_to(self, timestamp):
        for stream in self.streams.values():
            self._move_updates_to(stream, timestamp)

    def get_timestamps(self, dataset, entity_group=None) -> t.List[int]:
        if entity_group is None:
            timestamps = set()
            for (ds, _), stream in self.streams.items():
                if ds == dataset:
                    timestamps.update(upd.timestamp for upd in stream)
            return sorted(timestamps)

        if not self.attributes.get(dataset, {}).get(entity_group):
            return []
        if (stream := self.streams.get((dataset, entity_group))) is None:
            return [0]
        return [upd.timestamp for upd in stream]

    @staticmethod
    def _merge_updates_at_equal_timestamp(updates: t.Sequence[t.Dict]):
        if not len(updates):
            return []
        rv = [updates[0]]
        for upd in updates[1:]:
            if rv[-1]["timestamp"] == upd["timestamp"]:
                result = merge_updates(rv[-1], upd)
                result["timestamp"] = upd["timestamp"]
                result["iteration"] = upd["iteration"]
                rv[-1] = result
            else:
                rv.append(upd)
        return rv

    def _add_update_to_timeline(self, update: t.Dict):
        timestamp = update["timestamp"]
        iteration = update["iteration"]
        if self.last_timestamp is not None and timestamp <= self.last_timestamp:
            raise ValueError("Can only add new updates that have a larger timestamp")
        self.last_timestamp = timestamp
        for dataset_name, data in extract_dataset_data(update):
            for entity_name, entity_data in data.items():
                stream = self.streams.setdefault((dataset_name, entity_name), UpdateStream())
                rev_update = self._create_reversible_update(
                    timestamp, iteration, dataset_name, entity_name, entity_data
                )
                stream.insert_after(rev_update)
                rev_update.apply(self)

    def _create_reversible_update(
        self, timestamp, iteration, dataset_name, entity_name, entity_data
    ):
        index = self.get_index(dataset_name, entity_name)
        indices = index[entity_data["id"]["data"]]  # todo: process new ids
        rev_update = ReversibleUpdate(
            timestamp=timestamp,
            iteration=iteration,
            dataset=dataset_name,
            entity_group=entity_name,
            indices=indices,
            update=entity_data,
        )
        rev_update.calculate_reverse_update(self)
        return rev_update

    def _move_updates_to(self, updates: UpdateStream, timestamp: int):
        if updates.current is None:
            return
        if timestamp > updates.current.timestamp:
            self._move_stream_forward(updates, timestamp)
        if timestamp < updates.current.timestamp:
            self._move_stream_backward(updates, timestamp)

    def _move_stream_forward(self, updates: UpdateStream, timestamp):
        while True:
            try:
                upd = updates.next()
            except EndOfStream:
                break
            upd.apply(self)
            if upd.next is None or upd.next.timestamp > timestamp:
                break

    def _move_stream_backward(self, updates: UpdateStream, timestamp):
        upd = updates.current
        while True:
            upd.revert(self)
            try:
                upd = updates.prev()
            except EndOfStream:
                break

            if upd is None or upd.timestamp <= timestamp:
                break


def merge_updates(*updates: dict):
    if len(updates) == 0:
        return None
    state = TrackedState(track_unknown=OPT)
    for upd in updates:
        state.receive_update(upd)
    return state.to_dict()


@dataclasses.dataclass
class ReversibleUpdate:
    timestamp: int
    iteration: int
    dataset: str
    entity_group: str
    indices: np.ndarray
    update: EntityData
    reverse_update: t.Optional[EntityData] = None
    next: ReversibleUpdate = None
    prev: ReversibleUpdate = None

    def calculate_reverse_update(self, state: TrackedState):
        rev = {"id": self.update["id"]}
        for attr_name, data in self.update.items():
            if attr_name == "id":
                continue
            try:
                attr = state.get_attribute(self.dataset, self.entity_group, attr_name)
            except ValueError:
                num_entities = len(state.get_index(self.dataset, self.entity_group)) or len(
                    self.update["id"]["data"]
                )
                attr = create_empty_attribute(
                    infer_data_type_from_array(data),
                    num_entities,
                )
            current_data = attr.slice(self.indices)
            if isinstance(current_data, TrackedCSRArray):
                rev[attr_name] = {
                    "data": current_data.data,
                    DEFAULT_ROWPTR_KEY: current_data.row_ptr,
                }
            else:
                rev[attr_name] = {"data": current_data.copy()}
        self.reverse_update = rev

    def apply(self, state: TrackedState):
        state.receive_update({self.dataset: {self.entity_group: self.update}})

    def revert(self, state: TrackedState):
        if self.reverse_update is None:
            raise ValueError("No reverse update defined")
        state.receive_update(
            {self.dataset: {self.entity_group: self.reverse_update}}, process_undefined=True
        )


class EndOfStream(ValueError):
    pass


class UpdateStream:
    def __init__(self, updates: t.Optional[t.Sequence[ReversibleUpdate]] = None):
        self.current: t.Optional[ReversibleUpdate] = ReversibleUpdate(
            -1, -1, "dummy", "dummy", None, None
        )
        self.first = self.current
        self.length = 0
        updates = updates or []
        for upd in updates:
            self.insert_after(upd)

    def __iter__(self) -> t.Iterator[ReversibleUpdate]:
        item = self.first
        while (item := item.next) is not None:
            yield item

    def next(self) -> ReversibleUpdate:
        if self.current is None or self.current.next is None:
            raise EndOfStream("End reached")
        self.current = self.current.next
        return self.current

    def prev(self) -> ReversibleUpdate:
        if self.current is None or self.current.prev is None:
            raise EndOfStream("Beginning reached")
        self.current = self.current.prev
        return self.current

    def insert_after(self, update: ReversibleUpdate):
        if self.current is None:
            self.current = update
            return
        after = self.current.next
        if after is not None:
            after.prev = update
        update.next = after
        update.prev = self.current
        self.current.next = update
        self.current = update
        self.length += 1


class SlicingStrategy:
    def __init__(
        self,
        state: TimeProgressingState,
        dataset: str,
        entity_group: str,
        timeline_info: TimelineInfo,
    ):
        self.state = state
        self.dataset = dataset
        self.entity_group = entity_group
        self.timeline_info = timeline_info

    @abc.abstractmethod
    def slice(
        self,
        timestamp: t.Union[int, str, datetime.datetime, None] = None,
        attribute: t.Optional[str] = None,
        entity_selector=None,
        key="id",
        **_,
    ):
        pass


class SingleTimestampSlicingStrategy(SlicingStrategy):
    def slice(self, timestamp: t.Union[int, str, datetime.datetime, None] = None, **_):
        timestamp = self._ensure_discrete_timestamp(timestamp)
        self.state.move_to(timestamp)
        return self.state.to_dict().get(self.dataset, {}).get(self.entity_group)

    def _ensure_discrete_timestamp(self, timestamp: t.Union[int, str, datetime.datetime]):
        if isinstance(timestamp, int):
            return timestamp
        elif isinstance(timestamp, str):
            timestamp = string_to_datetime(timestamp)

        if isinstance(timestamp, datetime.datetime):
            return self.timeline_info.datetime_to_timestamp(timestamp)
        else:
            raise TypeError(f"cannot interpret object of type {type(timestamp)} as timestamp")


class SingleAttributeSlicingStrategy(SlicingStrategy):
    def slice(
        self,
        attribute: t.Optional[str] = None,
        **_,
    ):
        timestamps = []
        data = []
        ids = self.state.get_index(self.dataset, self.entity_group).ids
        try:
            prop = self.state.get_attribute(self.dataset, self.entity_group, attribute)
        except ValueError:
            pass
        else:
            for timestamp in self.state.get_timestamps(self.dataset, self.entity_group):
                self.state.move_to(timestamp)
                timestamps.append(timestamp)
                data.append(prop.to_dict())
        finally:
            return {
                "timestamps": timestamps,
                "id": ids,
                "data": data,
            }


class SingleEntitySlicingStrategy(SlicingStrategy):
    def slice(
        self,
        entity_selector=None,
        key="id",
        **_,
    ):
        index = self._get_entity_index(entity_selector, key)
        if index == -1:
            raise ValueError(f"Entity not found where {key}=={entity_selector}")

        timestamps = self.state.get_timestamps(self.dataset, self.entity_group)
        all_attrs = self.state.attributes.get(self.dataset, {}).get(self.entity_group, {})
        data = {key: [] for key in all_attrs}

        for timestamp in timestamps:
            self.state.move_to(timestamp)
            for key, attr in all_attrs.items():
                result = attr.slice([index])
                if isinstance(attr, UniformAttribute):
                    result = result[0]
                else:
                    result = result.data
                data[key].append(result)

        return {
            "timestamps": timestamps,
            "data": data,
        }

    def _get_entity_index(self, entity_selector, attribute: str):
        index = self.state.get_index(self.dataset, self.entity_group)
        if attribute == "id":
            return index[[entity_selector]][0]
        try:
            key_attr = self.state.get_attribute(self.dataset, self.entity_group, attribute)
        except ValueError:
            return -1
        if isinstance(key_attr, CSRAttribute):
            raise ValueError("Can only use UniformAttribute as key")
        self.state.move_to(0)
        matches = np.flatnonzero(key_attr.array == entity_selector)
        if len(matches) == 0:
            return -1
        return matches[0]
