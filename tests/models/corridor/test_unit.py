import numpy as np
import pytest

from movici_simulation_core.data_tracker.arrays import TrackedArray, TrackedCSRArray
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.entities import PointEntity, LinkEntity
from movici_simulation_core.models.corridor.entities import (
    CorridorEntity,
    CorridorTransportSegmentEntity,
    DemandNodeEntity,
)
from movici_simulation_core.models.corridor.model import Model


def initialize_corridor(corridor_entity, entity_count):
    corridor_entity.passenger_flow.initialize(entity_count)
    corridor_entity.cargo_flow.initialize(entity_count)
    corridor_entity.passenger_car_unit.initialize(entity_count)
    corridor_entity.travel_time.initialize(entity_count)
    corridor_entity.co2_emission.initialize(entity_count)
    corridor_entity.nox_emission.initialize(entity_count)
    corridor_entity.energy_consumption.initialize(entity_count)
    corridor_entity.max_volume_to_capacity.initialize(entity_count)
    corridor_entity.delay_factor.initialize(entity_count)
    corridor_entity.line2d.initialize(entity_count)


def initialize_transport_segments(transport_segments, entity_count):
    transport_segments.passenger_car_unit.initialize(entity_count)
    transport_segments.travel_time.initialize(entity_count)
    transport_segments.co2_emission.initialize(entity_count)
    transport_segments.nox_emission.initialize(entity_count)
    transport_segments.energy_consumption.initialize(entity_count)
    transport_segments._linestring2d.initialize(entity_count)


@pytest.fixture
def model() -> Model:
    state = TrackedState()

    corridor_model = Model()
    corridor_model._corridor_entity = state.register_entity_group("ds", CorridorEntity(name="a"))
    corridor_model._transport_segments = state.register_entity_group(
        "ds", CorridorTransportSegmentEntity(name="b")
    )
    corridor_model._transport_nodes = state.register_entity_group("ds", PointEntity(name="c"))
    corridor_model._demand_nodes = state.register_entity_group("ds", DemandNodeEntity(name="d"))
    corridor_model._demand_links = state.register_entity_group("ds", LinkEntity(name="e"))

    initialize_corridor(corridor_model._corridor_entity, 5)
    initialize_transport_segments(corridor_model._transport_segments, 4)

    corridor_model._reset_values()

    return corridor_model


def test_node_properties(model: Model):

    model._add_node_properties(
        corridor_index=2, passenger_demand=10, cargo_demand=20, pcu_demand=30
    )

    assert model._corridor_entity.passenger_flow[2] == 10
    assert model._corridor_entity.cargo_flow[2] == 20
    assert model._corridor_entity.passenger_car_unit[2] == 30

    model._add_node_properties(corridor_index=2, passenger_demand=1, cargo_demand=2, pcu_demand=3)

    assert model._corridor_entity.passenger_flow[2] == 11
    assert model._corridor_entity.cargo_flow[2] == 22
    assert model._corridor_entity.passenger_car_unit[2] == 33


def test_energy_kpis(model: Model):

    model._transport_segments.passenger_car_unit.array = TrackedArray([10, 20, 30, 40])
    model._transport_segments.co2_emission.array = TrackedArray([10, 11, 12, 13])
    model._transport_segments.nox_emission.array = TrackedArray([100, 101, 102, 103])
    model._transport_segments.energy_consumption.array = TrackedArray([1000, 1001, 1002, 1003])

    model._calculate_energy_kpis(corridor_index=2, roads_indices=np.array([0]), pcu_demand=10)

    assert model._corridor_entity.co2_emission[2] == 10
    assert model._corridor_entity.nox_emission[2] == 100
    assert model._corridor_entity.energy_consumption[2] == 1000

    model._calculate_energy_kpis(corridor_index=2, roads_indices=np.array([2, 3]), pcu_demand=10)

    assert model._corridor_entity.co2_emission[2] == 10 + 12 / 3 + 13 / 4
    assert model._corridor_entity.nox_emission[2] == 100 + 102 / 3 + 103 / 4
    assert model._corridor_entity.energy_consumption[2] == 1000 + 1002 / 3 + 1003 / 4


def test_weighted_travel_time(model: Model):
    model._transport_segments.travel_time.array = TrackedArray([10, 20, 30, 40])

    model._calculate_weighted_travel_time(
        corridor_index=2, roads_indices=np.array([0]), pcu_demand=10
    )
    assert model._corridor_entity.travel_time[2] == 100

    model._calculate_weighted_travel_time(
        corridor_index=2, roads_indices=np.array([2, 3]), pcu_demand=10
    )
    assert model._corridor_entity.travel_time[2] == 100 + 300 + 400

    model._corridor_entity.passenger_car_unit[2] = 20
    model._calculate_average_travel_time()
    assert model._corridor_entity.travel_time[2] == 40


def test_max_delay_factor(model: Model):
    model._transport_segments.travel_time.array = TrackedArray([10, 20, 30, 40])
    model._free_flow_times = np.array([2, 5, 5, 4])

    model._calculate_max_delay_factor(corridor_index=2, roads_indices=np.array([0]))
    assert model._corridor_entity.delay_factor[2] == 5

    model._calculate_max_delay_factor(corridor_index=2, roads_indices=np.array([2, 3]))
    assert model._corridor_entity.delay_factor[2] == 70 / 9


def test_max_volume_to_capacity(model: Model):
    model._transport_segments.passenger_car_unit.array = TrackedArray([10, 20, 30, 40])
    model._transport_segments.capacity.array = TrackedArray([2, 5, 5, 4])

    model._calculate_max_volume_to_capacity(corridor_index=2, roads_indices=np.array([0]))
    assert model._corridor_entity.max_volume_to_capacity[2] == 5

    model._calculate_max_volume_to_capacity(corridor_index=2, roads_indices=np.array([2, 3]))
    assert model._corridor_entity.max_volume_to_capacity[2] == 10


def test_geometry(model: Model):
    model._transport_segments._linestring2d.csr = TrackedCSRArray(
        np.array([[0, 0], [0, 1], [0, 0], [1, 0], [0, 0], [0, 1], [0, 1], [1, 0]]),
        np.array([0, 2, 4, 6, 8]),
    )
    model._transport_directions = np.array([1, 1, -1, 0])

    model._calculate_geometry(corridor_index=2, roads_indices=[0, 2, 1])
    result = model._corridor_entity.line2d.csr.get_row(2)
    assert np.array_equal(result, [[0, 0], [0, 1], [0, 0], [1, 0]])

    model._calculate_geometry(corridor_index=2, roads_indices=[2, 1])
    result = model._corridor_entity.line2d.csr.get_row(2)
    assert np.array_equal(result, [[0, 1], [0, 0], [1, 0]])

    model._calculate_geometry(corridor_index=2, roads_indices=[0, 3])
    result = model._corridor_entity.line2d.csr.get_row(2)
    assert np.array_equal(result, [[0, 0], [0, 1], [1, 0]])
