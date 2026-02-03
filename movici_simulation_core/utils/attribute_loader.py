"""Dynamic attribute loader from JSON configuration.

This module provides utilities to dynamically load attribute specifications
from JSON configuration files and create AttributeSpec objects for use with
the Movici simulation core attribute system.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from movici_simulation_core import AttributeSpec, DataType


def load_attributes(json_path: Path) -> List[AttributeSpec]:
    """Load attributes from JSON file and create AttributeSpec objects.

    :param json_path: Path to attributes.json. Defaults to BASE_DIR/attributes.json
    :type json_path: Path
    :returns: List of AttributeSpec objects ready for register_attributes()
    :rtype: List[AttributeSpec]
    :raises FileNotFoundError: If the attributes file does not exist
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Attributes file not found: {json_path}")

    attr_config = json.loads(json_path.read_text())

    if isinstance(attr_config, dict):
        return [
            create_attribute_spec(attr_name, config) for attr_name, config in attr_config.items()
        ]

    elif isinstance(attr_config, list):
        return [create_attribute_spec(attr_info["name"], attr_info) for attr_info in attr_config]

    else:
        raise TypeError("attributes file content must be a list or dict")


def create_attribute_spec(name: str, config: Dict[str, Any]) -> AttributeSpec:
    """Create an AttributeSpec from configuration.

    :param name: Attribute name
    :type name: str
    :param config: Attribute configuration dictionary. Supported keys:
                   - data_type: Type of the attribute (float, int, str, bool, object)
                   - csr: Whether the attribute uses CSR (Compressed Sparse Row) format
                   - shape: Unit shape of the attribute
                   - enum_name: Name of the enumeration for (certain) integer attributes
    :type config: Dict[str, Any]
    :returns: AttributeSpec object
    :rtype: AttributeSpec
    """
    data_type_str = config.get("data_type", "float").lower()
    csr = config.get("csr", False)
    unit_shape = tuple(config.get("shape", []))
    enum_name = config.get("enum_name")

    # Map string types to Python types
    type_map = {
        "float": float,
        "double": float,
        "int": int,
        "bool": bool,
        "boolean": bool,
        "str": str,
        "string": str,
    }

    if data_type_str not in type_map:
        raise ValueError(f"Invalid data type: {data_type_str}")

    py_type = type_map[data_type_str]

    # Create DataType
    data_type = DataType(py_type=py_type, unit_shape=unit_shape, csr=csr)

    return AttributeSpec(name=name, data_type=data_type, enum_name=enum_name)
