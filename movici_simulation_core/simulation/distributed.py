import multiprocessing
import multiprocessing.connection
import sys
import traceback
import typing as t
from multiprocessing import Process

import zmq
from zmq import Socket

from movici_simulation_core.core import AttributeSchema, Model, ModelAdapterBase, set_timeline_info
from movici_simulation_core.exceptions import StartupFailure
from movici_simulation_core.messages import ErrorMessage, QuitMessage
from movici_simulation_core.model_connector import (
    ConnectorStreamHandler,
    ModelConnector,
    ServicedInitDataHandler,
    UpdateDataClient,
)
from movici_simulation_core.networking import MessageDealerSocket, MessageRouterSocket, Stream
from movici_simulation_core.settings import Settings
from movici_simulation_core.types import (
    ExternalSerializationStrategy,
    InternalSerializationStrategy,
)
from movici_simulation_core.utils import get_logger, strategies

from .common import (
    DEFAULT_SERVICE_ADDRESS,
    ModelFromInstanceInfo,
    ModelFromTypeInfo,
    ModelInfo,
    ServiceInfo,
    SimulationRunner,
)


class DistributedSimulationRunner(SimulationRunner):
    """SimulationRunner that runs every model and service in its own separate process. The models
    and services then connect using TCP and zeroMQ
    """

    def run(self) -> int:
        """
        starts up services from config and auto_use using ServiceRunner. Collects service addresses
        starts up models from config with service addresses for discovery using ModelRunner
        tracks models and services, terminates when necessary (question: when do we terminate
        everything and when does the orchestrator take over exception handling?)
        """
        self._start_services()
        self._start_models()
        procs = (mod.process for mod in self.modules if mod.process is not None and not mod.daemon)
        self._wait_for_processes(procs)
        return self.exit_code

    def _wait_for_processes(self, processes: t.Iterable[Process]):
        exit_code = 0
        for proc in processes:
            proc.join()
            exit_code = max(exit_code, proc.exitcode or 0)
        self.exit_code = exit_code

    def _start_services(self):
        svc_discovery: t.Dict[str, str] = {}

        for service in (module for module in self.modules if isinstance(module, ServiceInfo)):
            self._start_service(service)
            service.fill_service_discovery(svc_discovery)
        self.settings.service_discovery = svc_discovery

    def _start_models(self):
        for model in (module for module in self.modules if isinstance(module, ModelInfo)):
            self._start_model(model)

    def _start_service(self, service: ServiceInfo):
        return ServiceRunner(
            service, self.settings, strategies=self.strategies, schema=self.schema
        ).start()

    def _start_model(self, model: ModelInfo):
        return ModelRunner(
            model, self.settings, strategies=self.strategies, schema=self.schema
        ).start()


class ProcessRunner:
    # Explicitly set start method, so that we're not dependent on global python state
    # that may be modified by other libraries
    _start_method = "spawn" if sys.platform in ("darwin", "win32") else "fork"
    ctx = multiprocessing.get_context(_start_method)

    def __init__(
        self, strategies: list[type] | None, schema: t.Optional[AttributeSchema] = None
    ) -> None:
        self.strategies = strategies
        self.schema = schema

    def prepare_subprocess(self):
        self._configure_strategies()

    def _configure_strategies(self):
        if self.strategies is not None:
            for strat in self.strategies:
                strategies.set(strat)
        strategies.get_instance(ExternalSerializationStrategy, schema=self.schema)
        strategies.get_instance(InternalSerializationStrategy)


class ServiceRunner(ProcessRunner):
    """
    Provides logic for:

    * Creating a Pipe that the Service can use to announce its port
    * Creating a Process (daemon=True) that runs Service. Using a wrapping function this
        subprocess will

        * create the service
        * create a (router) socket
        * announce the port
        * run the Service
        * raise exception on failure

    * Fills the ServiceInfo object
    * Raising an exception if it fails to announce the port in time

    By creating the process as deamon=True, services cannot spawn their own subprocesses but they
    can be easily terminated
    """

    TIMEOUT = 5

    def __init__(
        self,
        service: ServiceInfo,
        settings: Settings,
        strategies: list[type] | None = None,
        schema: t.Optional[AttributeSchema] = None,
    ):
        super().__init__(strategies=strategies, schema=schema)
        self.service = service
        self.settings = settings

    def start(self):
        recv, send = self.ctx.Pipe(duplex=False)
        proc = self.ctx.Process(
            target=self.entry_point,
            args=(send,),
            daemon=self.service.daemon,
            name="Process-" + self.service.name,
        )
        proc.start()
        poll_success = recv.poll(self.TIMEOUT)
        if not poll_success:
            raise StartupFailure(f"Service {self.service.name} failed to start in time")

        self.service.process = proc
        self.service.set_port(recv.recv())

    def entry_point(self, conn: multiprocessing.connection.Connection):
        self.prepare_subprocess()
        self.settings.name = self.service.name
        zmq_socket, port = self._get_bound_socket(self.service.name)
        socket = MessageRouterSocket(zmq_socket)
        logger = get_logger(self.settings)
        stream = Stream(socket, logger=logger)
        inst = self.service.cls()
        inst.setup(settings=self.settings, stream=stream, logger=logger, socket=socket)
        conn.send(port)
        result = inst.run()
        if result not in (None, 0):
            sys.exit(result)

    @staticmethod
    def _get_bound_socket(name, addr=DEFAULT_SERVICE_ADDRESS) -> t.Tuple[zmq.Socket, int]:
        context = zmq.Context.instance()
        socket: zmq.Socket = context.socket(zmq.ROUTER)
        socket.set(zmq.IDENTITY, name.encode())
        port = socket.bind_to_random_port(addr)
        return socket, port


class ModelRunner(ProcessRunner):
    """
    Provides logic for:

    * Creating a Process (daemon=False) that runs a Model. Using a wrapping function, this
        subprocess will:

        * create the model with its model adapter
        * create a (dealer) socket
        * run the model
        * catch exceptions from model, send ERROR message
        * raise exceptions when not directly from model

    * Fills the ModelInfo object

    By creating the process as deamon=False, models can spawn their own subprocesses
    """

    update_handler: t.Optional[UpdateDataClient] = None
    init_data_handler: t.Optional[ServicedInitDataHandler] = None
    socket: t.Optional[MessageDealerSocket] = None

    def __init__(
        self,
        model_info: ModelInfo,
        settings: Settings,
        strategies: list[type] | None = None,
        schema: t.Optional[AttributeSchema] = None,
    ):
        super().__init__(strategies=strategies, schema=schema)
        self.settings = settings
        self.model_info = model_info

    def start(self):
        proc = self.ctx.Process(
            target=self.entry_point, daemon=False, name="Process-" + self.model_info.name
        )
        proc.start()
        self.model_info.process = proc

    def entry_point(self):
        self.prepare_subprocess()
        self.settings.name = self.model_info.name
        logger = get_logger(self.settings)
        self.socket = self._get_orchestrator_socket()
        model = None

        try:
            set_timeline_info(self.settings.timeline_info)
            stream = Stream(self.socket, logger=logger)
            model = self._get_model(logger)

            self._setup_model(stream, model)
            stream.run()

        except Exception as e:
            self.socket.send(ErrorMessage(str(e)))
            logger.critical(str(e))
            logger.info(traceback.format_exc())
            if model:
                # noinspection PyBroadException
                try:
                    model.close(QuitMessage())
                except Exception:  # noqa: S110
                    pass
            sys.exit(1)
        finally:
            self.close()

    def _get_model(self, logger):
        model = self._ensure_model()
        adapter = model.get_adapter()
        wrapped = adapter(model=model, settings=self.settings, logger=logger)
        wrapped.set_schema(self.schema)
        return wrapped

    def _ensure_model(self) -> Model:
        if isinstance(self.model_info, ModelFromInstanceInfo):
            return self.model_info.instance
        elif isinstance(self.model_info, ModelFromTypeInfo):
            return self.model_info.cls(self.model_info.config or {})
        else:
            raise ValueError("Unsupported ModelInfo")

    def _setup_model(
        self,
        stream,
        model: ModelAdapterBase,
    ):
        self.update_handler = UpdateDataClient(
            self.settings.name, self.settings.service_discovery["update_data"]
        )
        self.init_data_handler = ServicedInitDataHandler(
            self.settings.name, server=self.settings.service_discovery["init_data"]
        )
        serialization = strategies.get_instance(InternalSerializationStrategy)
        connector = ModelConnector(
            model, self.update_handler, self.init_data_handler, serialization=serialization
        )
        stream_handler = ConnectorStreamHandler(connector, stream)
        stream_handler.initialize()

    def _get_orchestrator_socket(self):
        addr = self.settings.service_discovery["orchestrator"]
        context = zmq.Context.instance()
        socket: Socket = context.socket(zmq.DEALER)
        socket.set(zmq.IDENTITY, self.settings.name.encode())
        socket.connect(addr)
        return MessageDealerSocket(socket)

    def close(self):
        self.socket.close(linger=1000)  # ms
        if self.init_data_handler:
            self.init_data_handler.close()
        if self.update_handler:
            self.update_handler.close()
        if zmq.Context._instance is not None:
            zmq.Context.instance().term()
