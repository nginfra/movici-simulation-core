import typing as t
import warnings

import msgpack
import numpy as np
import ujson as json

from movici_simulation_core.core.schema import (
    DataType,
    DEFAULT_ROWPTR_KEY,
    has_rowptr_key,
    infer_data_type_from_array,
    AttributeSchema,
    get_rowptr,
)
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.unicode_helpers import get_unicode_dtype
from movici_simulation_core.types import NumpyPropertyData


class EntityInitDataFormat:
    schema: AttributeSchema

    def __init__(
        self,
        schema: t.Optional[AttributeSchema] = None,
        non_data_dict_keys=("general",),
        cache_inferred_attributes=False,
    ):
        self.schema = schema or AttributeSchema()
        self.non_data_dict_keys = set(non_data_dict_keys)
        self.cache_inferred_attributes = cache_inferred_attributes

    def load_bytes(self, raw: t.Union[str, bytes], **kwargs):
        list_data = json.loads(raw, **kwargs)
        return self.load_json(list_data)

    def load_json(self, obj: dict):
        if not isinstance(obj, dict):
            raise TypeError("Dataset must be dictionary")
        return {
            key: (
                self.load_data_section(val)
                if isinstance(val, dict) and key not in self.non_data_dict_keys
                else val
            )
            for key, val in obj.items()
        }

    def dump_dict(self, dataset: dict):
        return {
            key: (
                dump_dataset_data(val)
                if isinstance(val, dict) and key not in self.non_data_dict_keys
                else val
            )
            for key, val in dataset.items()
        }

    def dumps(self, dataset: dict, **kwargs) -> str:
        return json.dumps(
            self.dump_dict(dataset),
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

            def infer_datatype():
                warnings.warn(
                    f"Inferring datatype of attribute"
                    f" '{component + '/' + name if component else name}'"
                )
                try:
                    return infer_data_type_from_list(attr_data)
                except TypeError as e:
                    raise TypeError(f"Error when parsing data for {component}/{name}") from e

            data_type = self.schema.get_spec(
                (component, name), infer_datatype, cache=True
            ).data_type

            return parse_list(attr_data, data_type)

        else:
            raise TypeError("attribute data must be dict (component) or list (attribute)")


def load_from_json(
    data,
    schema: t.Optional[AttributeSchema] = None,
    non_data_dict_keys=("general",),
    cache_inferred_attributes=False,
):
    reader = EntityInitDataFormat(schema, non_data_dict_keys, cache_inferred_attributes)
    return reader.load_json(data)


def parse_list(data: list, data_type: DataType) -> NumpyPropertyData:
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
        if item is None:
            item = [None]
        flattened.extend(item)
        row_ptr.append(len(flattened))
    return {
        "data": create_array(flattened, data_type),
        DEFAULT_ROWPTR_KEY: np.array(row_ptr, dtype=np.uint32),
    }


def create_array(uniform_data: list, data_type: DataType):
    if data_type.unit_shape == ():
        undefined = data_type.undefined
    else:
        undefined = np.full(data_type.unit_shape, data_type.undefined)

    for idx, val in enumerate(uniform_data):
        if attribute_is_undefined(val):
            uniform_data[idx] = undefined
    dtype = data_type.np_type
    if np.issubdtype(dtype, str):
        dtype = get_unicode_dtype(_max_str_length(uniform_data))
    return np.array(uniform_data, dtype=dtype)


def _max_str_length(uniform_data: list) -> int:
    max_len = 0
    for item in uniform_data:
        if isinstance(item, list):
            max_len = max(max_len, _max_str_length(item))
        else:
            max_len = max(max_len, len(item))
    return max_len


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
    data, row_ptr = attribute_dict["data"], get_rowptr(attribute_dict)
    csr = TrackedCSRArray(data, row_ptr, equal_nan=True)
    return dump_tracked_csr_array(csr, data_type)


def dump_tracked_csr_array(csr: TrackedCSRArray, data_type=None):
    if data_type is not None:
        undefined_indices = set(np.flatnonzero(is_undefined_csr(csr, data_type)))
    else:
        undefined_indices = set()
    return [
        (None if row_idx in undefined_indices else csr.get_row(row_idx).tolist())
        for row_idx in range(csr.size)
    ]


def dump_uniform_attribute(attribute_dict, data_type):
    array = attribute_dict["data"]
    rv = array.tolist()
    for idx in np.flatnonzero(is_undefined_uniform(array, data_type)):
        rv[idx] = None
    return rv


def is_undefined_uniform(data, data_type):
    undefs = data_type.is_undefined(data)

    # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be
    # reduced to a result array of shape (10,) by reducing over axes (1,2). An single
    # entity's property is considered undefined if the item is undefined in all its dimensions
    reduction_axes = tuple(range(1, len(undefs.shape)))
    return np.minimum.reduce(undefs, axis=reduction_axes)


def is_undefined_csr(csr_array, data_type):
    return csr_array.rows_contain(np.array([data_type.undefined]))


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
