import pytest
from movici_simulation_core.base_model.config_helpers import property_mapping


@pytest.mark.parametrize(
    ["prop", "component", "data_type", "unit_shape", "has_indptr"],
    [("from_node_connected", "line_properties", bool, (), False), ("labels", None, int, (), True)],
)
def test_config_helpers_supplies_property_mapping(
    prop, component, data_type, unit_shape, has_indptr
):
    spec = property_mapping[(component, prop)]
    assert spec.name == prop
    assert spec.component == component
    assert spec.data_type.py_type == data_type
    assert spec.data_type.unit_shape == unit_shape
    assert spec.data_type.csr == has_indptr
