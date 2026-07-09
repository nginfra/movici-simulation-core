from __future__ import annotations

import typing as t

import numpy as np

from . import types
from .arrays import TrackedCSRArray
from .attribute_spec import AttributeSpec
from .data_type import DataType
from .utils import configure_global_plugins


class AttributeSchema(types.Extensible):
    def __init__(self, attributes: t.Optional[t.Iterable[AttributeSpec]] = None):
        self.attributes: t.Dict[str, AttributeSpec] = {}
        attributes = attributes or ()
        for attr in attributes:
            self.add_attribute(attr)

    def __getitem__(self, item):
        return self.attributes[item]

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    @t.overload
    def get_spec(
        self,
        name: str,
        default_data_type: t.Union[DataType, t.Callable[[], DataType]],
        cache=False,
    ) -> AttributeSpec: ...

    @t.overload
    def get_spec(
        self,
        name: str,
        default_data_type: t.Union[DataType, t.Callable[[], DataType], None] = None,
        cache=False,
    ) -> AttributeSpec | None: ...

    def get_spec(
        self,
        name: str,
        default_data_type: t.Union[DataType, t.Callable[[], DataType], None] = None,
        cache=False,
    ):
        if not isinstance(name, str):
            raise TypeError("name must be a single string")
        if spec := self.get(name):
            return spec
        if default_data_type is None:
            return None

        data_type = default_data_type() if callable(default_data_type) else default_data_type
        spec = AttributeSpec(name=name, data_type=data_type)
        if cache:
            self.add_attribute(spec)
        return spec

    def add_attributes(self, attributes: t.Iterable[AttributeSpec]):
        for attr in attributes:
            self.add_attribute(attr)

    def add_attribute(self, attr: AttributeSpec):
        if current := self.get(attr.name):
            if current.data_type != attr.data_type:
                raise TypeError(
                    f"Duplicate registration of attribute '{attr.name}':\n"
                    f"Data type {attr.data_type} is incompatible with "
                    f"data type {current.data_type}"
                )
            if attr.enum_name and (current.enum_name != attr.enum_name):
                raise TypeError(
                    f"Duplicate registration of attribute '{attr.name}':\n"
                    f"Enum name {attr.enum_name} does not match with "
                    f"enum name {current.enum_name}"
                )
        self.attributes[attr.name] = attr

    def __len__(self):
        return len(self.attributes)

    def __bool__(self):
        # always return True, even when len() == 0
        return True

    def __iter__(self):
        return iter(self.attributes.values())

    def use(self, plugin):
        plugin.install(self)

    def register_attributes(self, attributes: t.Iterable[AttributeSpec]):
        self.add_attributes(attributes)

    def register_model_type(self, identifier: str, model_type: t.Type[types.Model]):
        self.add_attributes(model_type.get_schema_attributes())

    def add_from_namespace(self, ns):
        try:
            self.add_attributes(
                attr for attr in vars(ns).values() if isinstance(attr, AttributeSpec)
            )

        except TypeError as e:
            raise TypeError("Could not read from namespace") from e


def get_global_schema():
    schema = AttributeSchema()
    configure_global_plugins(schema, ignore_missing_imports=False)
    return schema


def attribute_plugin_from_dict(d: dict):
    class AttributePlugin(types.Plugin):
        @classmethod
        def install(cls, obj: types.Extensible):
            obj.register_attributes(attributes_from_dict(d))

    return AttributePlugin


def attributes_from_dict(d: dict):
    return filter(lambda i: isinstance(i, AttributeSpec), d.values())


ALL_ROWPTR_KEYS = {"row_ptr", "ind_ptr", "indptr", "rowptr"}
DEFAULT_ROWPTR_KEY = "indptr"


def has_rowptr_key(d: dict):
    return bool(d.keys() & ALL_ROWPTR_KEYS)


def get_rowptr(d: dict):
    try:
        return d[next(iter(d.keys() & ALL_ROWPTR_KEYS))]
    except StopIteration:
        return None


def infer_data_type_from_array(attr_data: t.Union[dict, np.ndarray, TrackedCSRArray]) -> DataType:
    """given array data, either as an np.ndarray, TrackedCSRArray or a "data"/"row_ptr" dictionary
    infer the `DataType` of that array data
    """
    # "i" is missing the dictionary below. We need to treat "i" differently because both int and
    # bool are of type "i": int is "<i4" and bool is "|i1". `get_pytype` below handles that
    # distinction
    pytypes = {"f": float, "U": str, "b": bool}

    def get_pytype(dtype: np.dtype):
        if pytype := pytypes.get(dtype.kind):
            return pytype
        if "i1" in dtype.str:
            return bool
        return int

    if isinstance(attr_data, dict):
        data = attr_data["data"]
        is_csr = has_rowptr_key(attr_data)
    elif isinstance(attr_data, TrackedCSRArray):
        data = attr_data
        is_csr = True
    else:
        data = attr_data
        is_csr = False
    return DataType(
        get_pytype(data.dtype),
        data.shape[1:],
        is_csr,
    )


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
