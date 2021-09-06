import numpy as np

from .optional import get_schema_for_parser, type_code_to_data_type
from ..data_tracker.property import PropertySpec, DataType


def to_spec(prop):
    dtype_map = {
        np.dtype("float64"): float,
        np.dtype("int32"): int,
        np.dtype("int8"): bool,
        np.dtype("<U"): str,
    }

    return PropertySpec(
        name=prop.property_name,
        data_type=DataType(dtype_map[prop.dtype], prop.unit_shape, prop.has_indptr),
        component=prop.component_name,
    )


def _get_property_mapping(schema=None) -> dict:
    rv = {}

    if schema is None:
        try:
            schema = get_schema_for_parser()
        except RuntimeError:  # optional dependency is not installed
            return rv

    for prop in schema["prop_schema"].values():
        data_type = type_code_to_data_type(prop["type"]).to_dict()
        component = prop["component_name"] or None
        name = prop["property_name"]
        rv[(component, name)] = PropertySpec(
            name=name,
            component=component,
            data_type=DataType(
                py_type=data_type["dtype"],
                unit_shape=data_type["unit_shape"],
                csr=data_type["has_indptr"],
            ),
        )
    return rv


property_mapping = _get_property_mapping()
