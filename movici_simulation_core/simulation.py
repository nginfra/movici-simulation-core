import dataclasses
import multiprocessing
import multiprocessing.connection
import sys
import traceback
import typing as t
from multiprocessing import Process

import zmq
from zmq import Socket

from movici_simulation_core.core import (
    AttributeSchema,
    AttributeSpec,
    EntityInitDataFormat,
    Extensible,
    Model,
    ModelAdapterBase,
    Plugin,
    Service,
    TimelineInfo,
    UpdateDataFormat,
    configure_global_plugins,
    set_timeline_info,
)
from movici_simulation_core.exceptions import StartupFailure
from movici_simulation_core.messages import ErrorMessage, QuitMessage
from movici_simulation_core.model_connector import (
    ConnectorStreamHandler,
    ModelConnector,
    ServicedInitDataHandler,
    UpdateDataClient,
)
from movici_simulation_core.networking import MessageDealerSocket, MessageRouterSocket, Stream
from movici_simulation_core.types import (
    ExternalSerializationStrategy,
    InternalSerializationStrategy,
)
from movici_simulation_core.utils import get_logger, strategies

from .settings import Settings

DEFAULT_SERVICE_ADDRESS = "tcp://127.0.0.1"


@dataclasses.dataclass
class ModuleTypeInfo:
    identifier: str


@dataclasses.dataclass
class ServiceTypeInfo(ModuleTypeInfo):
    cls: t.Type[Service]
    auto_use: bool
    daemon: bool = True


@dataclasses.dataclass
class ModelTypeInfo(ModuleTypeInfo):
    cls: t.Type[Model]


class ProcessInfo(t.Protocol):
    daemon: bool
    process: t.Optional[Process]


@dataclasses.dataclass
class ActiveModuleInfo:
    name: str
    process: t.Optional[Process] = dataclasses.field(init=False, default=None)


@dataclasses.dataclass
class ServiceInfo(ActiveModuleInfo):
    cls: t.Type[Service]
    address: t.Optional[str] = None
    daemon: bool = True

    def fill_service_discovery(self, svc_discovery: t.Dict[str, str]):
        if self.address is None:
            raise ValueError(f"No address set for service '{self.name}'")
        svc_discovery[self.name] = self.address

    def set_port(self, port: int):
        self.address = f"{DEFAULT_SERVICE_ADDRESS}:{port}"


@dataclasses.dataclass
class ModelInfo(ActiveModuleInfo):
    daemon: bool = dataclasses.field(init=False, default=None)


@dataclasses.dataclass
class ModelFromTypeInfo(ModelInfo):
    cls: t.Type[Model]
    config: t.Optional[dict] = None


@dataclasses.dataclass
class ModelFromInstanceInfo(ModelInfo):
    instance: Model


class Simulation(Extensible):
    """Main class for starting a simulation. A simulation can be configured from a scenario config
    using `Simulation.configure` or manually using the `Simulation.add_model` and
    `Simulation.set_timeline_info` methods. A simulation can then be started using
    `Simulation.run`. Every model and service runs in its own subprocess
    (`multiprocessing.Process`) for parallelism.

    """

    service_types: t.Dict[str, ServiceTypeInfo]
    model_types: t.Dict[str, ModelTypeInfo]
    active_modules: t.Dict[str, ProcessInfo]
    schema: AttributeSchema
    timeline_info: t.Optional[TimelineInfo] = None
    exit_code: int = None

    def __init__(self, use_global_plugins=True, debug=False, **settings):
        """
        :param use_global_plugins: Use the plugins that are installed using setuptools
            entry_points
        :param debug: log debug information
        :param settings: additional settings that will be passed directly into the `Settings`
            object
        """
        self.service_types = {}
        self.model_types = {}
        self.active_modules = {}
        self.schema = AttributeSchema()

        self.settings = Settings(**settings)
        if debug:
            self.settings.log_level = "DEBUG"

        self.strategies: t.List[type] = []
        self.set_default_strategies()

        if use_global_plugins:
            configure_global_plugins(self)

    @property
    def active_models(self):
        return [mod for mod in self.active_modules.values() if isinstance(mod, ModelInfo)]

    @property
    def active_services(self):
        return [mod for mod in self.active_modules.values() if isinstance(mod, ServiceInfo)]

    def set_default_strategies(self):
        self.set_strategy(UpdateDataFormat)
        self.set_strategy(EntityInitDataFormat)

    def configure(self, config: dict):
        """Configure a simulation by scenario config. All model types and additional services that
        are present in the simulation must first be registered as a plugin (see `Simulation.use`).
        """
        self.settings.apply_scenario_config(config)

    def add_model(self, name: str, model: t.Union[Model, t.Type[Model]], config=None):
        """
        Manually add a model to a Simulation. A model can be added as an instance, or as
        class. When added as a class, instantiation is of the model is done inside its subprocess,
        which, depending on the model, could help with certain forking issues

        :param name: the model name, a model name must be unique within a simulation
        :param model: the model class (or instance)
        :param config: the model config dictionary to instantiate the model, when the model is
            given as a class

        """
        if isinstance(model, type) and issubclass(model, Model):
            self.active_modules[name] = ModelFromTypeInfo(name, model, config)
        elif isinstance(model, Model):
            self.active_modules[name] = ModelFromInstanceInfo(name, model)
        else:
            raise TypeError(f"Invalid model type '{model.__class__}")
        self.schema.add_attributes(model.get_schema_attributes())

    def set_timeline_info(self, timeline_info: TimelineInfo):
        """
        When configuring the Simulation manually, use this  method to add timeline information
        the simulation.

        :param timeline_info: the `TimelineInfo` object for this simulation

        """
        self.settings.timeline_info = timeline_info

    def run(self) -> int:
        """
        starts up services from config and auto_use using ServiceRunner. Collects service addresses
        starts up models from config with service addresses for discovery using ModelRunner
        tracks models and services, terminates when necessary (question: when do we terminate
        everything and when does the orchestrator take over exception handling?)
        """
        self._prepare()
        self._start_services()
        self._start_models()
        procs = (
            mod.process
            for mod in self.active_modules.values()
            if mod.process is not None and not mod.daemon
        )
        self._wait_for_processes(procs)
        return self.exit_code

    def _wait_for_processes(self, processes: t.Iterable[Process]):
        exit_code = 0
        for proc in processes:
            proc.join()
            exit_code = max(exit_code, proc.exitcode)
        self.exit_code = exit_code

    def _prepare(self):
        self._activate_services()
        self._activate_models()

    def _activate_services(self):
        active_svc_names = set(name for name, svc in self.service_types.items() if svc.auto_use)
        for name in self.settings.service_types:
            if name not in self.service_types:
                raise ValueError(f"Unknown service '{name}'")
            active_svc_names.add(name)
        for name in active_svc_names:
            svc = self.service_types[name]
            self.active_modules[name] = ServiceInfo(name, svc.cls, daemon=svc.daemon)

    def _activate_models(self):
        for model_config in self.settings.models:
            name = model_config["name"]
            model_type = model_config["type"]
            if (info := self.model_types.get(model_type)) is None:
                raise ValueError(f"Unknown model type '{model_type}' for model '{name}")
            self.active_modules[name] = ModelFromTypeInfo(name, info.cls, model_config)

        self.settings.model_names = [module.name for module in self.active_models]

    def _start_services(self):
        svc_discovery: t.Dict[str, str] = {}

        for module in self.active_services:
            self._start_service(module)
            module.fill_service_discovery(svc_discovery)
        self.settings.service_discovery = svc_discovery

    def _start_models(self):
        for module in self.active_models:
            self._start_model(module)

    def _start_service(self, service: ServiceInfo):
        return ServiceRunner(
            service, self.settings, strategies=self.strategies, schema=self.schema
        ).start()

    def _start_model(self, model: ModelInfo):
        return ModelRunner(
            model, self.settings, strategies=self.strategies, schema=self.schema
        ).start()

    def use(self, plugin: t.Type[Plugin]):
        """Using a plugin allows a model_type or service to register itself for availability. This
        method calls `Plugin.install` with the Simulation as its argument. The plugins can then use
        the methods `Simulation.register_service`, `Simulation.register_model_type` and
        `Simulation.register_attributes`.
        """
        plugin.install(self)

    def register_service(
        self, identifier: str, service: t.Type[Service], auto_use=False, daemon=True
    ):
        """Register a `Service` for this `Simulation`. After registration, a service can either be
        used automatically or activated (ie. used in this Simulation) through the
        `Simulation.configure` method.

        :param identifier: A unique name to identify the Simulation by
        :param service: The service class that will be used when this service is activated
        :param auto_use: When a service is registered as `auto_use`, an instance of this Service is
            always available in the `Simulation`
        :param daemon: Services can be either daemonic or not. Daemonic services are run as
            fire-and-forget and will be terminated/killed once the simulation has ended.
            Non-daemonic services are joined before exiting the simulation (and must have some way
            to exit). Non-daemonic services have the benefit that they can spawn their own
            subprocesses

        """
        self.service_types[identifier] = ServiceTypeInfo(
            identifier, cls=service, auto_use=auto_use, daemon=daemon
        )

    def register_model_type(self, identifier: str, model_type: t.Type[Model]):
        """Register a `Model` type to use in a simulation. Upon registration, this method also
        registers any attributes (ie `AttributeSpec`s) from the models
        `Model.get_schema_attributes` method.

        :param identifier: A unique identifier for a model type. When configuring the `Simulation`
            using `Simulation.configure`, this identifier must match the `type` key of the model
            config
        :param model_type: The `Model` subclass to register

        """
        self.model_types[identifier] = ModelTypeInfo(identifier, cls=model_type)
        self.schema.add_attributes(model_type.get_schema_attributes())

    def register_attributes(self, attributes: t.Iterable[AttributeSpec]):
        """Register attributes for this Simulation.

        :param attributes: an iterable of `AttributeSpec` objects

        """
        self.schema.add_attributes(attributes)

    def set_strategy(self, strat):
        self.strategies.append(strat)
        strategies.set(strat)


class Runner:
    ctx = multiprocessing.get_context()

    def __init__(
        self, strategies: t.List[type], schema: t.Optional[AttributeSchema] = None
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


class ServiceRunner(Runner):
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
        strategies: t.List[type] = None,
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
        socket: Socket = context.socket(zmq.ROUTER)
        socket.set(zmq.IDENTITY, name.encode())
        port = socket.bind_to_random_port(addr)
        return socket, port


class ModelRunner(Runner):
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
        strategies: t.Optional[t.List[type]] = None,
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
                except Exception:  # nosec
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
        connector = ModelConnector(model, self.update_handler, self.init_data_handler)
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
