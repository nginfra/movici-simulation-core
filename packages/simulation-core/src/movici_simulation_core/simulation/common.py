import dataclasses
import typing as t
from multiprocessing import Process

from movici_simulation_core.core import (
    AttributeSchema,
    Model,
    Service,
)

from ..settings import Settings

DEFAULT_SERVICE_ADDRESS = "tcp://127.0.0.1"


@dataclasses.dataclass
class ModuleTypeInfo:
    identifier: str


@dataclasses.dataclass
class ServiceTypeInfo(ModuleTypeInfo):
    cls: t.Type[Service]
    auto_use: bool
    daemon: bool


@dataclasses.dataclass
class ModelTypeInfo(ModuleTypeInfo):
    cls: t.Type[Model]


@dataclasses.dataclass
class ActiveModuleInfo:
    name: str
    daemon: bool
    process: t.Optional[Process] = dataclasses.field(init=False, default=None)


@dataclasses.dataclass
class ServiceInfo(ActiveModuleInfo):
    cls: t.Type[Service]
    address: t.Optional[str] = None

    def fill_service_discovery(self, svc_discovery: t.Dict[str, str]):
        if self.address is None:
            raise ValueError(f"No address set for service '{self.name}'")
        svc_discovery[self.name] = self.address

    def set_port(self, port: int):
        self.address = f"{DEFAULT_SERVICE_ADDRESS}:{port}"


class ModelInfo:
    name: str

    def get_instance(self) -> Model:
        raise NotImplementedError


@dataclasses.dataclass
class ModelFromTypeInfo(ActiveModuleInfo, ModelInfo):
    cls: t.Type[Model]
    config: t.Optional[dict] = None

    def get_instance(self):
        return self.cls(self.config or {})


@dataclasses.dataclass
class ModelFromInstanceInfo(ActiveModuleInfo, ModelInfo):
    instance: Model

    def get_instance(self):
        return self.instance


class SimulationRunner:
    def __init__(
        self,
        modules: dict[str, ActiveModuleInfo],
        settings: Settings,
        schema: AttributeSchema,
        strategies: t.Sequence[type],
    ):
        self.modules = modules
        self.settings = settings
        self.schema = schema
        self.strategies = strategies
