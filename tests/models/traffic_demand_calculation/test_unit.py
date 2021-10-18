import logging

import numpy as np
import pytest

from movici_simulation_core.core.schema import DataType, PropertySpec
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.property import INIT
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.traffic_demand_calculation.local_effect_calculators import (
    TransportPathingValueSum,
)
from movici_simulation_core.utils.settings import Settings


@pytest.fixture
def get_transport_value_sum_calculator(
    road_network_name, road_network_for_traffic, global_schema
) -> TransportPathingValueSum:
    calc = TransportPathingValueSum()
    state = TrackedState(logging.getLogger("some_name"))
    elasticity = 2
    prop_spec = PropertySpec(
        component="traffic_properties", name="average_time", data_type=DataType(float, (), False)
    )
    prop = state.register_property(
        road_network_name, "road_segment_entities", prop_spec, flags=INIT
    )
    data_format = EntityInitDataFormat(global_schema)
    calc.setup(
        state,
        prop,
        road_network_name,
        "road_segment_entities",
        "line",
        elasticity,
        Settings(),
    )

    upd = {road_network_name: data_format.load_json(road_network_for_traffic)["data"]}
    state.receive_update(upd)

    return calc


def test_transport_pathing(get_transport_value_sum_calculator):
    calc = get_transport_value_sum_calculator
    closest_indices = np.array([2, 2, 0])
    calc.initialize(closest_indices)

    base_path_travel_costs = np.array([[0, 0, 2], [0, 0, 2], [1, 1, 0]])

    calc._property[:] = 2
    updated = calc.update_graph()
    assert not updated
    assert np.array_equal(calc._old_summed_values, base_path_travel_costs * 2)

    calc._property[:] = 3
    updated = calc.update_graph()
    assert updated
    new, old = calc.get_new_and_old_summed_value_along_paths()
    assert np.array_equal(old, base_path_travel_costs * 2)
    assert np.array_equal(new, base_path_travel_costs * 3)
    assert np.array_equal(calc._old_summed_values, base_path_travel_costs * 3)
