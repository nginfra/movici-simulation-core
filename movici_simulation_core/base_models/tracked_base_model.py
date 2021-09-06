from __future__ import annotations

import dataclasses
import logging
import typing as t
from abc import abstractmethod

from movici_simulation_core.exceptions import NotReady
from .moment import Moment
from ..core.settings import Settings
from ..data_tracker.property import INIT, SUB, PUB
from ..data_tracker.state import TrackedState
from ..model_connector.connector import ModelBaseAdapter, InitDataHandler, DatasetType
from ..core.data_format import load_update
from ..types import Result, Timestamp, UpdateData


@dataclasses.dataclass
class TrackedBaseModelAdapter(ModelBaseAdapter):
    model: TrackedBaseModel
    state: TrackedState = dataclasses.field(init=False, default=None)
    model_initialized: bool = dataclasses.field(init=False, default=False)
    model_ready_for_update: bool = dataclasses.field(init=False, default=False)

    def __post_init__(self):
        self.state = TrackedState(logger=self.logger)

    def initialize(self, init_data_handler: InitDataHandler):
        self.model.setup(
            state=self.state,
            settings=self.settings,
            init_data_handler=init_data_handler,
            logger=self.logger,
        )
        self.download_init_data(init_data_handler)
        self.try_initialize()

    def download_init_data(self, init_data_handler: InitDataHandler):
        init_data_handler.as_numpy_array = True
        for dataset_name, _ in self.state.iter_datasets():
            data_dtype, path = init_data_handler.get(dataset_name)
            if data_dtype not in [DatasetType.JSON, DatasetType.MSGPACK]:
                raise ValueError(
                    f"'{dataset_name}' not of type {DatasetType.JSON} or {DatasetType.MSGPACK}"
                )
            data_dict = path.read_dict()
            self.state.receive_update(data_dict)

    def get_data_filter(self) -> dict:
        return self.state.get_pub_sub_filter()

    def update(self, timestamp: Timestamp, data: UpdateData) -> Result:
        should_calculate = self.process_data(data)
        return self.try_calculate(timestamp, should_calculate)

    def update_series(self, timestamp: Timestamp, data: t.Iterable[t.Optional[bytes]]) -> Result:
        should_calculate = any(self.process_data(item) for item in data)
        return self.try_calculate(timestamp, should_calculate)

    def process_data(self, data: UpdateData) -> bool:
        # Always calculate on a major update
        if data is None:
            return True

        # Only calculate on a cascading update if there is actually data for the model
        if update_dict := load_update(data):
            self.state.receive_update(update_dict)
            return True
        return False

    def try_calculate(self, timestamp: Timestamp, should_calculate=True) -> Result:
        if not should_calculate:
            return None, None
        self.try_initialize()

        if not self.model_initialized:
            return None, timestamp

        if not self.model_ready_for_update and self.state.is_ready_for(SUB):
            self.model_ready_for_update = True

        next_time = None

        model_updated = False
        if self.model_ready_for_update:
            moment = Moment(timestamp)
            next_time = self.model.update(self.state, moment)
            model_updated = True
        update = self.state.generate_update(PUB)
        if model_updated and self.model.auto_reset & SUB:
            self.state.reset_tracked_changes(SUB)
        if self.model.auto_reset & PUB:
            self.state.reset_tracked_changes(PUB)

        return update, next_time

    def try_initialize(self):
        if not self.model_initialized and self.state.is_ready_for(INIT):
            try:
                self.model.initialize(self.state)
            except NotReady:
                return
            self.model_initialized = True

    def new_time(self, new_time: Timestamp):
        moment = Moment(new_time)
        self.model.new_time(self.state, moment)
        if not (self.model_initialized or self.model_ready_for_update) and moment.timestamp > 0:
            self.log_uninitialized_properties()
            raise RuntimeError(
                f"Model called with timestamp >0 while"
                f" initialized: {self.model_initialized} ,"
                f" ready_for_updates:{self.model_ready_for_update}"
            )

    def close(self):
        self.model.shutdown(self.state)
        if not (self.model_initialized or self.model_ready_for_update):
            self.log_uninitialized_properties()
            raise RuntimeError(
                f"Model called with shutdown while"
                f" initialized: {self.model_initialized} ,"
                f" ready_for_updates:{self.model_ready_for_update}"
            )

    def log_uninitialized_properties(self):
        for ds, entity, (comp, prop_name), prop in self.state.iter_properties():
            if (prop.flags & INIT) and not prop.is_initialized():
                msg = "/".join((ds, entity, comp or "", prop_name))
                self.logger.warn(f"Uninitialized property: {msg}")


class TrackedBaseModel:
    """To work with a `TrackedState`, a model developer could create their own `TrackedState()`
    object and work with it directly to track changes and produce updates of changed data. However,
    It is also possible to extend this `TrackedBaseModel` class and let the
    `TrackedBaseModelAdapter` manage the `TrackedState`

    Attributes:
        auto_reset  By default, the TrackedBaseModelAdapter resets tracking information of the
                    state for PUB and/or SUB properties at the appropriate time, so that the model
                    receives a SUB update only once, and PUB properties are published
                    only once. By setting `auto_reset` to `0`, `PUB`, `SUB` or `PUB|SUB`. A model
                    can limit this automatic behaviour and gain full control over which properties
                    are reset and when. However, when overriding the default behaviour, a model
                    must be very careful in implementing this appropriately.
    """

    auto_reset = PUB | SUB  # Set to 0 to manually manage change track resetting. DANGEROUS!

    def __init__(self, model_config: dict):
        self.config = model_config

    @abstractmethod
    def setup(
        self,
        state: TrackedState,
        settings: Settings,
        init_data_handler: InitDataHandler,
        logger: logging.Logger,
    ):
        """In `setup`, a model receives a `state` object, it's `config` and other parameters. The
        goal of `setup` is to prepare the `state` by giving it information of the properties it
        needs to track (by subscribing (INIT/SUB/OPT) or publishing (PUB) properties) from which
        datasets. These properties may be grouped together in `EntityGroup` classes or created
        directly. The main entry points for registering are:
         * `state.add_dataset()` for registering a bunch of `EntityGroup` classes for a certain
           dataset name at once
         * `state.add_entity_group()` for registering a single `EntityGroup` class (or instance)
           for a dataset name
         * `state.create_property()` for registering a single property in a dataset/entity_group
           combination

        During `setup` there is no data available in the `state`. These will be downloaded
        automatically by the `TrackedBaseModelAdapter`. However, additional datasets may be
        requested directly through the `init_data_handler` parameter.

        :param state: The model's TrackedState object, managed by the `TrackedBaseModelAdapter`
        :param settings: global settings
        :param init_data_handler: a `InitDataHandler` that may be used to retrieve additional
            datasets
        :param logger: a `logging.Logger` instance
        """
        ...

    @abstractmethod
    def initialize(self, state: TrackedState):
        """The `initialize` method is called when all of the `state`'s `INIT` property arrays are
        filled with data. This may be during the model engines initialization phase or during
        `t=0`. Data that is required for the model to initialize property may be published in
        another model's t0-update, and the `TrackedBaseModelAdapter` can wait for this to happen
        before calling `initialize`. When the simulation progresses to `t>0` before the model's
        INIT properties have been filled, an Exception is raised, indicating that the model was
        not ready yet.

        :param state: The model's TrackedState object, managed by the `TrackedBaseModelAdapter`
        """

    @abstractmethod
    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """The `update` method is called for every update coming from the model engine. However
        it is only called the first time once all PUB properties have their arrays filled with
        data. When the simulation progresses to `t>0` before the model's SUB properties have been
        filled, an Exception is raised, indicating that the model was not ready yet.

        :param state: The model's TrackedState object, managed by the `TrackedBaseModelAdapter`
        :param moment: The current simulation `Moment`

        :return: an optional `Moment` indicating the next time a model want to be woken up, as
                 per the model engine's protocol
        """

    def new_time(self, state: TrackedState, time_stamp: Moment):
        """Called for every change of timestamp during a simulation run. This method is called
        before checking whether the state is ready for INIT or PUB and may be called before the
        `initialize` and `update` methods have been called the first time.
        """

    def shutdown(self, state: TrackedState):
        """Called when a simulation ends (either due to it being finished or one of the models
        raises an exception). The model may implement this method to clean up local resources.
        This method may be called before the `initialize` and `update` methods have been called
        the first time"""
