from __future__ import annotations

import logging
import typing as t
from abc import abstractmethod

from movici_simulation_core.core import Model
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.data_tracker.data_format import load_update, dump_update
from movici_simulation_core.data_tracker.property import INITIALIZE, SUBSCRIBE, PUBLISH, REQUIRED
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.model_connector.connector import (
    ModelAdapterBase,
)
from ..model_connector.init_data import InitDataHandler, FileType
from movici_simulation_core.networking.messages import (
    UpdateMessage,
    UpdateSeriesMessage,
    QuitMessage,
    NewTimeMessage,
)
from movici_simulation_core.types import RawResult, Timestamp, RawUpdateData, UpdateData
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings
from .common import SchemaAwareInitDataHandler


class TrackedModelAdapter(ModelAdapterBase):
    model: TrackedModel

    def __init__(self, model: TrackedModel, settings: Settings, logger: logging.Logger):
        super().__init__(model, settings, logger)
        self.state = TrackedState(logger=self.logger)
        self.model_initialized: bool = False
        self.model_ready_for_update: bool = False
        self.schema: t.Optional[AttributeSchema] = None
        self.next_time: t.Optional[int] = None

    def set_schema(self, schema: AttributeSchema):
        self.schema = schema

    def initialize(self, init_data_handler: InitDataHandler):
        init_data_handler = SchemaAwareInitDataHandler(init_data_handler, schema=self.schema)
        self.model.setup(
            state=self.state,
            settings=self.settings,
            schema=self.schema,
            init_data_handler=init_data_handler,
            logger=self.logger,
        )
        self.download_init_data(init_data_handler)
        self.try_initialize()
        return self.get_data_filter()

    def download_init_data(self, init_data_handler: InitDataHandler):
        init_data_handler.as_numpy_array = True
        for dataset_name, _ in self.state.iter_datasets():
            data_dtype, path = init_data_handler.get(dataset_name)
            if data_dtype is None:
                self.logger.warning(f"Dataset '{dataset_name}' not found")
                continue
            if data_dtype not in [FileType.JSON, FileType.MSGPACK]:
                raise ValueError(
                    f"'{dataset_name}' not of type {FileType.JSON} or {FileType.MSGPACK}"
                )
            data_dict = path.read_dict()
            self.state.receive_update(data_dict, is_initial=True)

    def get_data_filter(self) -> dict:
        return self.state.get_data_mask()

    def update(self, message: UpdateMessage, data: RawUpdateData) -> RawResult:
        should_calculate = self.process_input(data)
        result = self.try_calculate(message.timestamp, should_calculate)
        return self.process_result(result)

    def update_series(
        self, message: UpdateSeriesMessage, data: t.Iterable[t.Optional[bytes]]
    ) -> RawResult:
        should_calculate = any([self.process_input(item) for item in data])
        result = self.try_calculate(message.timestamp, should_calculate)
        return self.process_result(result)

    def process_input(self, data: RawUpdateData) -> bool:
        # Always calculate on a major update
        if data is None:
            return True

        # Only calculate on a cascading update if there is actually data for the model
        if update_dict := load_update(data):
            self.state.receive_update(update_dict)
            return True
        return False

    @staticmethod
    def process_result(result: t.Tuple[UpdateData, t.Union[Moment, Timestamp, None]]) -> RawResult:
        data, next_time = result
        if data:
            data = dump_update(data)
        if isinstance(next_time, Moment):
            next_time = next_time.timestamp
        return data, next_time

    def try_calculate(
        self, timestamp: Timestamp, should_calculate=True
    ) -> t.Tuple[t.Optional[dict], t.Union[Moment, Timestamp, None]]:
        if not should_calculate:
            return None, self.next_time
        self.try_initialize()

        if not self.model_initialized:
            return None, None

        if not self.model_ready_for_update and self.state.is_ready_for(REQUIRED):
            self.model_ready_for_update = True

        next_time = None

        model_updated = False
        if self.model_ready_for_update:
            moment = Moment(timestamp)
            next_time = self.model.update(state=self.state, moment=moment)
            model_updated = True
        update = self.state.generate_update(PUBLISH) or None
        if model_updated and self.model.auto_reset & SUBSCRIBE:
            self.state.reset_tracked_changes(SUBSCRIBE)
        if self.model.auto_reset & PUBLISH:
            self.state.reset_tracked_changes(PUBLISH)

        self.next_time = next_time
        return update, next_time

    def try_initialize(self):
        if not self.model_initialized and self.state.is_ready_for(INITIALIZE):
            try:
                self.model.initialize(self.state)
            except NotReady:
                return
            self.model_initialized = True

    def new_time(self, message: NewTimeMessage):
        moment = Moment(message.timestamp)
        self.model.new_time(self.state, moment)
        if not (self.model_initialized and self.model_ready_for_update) and moment.timestamp > 0:
            raise RuntimeError(
                "Model called with timestamp >0 while\n"
                + f"initialized      : {self.model_initialized}\n"
                + f"ready_for_updates: {self.model_ready_for_update}\n"
                + self.format_uninitialized_properties()
            )

    def close(self, message: QuitMessage):
        self.model.shutdown(self.state)
        if not (self.model_initialized and self.model_ready_for_update):
            raise RuntimeError(
                "Model called with shutdown while\n"
                + f"initialized: {self.model_initialized}\n"
                + f"ready_for_updates:{self.model_ready_for_update}\n"
                + self.format_uninitialized_properties()
            )

    def format_uninitialized_properties(self) -> str:
        def uninitialized_properties():
            for ds, entity, (comp, prop_name), prop in self.state.iter_properties():
                if (prop.flags & REQUIRED) and not prop.is_initialized():
                    yield "/".join((ds, entity, comp or "", prop_name))

        return "\n".join(f"Uninitialized property: {prop}" for prop in uninitialized_properties())


class TrackedModel(Model):
    """To work with a `TrackedState`, a model developer could create their own `TrackedState()`
    object and work with it directly to track changes and produce updates of changed data. However,
    It is also possible to extend this `TrackedModel` class and let the
    `TrackedModelAdapter` manage the `TrackedState`

    Attributes:
        auto_reset  By default, the TrackedModelAdapter resets tracking information of the
                    state for PUB and/or SUB properties at the appropriate time, so that the model
                    receives a SUB update only once, and PUB properties are published
                    only once. By setting `auto_reset` to `0`, `PUB`, `SUB` or `PUB|SUB`. A model
                    can limit this automatic behaviour and gain full control over which properties
                    are reset and when. However, when overriding the default behaviour, a model
                    must be very careful in implementing this appropriately.
    """

    auto_reset = (
        PUBLISH | SUBSCRIBE
    )  # Set to 0 to manually manage change track resetting. DANGEROUS!

    @abstractmethod
    def setup(
        self,
        state: TrackedState,
        settings: Settings,
        schema: AttributeSchema,
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
        automatically by the `TrackedModelAdapter`. However, additional datasets may be
        requested directly through the `init_data_handler` parameter.

        :param state: The model's TrackedState object, managed by the `TrackedModelAdapter`
        :param settings: global settings
        :param schema: The AttributeSchema with all registered attributes
        :param init_data_handler: a `InitDataHandler` that may be used to retrieve additional
            datasets
        :param logger: a `logging.Logger` instance
        """
        ...

    def initialize(self, state: TrackedState):
        """The `initialize` method is called when all of the `state`'s `INIT` property arrays are
        filled with data. This may be during the model engines initialization phase or during
        `t=0`. Data that is required for the model to initialize property may be published in
        another model's t0-update, and the `TrackedModelAdapter` can wait for this to happen
        before calling `initialize`. When the simulation progresses to `t>0` before the model's
        INIT properties have been filled, an Exception is raised, indicating that the model was
        not ready yet.

        `Model.initialize` may raise `NotReady` to indicate that it does not have its required
        input data yet. This is for example useful if a model has a number `OPT`ional required
        attributes of which at least one must be set. The model would check whether this is the
        case, and raise `NotReady` if it is not. Once a model has succesfully run its initialize
        method, this method will not be called again for the duration of the simulation.

        :param state: The model's TrackedState object, managed by the `TrackedModelAdapter`
        """

    @abstractmethod
    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """The `update` method is called for every update coming from the model engine. However
        it is only called the first time once all PUB properties have their arrays filled with
        data. When the simulation progresses to `t>0` before the model's SUB properties have been
        filled, an Exception is raised, indicating that the model was not ready yet.

        :param state: The model's TrackedState object, managed by the `TrackedModelAdapter`
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

    def get_adapter(self) -> t.Type[ModelAdapterBase]:
        return TrackedModelAdapter
