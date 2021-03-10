import typing as t
from abc import abstractmethod

from model_engine import BaseModel, Config, TimeStamp, Result, DataFetcher
from model_engine.model_driver.data_handlers import DType
from movici_simulation_core.exceptions import NotReady

from ..data_tracker.property import INIT, SUB, PUB
from ..data_tracker.state import TrackedState


class TrackedBaseModelAdapter(BaseModel):
    use_numpy = True

    def __init__(self, model: "TrackedBaseModel", name: str, config: Config):
        super().__init__(name, config)
        self.model = model
        self.state = TrackedState(logger=self.logger)
        self.model_initialized = False
        self.model_ready_for_update = False

    def initialize(self, data_fetcher: DataFetcher):
        self.model.setup(
            state=self.state,
            config=self.config.MODEL_SETTINGS,
            scenario_config=self.config,
            data_fetcher=data_fetcher,
        )
        self.download_init_data(data_fetcher)
        self.try_initialize()

    def download_init_data(self, data_fetcher: DataFetcher):
        data_fetcher.as_numpy_array = True
        for dataset_name, _ in self.state.iter_datasets():
            data_dtype, data_dict = data_fetcher.get(dataset_name)
            if data_dtype not in [DType.JSON, DType.MSGPACK]:
                raise ValueError(f"'{dataset_name}' not of type {DType.JSON} or {DType.MSGPACK}")

            self.state.receive_update(data_dict)

    def get_data_filter(self) -> dict:
        return self.state.get_pub_sub_filter()

    def update(self, time_stamp: TimeStamp, update_dict=None) -> Result:
        self.state.receive_update(update_dict)
        self.try_initialize()

        if not self.model_ready_for_update and self.state.is_ready_for(SUB):
            self.model_ready_for_update = True

        next_time = None

        if self.model_ready_for_update:
            next_time = self.model.update(self.state, time_stamp)
            (self.model.auto_reset & SUB) and self.state.reset_tracked_changes(SUB)

        update = self.state.generate_update(PUB)
        (self.model.auto_reset & PUB) and self.state.reset_tracked_changes(PUB)

        return Result(time_stamp, update, next_time)

    def try_initialize(self):
        if not self.model_initialized and self.state.is_ready_for(INIT):
            try:
                self.model.initialize(self.state)
            except NotReady:
                return
            self.model_initialized = True

    def new_time(self, time_stamp: TimeStamp):
        self.model.new_time(time_stamp)
        if not (self.model_initialized or self.model_ready_for_update) and time_stamp.time > 0:
            raise RuntimeError(
                f"Model [{self.name}] called with timestamp >0 while"
                f" initialized: {self.model_initialized} ,"
                f" ready_for_updates:{self.model_ready_for_update}"
            )

    def shutdown(self):
        self.model.shutdown()
        if not (self.model_initialized or self.model_ready_for_update):
            raise RuntimeError(
                f"Model [{self.name}] called with shutdown while"
                f" initialized: {self.model_initialized} ,"
                f" ready_for_updates:{self.model_ready_for_update}"
            )


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

    @abstractmethod
    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
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
        requested directly through the `data_fetcher` parameter.

        :param state: The model's TrackedState object, managed by the `TrackedBaseModelAdapter`
        :param config: The model's specific config section from the scenario config
        :param scenario_config: The full scenario config (as an object)
        :param data_fetcher: a `DataFetcher` that may be used to retrieve additional datasets
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
    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        """The `update` method is called for every update coming from the model engine. However
        it is only called the first time once all PUB properties have their arrays filled with
        data. When the simulation progresses to `t>0` before the model's SUB properties have been
        filled, an Exception is raised, indicating that the model was not ready yet.

        :param state: The model's TrackedState object, managed by the `TrackedBaseModelAdapter`
        :param time_stamp: The current simulation `TimeStamp`

        :return: an optional `TimeStamp` indicating the next time a model want to be woken up, as
                 per the model engine's protocol
        """

    def new_time(self, time_stamp: TimeStamp):
        """Called for every change of timestamp during a simulation run. This method is called
        before checking whether the state is ready for INIT or PUB and may be called before the
        `initialize` and `update` methods have been called the first time.
        """

    def shutdown(self):
        """Called when a simulation ends (either due to it being finished or one of the models
        raises an exception). The model may implement this method to clean up local resources.
        This method may be called before the `initialize` and `update` methods have been called
        the first time"""


def model_factory(model_cls: t.Type[TrackedBaseModel]):
    """Helper function to use in the `run_{model}.py` entry point script. This helper wraps the
    model in a `TrackedBaseModelAdapter` before giving it over to the model driver. The entry
    point's `execute` function takes the result of this helper: eg.
    `execute(model_factory(MyTrackedModel))`

    :param model_cls: a class (not an instance) inheriting from `TrackedBaseModel`
    """

    def create_model(name: str, config: Config):
        return TrackedBaseModelAdapter(model_cls(), name, config)

    return create_model
