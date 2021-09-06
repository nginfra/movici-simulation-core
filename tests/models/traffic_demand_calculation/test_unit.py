import numpy as np
import pytest
import logging
from model_engine.dataset_manager.dataset_handler import _convert_dataset_to_numpy_format
from model_engine.utils.config import current_config
from movici_simulation_core.base_models.config_helpers import property_mapping
from movici_simulation_core.data_tracker.property import INIT
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.traffic_demand_calculation.local_effect_calculators import (
    TransportPathingValueSum,
)


@pytest.fixture
def get_transport_value_sum_calculator(
    road_network_name, road_network_for_traffic
) -> TransportPathingValueSum:
    calc = TransportPathingValueSum()
    state = TrackedState(logging.getLogger("some_name"))
    elasticity = 2
    prop_spec = property_mapping[("traffic_properties", "average_time")]
    prop = state.register_property(
        road_network_name, "road_segment_entities", prop_spec, flags=INIT
    )

    calc.setup(
        state,
        prop,
        road_network_name,
        "road_segment_entities",
        "line",
        elasticity,
        current_config(),
    )

    upd = {road_network_name: _convert_dataset_to_numpy_format(road_network_for_traffic)["data"]}
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
