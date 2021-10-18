from __future__ import annotations

import dataclasses
import itertools
import shutil
import typing as t
from pathlib import Path

from movici_simulation_core.base_models.simple_model import SimpleModel
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.property import SUB, SUBSCRIBE
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.data_collector.concurrent import (
    LimitedThreadPoolExecutor,
    MultipleFutures,
)
from movici_simulation_core.networking.messages import UpdateMessage
from movici_simulation_core.types import DataMask, UpdateData
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings


@dataclasses.dataclass
class UpdateInfo:
    name: str
    timestamp: int
    iteration: int
    data: dict
    origin: t.Optional[str] = None

    def full_data(self):
        return {self.name: self.data}


class DataCollector(SimpleModel, name="data_collector"):
    state: t.Optional[TrackedState] = None
    aggregate: bool = False
    strategy: StorageStrategy
    strategies: t.Dict[str, t.Type[StorageStrategy]] = {}

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.pool = LimitedThreadPoolExecutor(max_workers=5)
        self.futures = MultipleFutures()
        self.iteration = itertools.count()
        self.current_time = None

    def initialize(self, settings: Settings, **_) -> DataMask:
        self.strategy = self.get_storage_strategy(settings)
        self.strategy.initialize()
        self.state = TrackedState(track_unknown=SUB)
        self.aggregate = self.config.get("aggregate_updates", self.aggregate)
        return self._get_mask()

    def _get_mask(self, key="gather_filter") -> DataMask:
        sub_mask = self.config.get(key, None)
        if sub_mask == "*":
            sub_mask = None
        return {"pub": {}, "sub": sub_mask}

    def update(
        self, moment: Moment, data: UpdateData, message: UpdateMessage
    ) -> t.Tuple[UpdateData, t.Optional[Moment]]:
        if data is None:
            return None, None
        self.state.receive_update(data)
        self.maybe_flush(moment, message.origin, self.aggregate is False)
        return None, None

    def new_time(self, new_time: Moment, **_):
        self.maybe_flush(self.current_time, origin=None, trigger=self.aggregate)
        self.current_time = new_time
        self.strategy.reset_iterations(self)

    def close(self, **_):
        self.maybe_flush(self.current_time, origin=None, trigger=self.aggregate)
        self.futures.wait()
        self.pool.shutdown()

    def maybe_flush(self, moment: Moment, origin, trigger):
        if trigger:
            self.flush(moment, origin)

    def flush(self, moment: Moment, origin: t.Optional[str]):
        for ds, data in self.state.generate_update(SUBSCRIBE).items():
            info = UpdateInfo(
                name=ds,
                timestamp=moment.timestamp,
                iteration=next(self.iteration),
                data=data,
                origin=origin,
            )
            self.submit(self.strategy.store, info)
        self.state.reset_tracked_changes(SUBSCRIBE)

    def submit(self, fn, *args, **kwargs):
        fut = self.pool.submit(fn, *args, **kwargs)
        self.futures.add(fut)

    def get_storage_strategy(self, settings: Settings):
        try:
            strategy_cls = self.strategies[settings.storage]
        except KeyError:
            raise ValueError(f"Unsupported storage method '{settings.storage}'")
        return strategy_cls.choose(self.config, settings)

    @classmethod
    def add_storage_strategy(cls, name, strategy: t.Type[StorageStrategy]):
        cls.strategies[name] = strategy


class StorageStrategy:
    @classmethod
    def choose(cls, config: dict, settings: Settings) -> StorageStrategy:
        raise NotImplementedError

    def initialize(self):
        pass

    def store(self, info: UpdateInfo):
        raise NotImplementedError

    def reset_iterations(self, model: DataCollector):
        pass


class LocalStorageStrategy(StorageStrategy):
    def __init__(self, directory: Path, filename_template="t{timestamp}_{iteration}_{name}"):
        self.directory = Path(directory)
        self.filename_template = filename_template

    @classmethod
    def choose(cls, config: dict, settings: Settings) -> StorageStrategy:
        directory = config.get("storage_dir") or settings.storage_dir
        if directory is None:
            raise ValueError("No storage_dir set")
        return LocalStorageStrategy(directory)

    def initialize(self):
        self._ensure_empty_directory()

    def store(self, info: UpdateInfo):
        filename = self.filename_template.format(**dataclasses.asdict(info))
        path = (self.directory / filename).with_suffix(".json")
        path.write_text(EntityInitDataFormat().dumps(info.full_data()))

    def reset_iterations(self, model: DataCollector):
        model.iteration = itertools.count()

    def _ensure_empty_directory(self):
        if self.directory.exists() and not self.directory.is_dir():
            raise FileNotFoundError(f"{str(self.directory)} is not a valid directory")
        if self.directory.exists():
            shutil.rmtree(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True)


DataCollector.add_storage_strategy("disk", LocalStorageStrategy)
