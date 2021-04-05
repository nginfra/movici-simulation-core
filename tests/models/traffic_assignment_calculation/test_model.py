import pytest

from model_engine import testing
from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.models.traffic_assignment_calculation.model import Model


@pytest.fixture
def time_scale():
    return 1


@pytest.fixture
def model_name():
    return "test_traffic_assignment_calculation"


@pytest.fixture
def config(
    time_scale,
    model_config,
    init_data,
):

    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 30,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture(params=["road_network", "road_network_with_line3d"])
def init_data(
    request,
    road_network_name,
    virtual_nodes_name,
    virtual_nodes_dataset,
):
    road_network = request.getfixturevalue(request.param)

    return [
        {"name": road_network_name, "data": road_network},
        {"name": virtual_nodes_name, "data": virtual_nodes_dataset},
    ]


@pytest.fixture
def model_config(model_name, road_network_name, virtual_nodes_name):
    return {
        "name": model_name,
        "type": "traffic_assignment_calculation",
        "transport_network_segments": [(road_network_name, "road_segment_entities")],
        "transport_network_vertices": [(road_network_name, "road_vertex_entities")],
        "demand_nodes": [(virtual_nodes_name, "virtual_node_entities")],
    }


class TestTrafficAssignmentCalculation:
    def test_traffic_assignment_calculation(
        self,
        get_entity_update,
        config,
        model_name,
        road_network_name,
        virtual_nodes_name,
        time_scale,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        virtual_nodes_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[0, 20, 0], [5, 0, 0], [0, 100, 0]],
                                "transport.cargo_demand": [
                                    [0, 10, 10],
                                    [10, 0, 10],
                                    [10, 10, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 1, "data": {}},
                {
                    "time": 2,
                    "data": {
                        virtual_nodes_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [
                                    [0, 10, 0],
                                    [2.5, 0, 0],
                                    [0, 50, 0],
                                ],
                                "transport.cargo_demand": [
                                    [0, 5, 5],
                                    [5, 0, 5],
                                    [5, 5, 0],
                                ],
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_flow": [4.1667, 20, 120, 0.8333],
                                "transport.cargo_flow": [25, 30, 30, 5],
                                "transport.delay_factor": [1.171, 1.0527, 24.5561, 1.171],
                                "transport.volume_to_capacity_ratio": [
                                    1.03333,
                                    0.77,
                                    3.54,
                                    1.03333,
                                ],
                                "transport.passenger_car_unit": [51.6667, 77, 177, 10.3333],
                                "traffic_properties": {
                                    "average_time": [
                                        0.4216,
                                        0.3032,
                                        0.884,
                                        0.4216,
                                    ],  # todo rename to transport.travel_time
                                },
                            },
                        },
                    },
                },
                {"time": 1, "data": {}},
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_flow": [2.0834, 10, 60, 0.4167],
                                "transport.cargo_flow": [12.5, 15, 15, 2.5],
                                "transport.delay_factor": [1.011, 1.003, 2.472, 1.011],
                                "transport.volume_to_capacity_ratio": [
                                    0.5167,
                                    0.385,
                                    1.77,
                                    0.5167,
                                ],
                                "transport.passenger_car_unit": [25.8334, 38.5, 88.5, 5.1667],
                                "traffic_properties": {
                                    "average_time": [0.3639, 0.289, 0.089, 0.3639],
                                },
                            },
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=model_factory(Model),
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )
