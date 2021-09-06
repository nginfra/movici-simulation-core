import typing as t
import warnings

import msgpack
import numpy as np
import ujson as json

from movici_simulation_core.legacy_base_model.config_helpers import property_mapping
from movici_simulation_core.core.schema import (
    PropertySpec,
    DataType,
    DEFAULT_ROWPTR_KEY,
    has_rowptr_key,
    infer_data_type_from_array,
)
from movici_simulation_core.data_tracker.property import CSRProperty, UniformProperty
from movici_simulation_core.types import NumpyPropertyData, PropertyIdentifier


class EntityInitDataFormat:
    attributes: t.Dict[PropertyIdentifier, PropertySpec]

    def __init__(self, attributes: t.Sequence[PropertySpec] = (), non_data_dict_keys=("general",)):
        attributes = attributes or property_mapping.values()

        self.attributes = {(spec.component, spec.name): spec.data_type for spec in attributes}
        self.non_data_dict_keys = set(non_data_dict_keys)

    def loads(self, raw: t.Union[str, bytes], **kwargs):
        list_data = json.loads(raw, **kwargs)
        if not isinstance(list_data, dict):
            raise TypeError("Dataset must be dictionary")
        return {
            key: (
                self.load_data_section(val)
                if isinstance(val, dict) and key not in self.non_data_dict_keys
                else val
            )
            for key, val in list_data.items()
        }

    def dumps(self, dataset: dict, **kwargs) -> str:
        return json.dumps(
            {
                key: (
                    dump_dataset_data(val)
                    if isinstance(val, dict) and key not in self.non_data_dict_keys
                    else val
                )
                for key, val in dataset.items()
            },
            **kwargs,
        )

    def load_data_section(self, data: dict) -> dict:
        rv = {}
        if data is None:
            return rv
        if not isinstance(data, dict):
            raise TypeError("'data' section must be dict")
        return {key: self.load_entity_group(val) for key, val in data.items()}

    def load_entity_group(self, entity_group: dict):
        if not isinstance(entity_group, dict):
            raise TypeError("Entity group data must be dict")
        return {key: self.load_attribute(data, key) for key, data in entity_group.items()}

    def load_attribute(
        self, attr_data: t.Union[dict, list], name: str, component: t.Optional[str] = None
    ) -> dict:
        if isinstance(attr_data, dict):
            return {
                key: self.load_attribute(data, name=key, component=name)
                for key, data in attr_data.items()
            }
        elif isinstance(attr_data, list):
            data_type = self.attributes.get((component, name))
            if not data_type:
                warnings.warn(
                    f"Inferring datatype of attribute"
                    f" '{component+'/'+name if component else name}'"
                )
            try:
                return parse_list(attr_data, data_type)
            except TypeError as e:
                raise TypeError(f"Error when parsing data for {component}/{name}") from e
        else:
            raise TypeError("attribute data must be dict (component) or list (attribute)")


def parse_list(data: list, data_type: t.Optional[DataType] = None) -> NumpyPropertyData:
    if not len(data):
        return {"data": np.array([], dtype=float)}
    data_type = data_type or infer_data_type_from_list(data)

    if data_type.csr:
        return parse_csr_list(data, data_type)
    return parse_uniform_list(data, data_type)


def infer_data_type_from_list(data: list):
    # TODO: check for nones
    # TODO: check for empty lists
    # TODO: check for int/float (if first item is int, but second is float)
    # TODO: check for unit shape

    def infer_pytype(d: list):
        if not len(d):
            return float
        first_item = d[0]
        if first_item is None:
            return float
        if (rv := type(first_item)) not in (int, float, bool, str):
            raise TypeError("Could not infer datatype")
        return rv

    if not len(data):
        pytype, csr = float, False

    elif isinstance(data[0], list):
        pytype = infer_pytype(data[0])
        csr = True
    else:
        pytype = infer_pytype(data)
        csr = False

    return DataType(pytype, unit_shape=(), csr=csr)


def parse_uniform_list(data: list, data_type: DataType) -> NumpyPropertyData:
    return {"data": create_array(data, data_type)}


def parse_csr_list(data: t.List[list], data_type: DataType) -> NumpyPropertyData:
    flattened = []
    row_ptr = [0]
    for item in data:
        flattened.extend(item)
        row_ptr.append(len(flattened))
    return {
        "data": create_array(flattened, data_type),
        DEFAULT_ROWPTR_KEY: np.array(row_ptr, dtype=np.uint32),
    }


def create_array(uniform_data: list, data_type: DataType):
    undefined = np.full(data_type.unit_shape, data_type.undefined)

    for idx, val in enumerate(uniform_data):
        if attribute_is_undefined(val):
            uniform_data[idx] = undefined

    return np.array(uniform_data, dtype=data_type.np_type)


def attribute_is_undefined(val):
    if val is None:
        return True
    elif isinstance(val, list):
        return any(attribute_is_undefined(v) for v in val)
    return False


def dump_dataset_data(dataset_data: dict) -> dict:
    return {
        key: (
            dump_attribute(val, infer_data_type_from_array(val))
            if "data" in val
            else dump_dataset_data(val)
        )
        for key, val in dataset_data.items()
    }


def dump_attribute(attribute_dict: dict, data_type):
    if has_rowptr_key(attribute_dict):
        return dump_csr_attribute(attribute_dict, data_type)
    return dump_uniform_attribute(attribute_dict, data_type)


def dump_csr_attribute(attribute_dict, data_type):
    attr = CSRProperty(attribute_dict, data_type)
    undefined_indices = set(np.flatnonzero(attr.is_undefined()))
    return [
        (None if row_idx in undefined_indices else attr.csr.get_row(row_idx).tolist())
        for row_idx in range(len(attr))
    ]


def dump_uniform_attribute(attribute_dict, data_type):
    attr = UniformProperty(attribute_dict, data_type)
    rv = attr.array.tolist()
    for idx in np.flatnonzero(attr.is_undefined()):
        rv[idx] = None
    return rv


class UpdateDataFormat:
    CURRENT_VERSION = 1

    def loads(self, raw_bytes: bytes):
        return msgpack.unpackb(raw_bytes, object_hook=self.decode_numpy_array)

    def dumps(self, data: dict):
        return msgpack.packb(data, default=self.encode_numpy_array)

    @classmethod
    def decode_numpy_array(cls, obj):
        ver = obj.get("__np_encode_version__", None)
        if ver is None:
            return obj
        if ver == 1:
            return np.ndarray(shape=obj["shape"], dtype=obj["dtype"], buffer=obj["data"]).copy()
        raise TypeError("Unsupported Numpy encoding version")

    @classmethod
    def encode_numpy_array(cls, obj):
        if isinstance(obj, np.ndarray):
            return {
                "__np_encode_version__": cls.CURRENT_VERSION,
                "dtype": obj.dtype.str,
                "shape": obj.shape,
                "data": obj.data,
            }
        return obj


def load_update(raw_bytes: bytes):
    return UpdateDataFormat().loads(raw_bytes)


def dump_update(data: dict):
    return UpdateDataFormat().dumps(data)


def extract_dataset_data(update_or_init_data):
    if "data" in update_or_init_data and isinstance(name := update_or_init_data.get("name"), str):
        yield (name, update_or_init_data["data"])
    else:
        yield from (
            (key, val) for key, val in update_or_init_data.items() if isinstance(val, dict)
        )
