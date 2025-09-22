"""Dynamic attribute loader from JSON configuration."""

import json
from pathlib import Path
from typing import Dict, Any, List

from movici_simulation_core import AttributeSpec, DataType


def load_attributes(json_path: Path = None) -> List[AttributeSpec]:
    """
    Load attributes from JSON file and create AttributeSpec objects.

    Args:
        json_path: Path to attributes.json. Defaults to BASE_DIR/attributes.json

    Returns:
        List of AttributeSpec objects ready for register_attributes()
    """
    if json_path is None:
        # Default to attributes.json in project base directory
        json_path = Path(__file__).parent.parent.parent / "attributes.json"

    if not json_path.exists():
        raise FileNotFoundError(f"Attributes file not found: {json_path}")

    with open(json_path, "r") as f:
        attr_config = json.load(f)

    attributes = []

    for attr_name, config in attr_config.items():
        attributes.append(create_attribute_spec(attr_name, config))

    return attributes


def create_attribute_spec(name: str, config: Dict[str, Any]) -> AttributeSpec:
    """
    Create an AttributeSpec from configuration.

    Args:
        name: Attribute name
        config: Attribute configuration

    Returns:
        AttributeSpec object
    """
    data_type_str = config.get("data_type", "float")
    csr = config.get("csr", False)
    unit_shape = tuple(config.get("shape", []))

    # Map string types to Python types
    type_map = {
        "float": float,
        "int": int,
        "str": str,
        "bool": bool,
        "object": object,
    }

    py_type = type_map.get(data_type_str, float)

    # Create DataType
    data_type = DataType(py_type=py_type, unit_shape=unit_shape, csr=csr)

    return AttributeSpec(name=name, data_type=data_type)