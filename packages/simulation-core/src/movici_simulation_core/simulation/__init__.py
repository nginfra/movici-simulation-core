import typing as t

from movici_simulation_core.core import (
    AttributeSchema,
    AttributeSpec,
    EntityInitDataFormat,
    Extensible,
    Model,
    Plugin,
    Service,
    TimelineInfo,
    UpdateDataFormat,
    configure_global_plugins,
)
from movici_simulation_core.simulation.common import (
    ActiveModuleInfo,
    ModelFromInstanceInfo,
    ModelFromTypeInfo,
    ModelInfo,
    ModelTypeInfo,
    ServiceInfo,
    ServiceTypeInfo,
)
from movici_simulation_core.utils import strategies

from ..settings import Settings
from .distributed import DistributedSimulationRunner
from .in_process import InProcessSimulationRunner


class Simulation(Extensible):
    """Main class for starting a simulation. A simulation can be configured from a scenario config
    using `Simulation.configure` or manually using the `Simulation.add_model` and
    `Simulation.set_timeline_info` methods. A simulation can then be started using
    `Simulation.run`. By default, every model and service runs in its own subprocess
    (`multiprocessing.Process`) for parallelism, but this can be turned off by providing the
    ``distributed=False`` argument when instantiating the ``Simulation``.

    """

    service_types: t.Dict[str, ServiceTypeInfo]
    model_types: t.Dict[str, ModelTypeInfo]
    active_modules: t.Dict[str, ActiveModuleInfo]
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
        class. When added as a class, instantiation of the model is done inside its subprocess,
        which, depending on the model, could help with certain forking issues

        :param name: the model name, a model name must be unique within a simulation
        :param model: the model class (or instance)
        :param config: the model config dictionary to instantiate the model, when the model is
            given as a class

        """
        if isinstance(model, type) and issubclass(model, Model):
            self.active_modules[name] = ModelFromTypeInfo(
                name, daemon=False, cls=model, config=config
            )
        elif isinstance(model, Model):
            self.active_modules[name] = ModelFromInstanceInfo(name, daemon=False, instance=model)
        else:
            raise TypeError(f"Invalid model type '{model.__class__}")
        self.schema.add_attributes(model.get_schema_attributes())

    def set_timeline_info(self, timeline_info: TimelineInfo):
        """
        When configuring the Simulation manually, use this method to add timeline information
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
        self._activate_services()
        self._activate_models()
        if self.settings.distributed:
            runner = DistributedSimulationRunner(
                self.active_modules, self.settings, schema=self.schema, strategies=self.strategies
            )
        else:
            runner = InProcessSimulationRunner(
                self.active_modules, self.settings, schema=self.schema, strategies=self.strategies
            )
        self.exit_code = runner.run()
        return self.exit_code

    def _activate_services(self):
        active_svc_names = set(name for name, svc in self.service_types.items() if svc.auto_use)
        for name in self.settings.service_types:
            if name not in self.service_types:
                raise ValueError(f"Unknown service '{name}'")
            active_svc_names.add(name)
        for name in active_svc_names:
            svc = self.service_types[name]
            self.active_modules[name] = ServiceInfo(name, cls=svc.cls, daemon=svc.daemon)

    def _activate_models(self):
        for model_config in self.settings.models:
            name = model_config["name"]
            model_type = model_config["type"]
            if (info := self.model_types.get(model_type)) is None:
                raise ValueError(f"Unknown model type '{model_type}' for model '{name}")
            self.active_modules[name] = ModelFromTypeInfo(
                name, cls=info.cls, config=model_config, daemon=False
            )

        self.settings.model_names = [module.name for module in self.active_models]

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
