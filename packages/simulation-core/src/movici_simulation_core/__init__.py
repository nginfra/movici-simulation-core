import importlib.metadata

from .base_models import SimpleModel, TrackedModel
from .core import (
    INIT,
    NP_TYPES,
    OPT,
    PUB,
    SUB,
    UNDEFINED,
    AttributeOptions,
    AttributeSchema,
    AttributeSpec,
    CSRAttribute,
    DataType,
    EntityGroup,
    EntityInitDataFormat,
    Extensible,
    Index,
    Model,
    Moment,
    Plugin,
    Service,
    TimelineInfo,
    TrackedArray,
    TrackedCSRArray,
    TrackedState,
    UniformAttribute,
    UpdateDataFormat,
    field,
    get_global_schema,
    get_timeline_info,
    set_timeline_info,
)
from .model_connector import (
    DirectoryInitDataClient,
    InitDataHandler,
    ServicedInitDataClient,
    UpdateDataClient,
)
from .settings import Settings
from .simulation import Simulation
from .validate import validate_and_process

__all__ = [
    "SimpleModel",
    "TrackedModel",
    "Simulation",
    "INIT",
    "NP_TYPES",
    "OPT",
    "PUB",
    "SUB",
    "UNDEFINED",
    "AttributeOptions",
    "AttributeSchema",
    "AttributeSpec",
    "CSRAttribute",
    "DataType",
    "EntityGroup",
    "EntityInitDataFormat",
    "Extensible",
    "Index",
    "Model",
    "Moment",
    "Plugin",
    "Service",
    "TimelineInfo",
    "TrackedArray",
    "TrackedCSRArray",
    "TrackedState",
    "UniformAttribute",
    "UpdateDataFormat",
    "field",
    "get_global_schema",
    "get_timeline_info",
    "set_timeline_info",
    "validate_and_process",
    "Settings",
    "DirectoryInitDataClient",
    "InitDataHandler",
    "ServicedInitDataClient",
    "UpdateDataClient",
]


try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"  # Fallback for development mode
