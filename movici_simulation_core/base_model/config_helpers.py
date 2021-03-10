import typing as t

import model_engine.dataset_manager as dm
import numpy as np
from model_engine.dataset_manager import property_definition

from ..data_tracker.property import PropertySpec, DataType


def to_spec(prop: t.Type[dm.Property]):
    dtype_map = {
        np.bool: bool,
        np.float64: float,
        np.int32: int,
        str: str,
        bool: bool,
        float: float,
        int: int,
    }

    return PropertySpec(
        name=prop.property_name,
        data_type=DataType(dtype_map[prop.dtype], prop.unit_shape, prop.has_indptr),
        component=prop.component_name,
    )


def _get_property_mapping(pd, rv=None) -> t.Dict:
    if rv is None:
        rv = {}
    for obj in vars(pd).values():
        if isinstance(obj, type):
            if issubclass(obj, dm.Component):
                _get_property_mapping(obj, rv)
            if issubclass(obj, dm.Property):
                rv[(obj.component_name, obj.property_name)] = to_spec(obj)
    return rv


property_mapping = _get_property_mapping(property_definition)
