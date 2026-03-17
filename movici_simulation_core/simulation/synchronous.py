import itertools
import traceback
import typing as t

from movici_simulation_core.core import AttributeSchema, set_timeline_info
from movici_simulation_core.core.types import UpdateDataClientBase
from movici_simulation_core.exceptions import FSMDone, FSMError, InvalidMessage
from movici_simulation_core.messages import (
    AcknowledgeMessage,
    ErrorMessage,
    Message,
    ModelMessage,
    NewTimeMessage,
    QuitMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.model_connector import DirectoryInitDataClient, ModelConnector
from movici_simulation_core.networking.stream import BaseStream
from movici_simulation_core.settings import Settings
from movici_simulation_core.types import InternalSerializationStrategy
from movici_simulation_core.utils import filter_data, get_logger, validate_mask

from .common import (
    ActiveModuleInfo,
    ModelFromInstanceInfo,
    ModelFromTypeInfo,
    ServiceInfo,
    SimulationRunner,
)

if t.TYPE_CHECKING:
    pass


class SynchronousOrchestratorStream(BaseStream[ModelMessage]):
    """SynchronousOrchestratorStream is a small implementation of BaseStream so that the
    orchestrator can run in syncrhonous mode. Different from a regular Stream, it is not the means
    to a long running process, ie. its run() method returns quickly
    """

    def __init__(self):
        self.pending_commands: dict[str, Message] = {}

    def run(self):
        """Just a noop"""
        pass

    def send(self, payload: ModelMessage):
        ident, message = payload
        if ident in self.pending_commands:
            raise RuntimeError(f"Cannot have more than one command pending for model {ident}")
        self.pending_commands[ident] = message

    def handle_message(self, payload: ModelMessage):
        if not self.handler:
            raise RuntimeError("Must set a handler using the set_handler() method")
        self.handler(payload)


class NoopSerializer(InternalSerializationStrategy[dict]):
    def dumps(self, data: dict) -> dict:
        return data

    def loads(self, raw_data: dict) -> dict:
        return raw_data


class SynchronousUpdateDataClient(UpdateDataClientBase[dict]):
    counter: t.Iterator[str]

    def __init__(self):
        self.store = {}
        self.reset_counter()

    def get(self, address: str, key: str, mask: t.Optional[dict]) -> dict:
        if not validate_mask(mask):
            raise ValueError("Invalid Mask")
        if key not in self.store:
            raise ValueError("Key not found")

        return filter_data(self.store[key], mask)

    def put(self, data: dict) -> t.Tuple[str, str]:
        key = next(self.counter)
        self.store[key] = data
        return "", key

    def clear(self):
        self.store = {}
        self.reset_counter()

    def close(self):
        pass

    def reset_counter(self):
        self.counter = map(str, itertools.count())


class SynchronousSimulationRunner(SimulationRunner):
    """A SimulationRunner that connects all models and services in a single process, as opposed to
    the DistributedSimulationRunner that sets up models and services that run in a separate proces
    each and have them connect through TCP"""

    def __init__(
        self,
        modules: dict[str, ActiveModuleInfo],
        settings: Settings,
        schema: AttributeSchema,
        strategies: t.Sequence[type],
    ):
        super().__init__(modules, settings, schema, strategies)
        self._ensure_only_supported_services()
        self.model_names = self.settings.model_names

    def _get_logger(self, name: str | None):
        return get_logger(self.settings, name)

    def _ensure_only_supported_services(self):
        service_names = set(k for k, v in self.modules.items() if isinstance(v, ServiceInfo))
        if unsupported_services := (service_names - {"orchestrator", "init_data", "update_data"}):
            raise ValueError(
                "Additional services are not supported when running with distributed=False: "
                ", ".join(unsupported_services)
            )

    def _start_orchestrator(self) -> SynchronousOrchestratorStream:
        service_info = t.cast(ServiceInfo, self.modules["orchestrator"])

        # Would like to cast this as Orchestrator, but can't because of circular import
        orchestrator_cls = t.cast(t.Any, service_info.cls)
        orchestrator = orchestrator_cls()

        stream = SynchronousOrchestratorStream()
        logger = self._get_logger("orchestrator")

        orchestrator.setup(settings=self.settings, stream=stream, logger=logger)
        orchestrator.run()
        return stream

    def _setup_models(self) -> dict[str, ModelConnector]:
        update_client = SynchronousUpdateDataClient()
        init_data_client = DirectoryInitDataClient(self.settings.data_dir)
        serializer = NoopSerializer()
        return {
            name: self._setup_model(
                self.modules[name],
                update_client=update_client,
                init_data_client=init_data_client,
                serializer=serializer,
            )
            for name in self.model_names
        }

    def _setup_model(
        self,
        model_info: ActiveModuleInfo,
        update_client: SynchronousUpdateDataClient,
        init_data_client: DirectoryInitDataClient,
        serializer: NoopSerializer,
    ):
        if isinstance(model_info, ModelFromInstanceInfo):
            model = model_info.instance
        elif isinstance(model_info, ModelFromTypeInfo):
            model = model_info.cls(model_info.config or {})
        else:
            raise ValueError("Unsupported ModelInfo")

        logger = self._get_logger(model_info.name)
        adapter = model.get_adapter()
        wrapped = adapter(model=model, settings=self.settings, logger=logger)
        wrapped.set_schema(self.schema)

        return ModelConnector(
            wrapped,
            update_client,
            init_data_client,
            serialization=serializer,
            name=model_info.name,
        )

    def run(self) -> int:
        set_timeline_info(self.settings.timeline_info)
        orchestrator = self._start_orchestrator()
        models = self._setup_models()
        for name in self.model_names:
            model = models[name]
            response = model.initialize()
            try:
                orchestrator.handle_message((name, response))
            except FSMDone:
                return 0
            except FSMError:
                return 1

        while True:
            for name in self.model_names:
                command = orchestrator.pending_commands.pop(name, None)
                if not command:
                    continue
                self._get_logger("orchestrator").debug(f"Sending: {command}")

                model = models[name]
                response = self.handle_model_command(model, command)
                self._get_logger(name).debug(f"Sending: {response}")
                try:
                    orchestrator.handle_message((name, response))
                except FSMDone:
                    return 0
                except FSMError:
                    return 1

    def handle_model_command(self, model: ModelConnector, command: Message):
        try:
            if isinstance(command, NewTimeMessage):
                model.new_time(command)
                return AcknowledgeMessage()
            if isinstance(command, UpdateMessage):
                return model.update(command)
            if isinstance(command, UpdateSeriesMessage):
                return model.update_series(command)
            if isinstance(command, QuitMessage):
                model.close(command)
                return AcknowledgeMessage()
            else:
                raise InvalidMessage

        except Exception as e:
            logger = self._get_logger(model.name)
            logger.critical(str(e))
            logger.info(traceback.format_exc())
            try:
                model.close(QuitMessage())
            except Exception:  # noqa: S110
                pass
            return ErrorMessage(str(e))
