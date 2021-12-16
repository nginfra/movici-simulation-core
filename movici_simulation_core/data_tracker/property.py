# flake8: noqa: F401
# noinspection PyUnresolvedReferences
from .attribute import (
    INITIALIZE,
    SUBSCRIBE,
    REQUIRED,
    PUBLISH,
    INIT,
    SUB,
    OPT,
    PUB,
    flag_info,
    FlagInfo,
    PropertyField,
    AttributeObject,
    field,
    AttributeOptions,
    Property,
    UniformProperty,
    CSRProperty,
    get_undefined_array,
    create_empty_property,
    create_empty_property_for_data,
    ensure_uniform_data,
    ensure_csr_data,
    ensure_array,
    convert_nested_list_to_csr,
    get_property_aggregate,
    get_array_aggregate,
    property_min,
    property_max,
)
from ..utils.lifecycle import deprecation_warning

deprecation_warning(
    "module 'movici_simulation_core.data_tracker.property' is deprecated, "
    "use 'movici_simulation_core.data_tracker.attribute' instead"
)
