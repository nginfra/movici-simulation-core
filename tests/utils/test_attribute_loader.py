"""Tests for the attribute_loader utility."""

import json
from pathlib import Path

import pytest

from movici_simulation_core import AttributeSpec
from movici_simulation_core.utils.attribute_loader import create_attribute_spec, load_attributes


class TestCreateAttributeSpec:
    """Tests for create_attribute_spec function."""

    @pytest.mark.parametrize(
        "data_type_str,expected_py_type",
        [
            ("float", float),
            ("double", float),
            ("int", int),
            ("str", str),
            ("string", str),
            ("bool", bool),
            ("boolean", bool),
        ],
    )
    def test_create_simple_attribute(self, data_type_str, expected_py_type):
        """Test creating a simple attribute with different data types."""
        config = {"data_type": data_type_str}
        spec = create_attribute_spec("test_attr", config)

        assert isinstance(spec, AttributeSpec)
        assert spec.name == "test_attr"
        assert spec.data_type.py_type is expected_py_type
        assert spec.data_type.unit_shape == ()
        assert spec.data_type.csr is False

    def test_create_attribute_with_default_type(self):
        """Test creating attribute with no data_type specified (defaults to float)."""
        config = {}
        spec = create_attribute_spec("default_attr", config)

        assert spec.name == "default_attr"
        assert spec.data_type.py_type is float

    def test_create_attribute_with_invalid_type(self):
        """Test creating attribute with invalid type falls back to float."""
        config = {"data_type": "invalid_type"}

        with pytest.raises(ValueError, match="Invalid data type: invalid_type"):
            create_attribute_spec("attr", config)

    @pytest.mark.parametrize(
        "shape,expected_tuple",
        [
            ([2], (2,)),
            ([3, 3], (3, 3)),
            ([2, 4], (2, 4)),
            ([], ()),
        ],
    )
    def test_create_attribute_with_shape(self, shape, expected_tuple):
        """Test creating attribute with various unit shapes."""
        config = {"data_type": "float", "shape": shape}
        spec = create_attribute_spec("shaped_attr", config)

        assert spec.data_type.unit_shape == expected_tuple

    def test_create_csr_attribute(self):
        """Test creating attribute with CSR format."""
        config = {"data_type": "int", "csr": True}
        spec = create_attribute_spec("csr_attr", config)

        assert spec.data_type.csr is True

    def test_create_attribute_with_all_options(self):
        """Test creating attribute with all configuration options."""
        config = {"data_type": "float", "shape": [2, 2], "csr": True}
        spec = create_attribute_spec("full_attr", config)

        assert spec.name == "full_attr"
        assert spec.data_type.py_type is float
        assert spec.data_type.unit_shape == (2, 2)
        assert spec.data_type.csr is True

    def test_create_attribute_without_enum_name(self):
        """Test that omitting enum_name results in None."""
        config = {"data_type": "int"}
        spec = create_attribute_spec("status", config)

        assert spec.enum_name is None

    def test_create_attribute_with_enum_name(self):
        """Test that providing enum_name sets it on the AttributeSpec."""
        config = {"data_type": "int", "enum_name": "StatusType"}
        spec = create_attribute_spec("status", config)

        assert spec.enum_name == "StatusType"


class TestLoadAttributes:
    """Tests for load_attributes function."""

    @pytest.fixture(params=[list, dict])
    def sample_attributes_json(self, request, tmp_path):
        """Create a temporary JSON file with sample attributes."""
        data = {
            "velocity": {"data_type": "float", "shape": [2], "csr": False},
            "node_id": {"data_type": "int"},
            "name": {"data_type": "str"},
            "is_active": {"data_type": "bool"},
        }
        if request.param is list:
            data = [{**v, "name": k} for k, v in data.items()]
        json_path = tmp_path / "attributes.json"
        json_path.write_text(json.dumps(data))
        return json_path

    @pytest.fixture
    def empty_attributes_json(self, tmp_path):
        """Create an empty attributes JSON file."""
        json_path = tmp_path / "empty.json"
        json_path.write_text(json.dumps({}))
        return json_path

    def test_load_attributes_from_file(self, sample_attributes_json):
        """Test loading attributes from a valid JSON file."""
        specs = load_attributes(sample_attributes_json)

        assert len(specs) == 4
        assert all(isinstance(spec, AttributeSpec) for spec in specs)

        # Check specific attributes
        velocity = next(s for s in specs if s.name == "velocity")
        assert velocity.data_type.py_type is float
        assert velocity.data_type.unit_shape == (2,)
        assert velocity.data_type.csr is False
        assert velocity.name == "velocity"

        node_id = next(s for s in specs if s.name == "node_id")
        assert node_id.data_type.py_type is int

        name = next(s for s in specs if s.name == "name")
        assert name.data_type.py_type is str

        is_active = next(s for s in specs if s.name == "is_active")
        assert is_active.data_type.py_type is bool

    def test_load_attributes_from_empty_file(self, empty_attributes_json):
        """Test loading from an empty JSON file returns empty list."""
        specs = load_attributes(empty_attributes_json)

        assert specs == []

    def test_load_attributes_file_not_found(self, tmp_path):
        """Test that FileNotFoundError is raised for non-existent file."""
        non_existent_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_attributes(non_existent_path)

        assert "Attributes file not found" in str(exc_info.value)
        assert str(non_existent_path) in str(exc_info.value)

    def test_load_attributes_with_complex_config(self, tmp_path):
        """Test loading attributes with complex configurations."""
        data = {
            "matrix_attr": {"data_type": "float", "shape": [3, 3], "csr": True},
            "vector_attr": {"data_type": "int", "shape": [4]},
            "simple_attr": {},  # Should default to float
        }
        json_path = tmp_path / "complex.json"
        json_path.write_text(json.dumps(data))

        specs = load_attributes(json_path)

        assert len(specs) == 3

        matrix_attr = next(s for s in specs if s.name == "matrix_attr")
        assert matrix_attr.data_type.py_type is float
        assert matrix_attr.data_type.unit_shape == (3, 3)
        assert matrix_attr.data_type.csr is True

        vector_attr = next(s for s in specs if s.name == "vector_attr")
        assert vector_attr.data_type.py_type is int
        assert vector_attr.data_type.unit_shape == (4,)

        simple_attr = next(s for s in specs if s.name == "simple_attr")
        assert simple_attr.data_type.py_type is float
        assert simple_attr.data_type.unit_shape == ()

    def test_load_attributes_handles_pathlib_path(self, tmp_path):
        """Test that both Path and string paths work."""
        data = {"test": {"data_type": "float"}}
        json_path = tmp_path / "test.json"
        json_path.write_text(json.dumps(data))

        # Test with Path object
        specs_from_path = load_attributes(json_path)
        assert len(specs_from_path) == 1

        # Test with string path
        specs_from_str = load_attributes(Path(str(json_path)))
        assert len(specs_from_str) == 1

        assert specs_from_path[0].name == specs_from_str[0].name
