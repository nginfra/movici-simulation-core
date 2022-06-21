import typing as t
import warnings

import msgpack
import numpy as np
import orjson as json

from movici_simulation_core.types import (
    ExternalSerializationStrategy,
    FileType,
    NumpyAttributeData,
)
from movici_simulation_core.utils import lifecycle
from movici_simulation_core.utils.unicode import get_unicode_dtype

from .arrays import TrackedCSRArray
from .data_type import DataType
from .schema import (
    DEFAULT_ROWPTR_KEY,
    AttributeSchema,
    get_rowptr,
    has_rowptr_key,
    infer_data_type_from_array,
    infer_data_type_from_list,
)


@lifecycle.has_deprecations
class EntityInitDataFormat(ExternalSerializationStrategy):
    schema: AttributeSchema

    def __init__(
        self,
        schema: t.Optional[AttributeSchema] = None,
        non_data_dict_keys: t.Container[str] = ("general",),
        cache_inferred_attributes: bool = False,
    ) -> None:
        if schema is None:
            schema = AttributeSchema()
        super().__init__(schema, non_data_dict_keys, cache_inferred_attributes)

    def supported_file_types(self) -> t.Sequence[FileType]:
        return (FileType.JSON, FileType.MSGPACK)

    @lifecycle.deprecated(alternative="EntityInitDataFormat.loads")
    def load_bytes(self, raw: t.Union[str, bytes], **kwargs):
        return self.loads(raw, FileType.JSON)

    def loads(self, raw_data, type: FileType):
        self.supported_file_type_or_raise(type)
        if type is FileType.JSON:
            list_data = json.loads(raw_data)
        elif type is FileType.MSGPACK:
            list_data = msgpack.unpackb(raw_data)

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

    def load_attribute(self, attr_data: list, name: str) -> dict:
        if isinstance(attr_data, list):

            def infer_datatype():
                warnings.warn(f"Inferring datatype of attribute '{name}'")
                try:
                    return infer_data_type_from_list(attr_data)
                except TypeError as e:
                    raise TypeError(f"Error when parsing data for '{name}'") from e

            data_type = self.schema.get_spec(name, infer_datatype, cache=True).data_type

            return parse_list(attr_data, data_type)

        else:
            raise TypeError("attribute data must be list")

    def dumps(
        self, dataset: dict, filetype: t.Optional[FileType] = FileType.JSON, **kwargs
    ) -> str:
        self.supported_file_type_or_raise(filetype)
        list_data = self.dump_dict(dataset)
        if filetype is FileType.JSON:
            return json.dumps(self.dump_dict(dataset), **kwargs)
        if filetype is FileType.MSGPACK:
            return msgpack.packb(list_data, **kwargs)

    def dump_dict(self, dataset: dict):
        return {
            key: (
                dump_dataset_data(val)
                if isinstance(val, dict) and key not in self.non_data_dict_keys
                else val
            )
            for key, val in dataset.items()
        }


def load_from_json(
    data,
    schema: t.Optional[AttributeSchema] = None,
    non_data_dict_keys=("general",),
    cache_inferred_attributes=False,
):
    reader = EntityInitDataFormat(schema, non_data_dict_keys, cache_inferred_attributes)
    return reader.load_json(data)


def parse_list(data: list, data_type: DataType) -> NumpyAttributeData:
    if data_type.csr:
        return parse_csr_list(data, data_type)
    return parse_uniform_list(data, data_type)


def parse_uniform_list(data: list, data_type: DataType) -> NumpyAttributeData:
    return {"data": create_array(data, data_type)}


def parse_csr_list(data: t.List[list], data_type: DataType) -> NumpyAttributeData:
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


def dump_uniform_attribute(attribute_dict, data_type: DataType):
    array = attribute_dict["data"]
    rv = array.astype(data_type.py_type).tolist()
    for idx in np.flatnonzero(is_undefined_uniform(array, data_type)):
        rv[idx] = None
    return rv


def is_undefined_uniform(data, data_type):
    undefs = data_type.is_undefined(data)

    # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be
    # reduced to a result array of shape (10,) by reducing over axes (1,2). An single
    # entity's attribute is considered undefined if the item is undefined in all its dimensions
    reduction_axes = tuple(range(1, len(undefs.shape)))
    return np.minimum.reduce(undefs, axis=reduction_axes)


def is_undefined_csr(csr_array, data_type):
    return csr_array.rows_contain(np.array([data_type.undefined]))


def data_keys(update_or_init_data, ignore_keys=("general",)):
    return {
        key
        for key in data_key_candidates(update_or_init_data, ignore_keys)
        if all(isinstance(update_or_init_data[key][k], dict) for k in update_or_init_data[key])
    }


def data_key_candidates(update_or_init_data, ignore_keys=("general",)):
    if "data" in update_or_init_data:
        return {"data"}
    else:
        return {key for key, val in update_or_init_data.items() if isinstance(val, dict)} - set(
            ignore_keys
        )


def extract_dataset_data(update_or_init_data, ignore_keys=("general",)):
    keys = data_keys(update_or_init_data, ignore_keys)

    if "data" in keys and isinstance(name := update_or_init_data.get("name"), str):
        yield (name, update_or_init_data["data"])
    else:
        yield from ((key, update_or_init_data[key]) for key in keys)
