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

    def get_spec(
        self,
        name: t.Union[str, t.Tuple[t.Optional[str], str]],
        default_data_type: t.Union[DataType, t.Callable[[], DataType], None] = None,
        cache=False,
    ):
        if not isinstance(name, str):
            name = self._extract_name(name)

        if spec := self.get(name):
            return spec
        if default_data_type is None:
            return None

        data_type = default_data_type() if callable(default_data_type) else default_data_type
        spec = AttributeSpec(name=name, data_type=data_type)
        if cache:
            self.add_attribute(spec)
        return spec

    # TODO: Remove _extract_name once all legacy test cases are updated and no user configs use old (None, "attr") format
    @staticmethod
    def _extract_name(identifier):
        # fallback behaviour for dealing with (component, attribute) style attribute identifier
        if not isinstance(identifier, t.Sequence) or len(identifier) != 2:
            raise TypeError(f"name must be a string, not {type(identifier)}")
        component, name = identifier
        if component is not None:
            raise ValueError(
                f"Components are no longer supported, received attribute identifier {identifier}"
            )
        return name

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


ALL_ROWPTR_KEYS = {"row_ptr", "ind_ptr", "indptr"}
DEFAULT_ROWPTR_KEY = "indptr"


def has_rowptr_key(d: dict):
    return bool(d.keys() & ALL_ROWPTR_KEYS)


def get_rowptr(d: dict):
    try:
        return d[next(iter(d.keys() & ALL_ROWPTR_KEYS))]
    except StopIteration:
        return None


def infer_data_type_from_array(attr_data: t.Union[dict, np.ndarray, TrackedCSRArray]):
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
    """Infer data type from a list with comprehensive validation.
    
    Args:
        data: List of values or list of lists (for CSR data)
        
    Returns:
        DataType: Inferred data type with unit shape and CSR flag
        
    Raises:
        TypeError: If data types are inconsistent or unsupported
        ValueError: If data structure is invalid
    """
    
    def infer_pytype(d: list):
        """Infer Python type from a list with validation."""
        if not len(d):
            return float
            
        # Check for None values and get first non-None item
        first_non_none = None
        for item in d:
            if item is not None:
                first_non_none = item
                break
                
        if first_non_none is None:
            return float  # All None values, default to float
            
        inferred_type = type(first_non_none)
        if inferred_type not in (int, float, bool, str):
            raise TypeError(f"Unsupported data type: {inferred_type}")
            
        # Check for int/float consistency - promote int to float if mixed
        if inferred_type == int:
            for item in d:
                if item is not None and isinstance(item, float):
                    inferred_type = float
                    break
                elif item is not None and not isinstance(item, (int, float)):
                    raise TypeError(f"Inconsistent types: expected numeric, got {type(item)}")
                    
        # Validate type consistency for all items
        for item in d:
            if item is not None:
                if inferred_type == float and not isinstance(item, (int, float)):
                    raise TypeError(f"Inconsistent types: expected numeric, got {type(item)}")
                elif inferred_type not in (int, float) and not isinstance(item, inferred_type):
                    raise TypeError(f"Inconsistent types: expected {inferred_type}, got {type(item)}")
                    
        return inferred_type

    # Check for empty list
    if not len(data):
        pytype, csr = float, False
    elif isinstance(data[0], list):
        # CSR case - list of lists
        csr = True
        
        # Validate that all items are lists
        for i, item in enumerate(data):
            if not isinstance(item, list):
                raise ValueError(f"Inconsistent structure: item {i} is not a list in CSR data")
                
        # Check for unit shape consistency across all sublists
        if data:
            first_sublist = data[0]
            if first_sublist:  # Only check if first sublist is not empty
                unit_shape = None
                for sublist in data:
                    if sublist:  # Skip empty sublists for shape inference
                        if isinstance(sublist[0], (list, tuple)):
                            # Multi-dimensional case
                            current_shape = (len(sublist[0]),) if sublist[0] else ()
                        else:
                            # 1D case
                            current_shape = ()
                            
                        if unit_shape is None:
                            unit_shape = current_shape
                        elif unit_shape != current_shape:
                            raise ValueError(f"Inconsistent unit shapes in CSR data: {unit_shape} vs {current_shape}")
                            
        # Infer type from first non-empty sublist
        pytype = float  # default
        for sublist in data:
            if sublist:
                pytype = infer_pytype(sublist)
                break
    else:
        # Regular list case
        csr = False
        pytype = infer_pytype(data)

    return DataType(pytype, unit_shape=(), csr=csr)
