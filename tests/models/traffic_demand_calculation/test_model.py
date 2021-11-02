import os

import pytest

from movici_simulation_core.models.traffic_demand_calculation.model import TrafficDemandCalculation
from movici_simulation_core.testing.model_tester import ModelTester
from ..conftest import get_dataset


@pytest.fixture
def scenario_parameters_csv_name():
    return "scenario_parameters_csv"


@pytest.fixture
def scenario_parameters_csv_path():
    return os.path.join(os.path.dirname(__file__), "scenario_parameters.csv")


@pytest.fixture
def init_data(
    road_network_name,
    road_network_for_traffic,
    scenario_parameters_csv_name,
    scenario_parameters_csv_path,
):
    return [
        {"name": road_network_name, "data": road_network_for_traffic},
        {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
    ]


@pytest.fixture
def waterways(water_network_name):
    return get_dataset(
        name=water_network_name,
        ds_type="random_type",
        data={
            "road_segment_entities": {
                "id": [1, 2],
                "shape_properties": {
                    "linestring_3d": [
                        [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                        [[1.1, 1.0, 1.0], [1.05, 1.0, -1.0]],
                    ]
                },
            },
        },
    )


class TestCargoDemand:
    @pytest.fixture
    def model_config(
        self,
        model_name,
        road_network_name,
        scenario_parameters_csv_name,
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "total_inward_demand_property": [],
            "total_outward_demand_property": [],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2"],
            "global_elasticities": [2, -1],
            "local_entity_groups": [],
            "local_properties": [],
            "local_geometries": [],
            "local_geometry_entities": [],
            "local_elasticities": [],
        }

    def test_demand_calculation(self, config, model_name, road_network_name, global_schema):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[1, 2, 3], [5, 0, 0], [0, 0, 0]],
                                "transport.cargo_demand": [
                                    [6, 0, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 2, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [121.5, 0, 0],
                                    [202.5, 0, 0],
                                ],
                            }
                        }
                    },
                },
            ],
        }
        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestPassengerDemand:
    @pytest.fixture
    def model_config(
        self,
        model_name,
        road_network_name,
        scenario_parameters_csv_name,
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.passenger_demand"],
            "total_inward_demand_property": [],
            "total_outward_demand_property": [],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2"],
            "global_elasticities": [2, -1],
            "local_entity_groups": [],
            "local_properties": [],
            "local_geometries": [],
            "local_geometry_entities": [],
            "local_elasticities": [],
        }

    def test_demand_calculation(self, config, model_name, road_network_name, global_schema):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[1, 2, 3], [5, 0, 0], [0, 0, 0]],
                                "transport.cargo_demand": [
                                    [6, 0, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 2, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.passenger_demand": [
                                    [20.25, 40.50, 60.75],
                                    [101.25, 0, 0],
                                ],
                            }
                        }
                    },
                },
            ],
        }
        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoDemandSum:
    @pytest.fixture
    def model_config(
        self,
        model_name,
        road_network_name,
        scenario_parameters_csv_name,
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "total_inward_demand_property": [None, "transport.total_inward_cargo_demand_vehicles"],
            "total_outward_demand_property": [
                None,
                "transport.total_outward_cargo_demand_vehicles",
            ],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2"],
            "global_elasticities": [2, -1],
            "local_entity_groups": [],
            "local_properties": [],
            "local_geometries": [],
            "local_geometry_entities": [],
            "local_elasticities": [],
        }

    def test_demand_calculation(self, config, model_name, road_network_name, global_schema):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[1, 2, 3], [5, 0, 0], [0, 0, 0]],
                                "transport.cargo_demand": [
                                    [6, 0, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 2, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.total_inward_cargo_demand_vehicles": [16, 0, 0],
                                "transport.total_outward_cargo_demand_vehicles": [6, 10, 0],
                            }
                        }
                    },
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [121.5, 0, 0],
                                    [202.5, 0, 0],
                                ],
                                "transport.total_inward_cargo_demand_vehicles": [
                                    324,
                                    None,
                                ],
                                "transport.total_outward_cargo_demand_vehicles": [121.5, 202.5],
                            }
                        }
                    },
                },
            ],
        }
        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoWithLocalParameters:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        water_network_name,
        scenario_parameters_csv_name,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
            {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
            {"name": water_network_name, "data": waterways},
        ]

    @pytest.fixture
    def model_config(
        self, model_name, road_network_name, scenario_parameters_csv_name, water_network_name
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2"],
            "global_elasticities": [2, -1],
            "local_entity_groups": [[water_network_name, "road_segment_entities"]],
            "local_properties": [
                ["traffic_properties", "average_time"],
            ],
            "local_geometries": ["line"],
            "local_elasticities": [2],
        }

    def test_demand_calculation(
        self, config, model_name, road_network_name, water_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.cargo_demand": [
                                    [0, 6, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [1, 1]},
                            }
                        }
                    },
                },
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [2, 2]},
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [0, 121.5 * 16, 0],
                                    [202.5 * 16, 0, 0],
                                ],
                            }
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoWithLoadFactor:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        water_network_name,
        scenario_parameters_csv_name,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
            {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
            {"name": water_network_name, "data": waterways},
        ]

    @pytest.fixture
    def model_config(
        self, model_name, road_network_name, scenario_parameters_csv_name, water_network_name
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2", "load_factor_multiplier"],
            "scenario_multipliers": ["load_factor_multiplier"],
            "global_elasticities": [2, -1, 0],
            "local_entity_groups": [[water_network_name, "road_segment_entities"]],
            "local_properties": [
                ["traffic_properties", "average_time"],
            ],
            "local_geometries": ["line"],
            "local_elasticities": [2],
        }

    def test_demand_calculation(
        self, config, model_name, road_network_name, water_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.cargo_demand": [
                                    [6, 0, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [1, 1]},
                            }
                        }
                    },
                },
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [2, 2]},
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [121.5 * 16 * 20, 0, 0],
                                    [202.5 * 16 * 20, 0, 0],
                                ],
                            }
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoWithNonIterativeLocalParameters:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        water_network_name,
        scenario_parameters_csv_name,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
            {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
            {"name": water_network_name, "data": waterways},
        ]

    @pytest.fixture
    def model_config(
        self, model_name, road_network_name, scenario_parameters_csv_name, water_network_name
    ):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "scenario_parameters": [scenario_parameters_csv_name],
            "global_parameters": ["gp1", "gp2"],
            "global_elasticities": [2, -1],
            "local_entity_groups": [[water_network_name, "road_segment_entities"]],
            "local_properties": [
                ["traffic_properties", "average_time"],
            ],
            "local_geometries": ["line"],
            "local_elasticities": [2],
            "local_prop_is_iterative": [False],
        }

    def test_demand_calculation(
        self, config, model_name, road_network_name, water_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.cargo_demand": [
                                    [6.0, 0, 0],
                                    [10, 0, 0],
                                    [0, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [1, 1]},
                            }
                        }
                    },
                },
                {
                    "time": 2,
                    "data": None,
                },
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "traffic_properties": {"average_time": [2, 2]},
                            }
                        }
                    },
                },
                {
                    "time": 3,
                    "data": None,
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [121.5, 0, 0],
                                    [202.5, 0, 0],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 2,
                    "data": None,
                    "next_time": 3,
                },
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11],
                                "transport.cargo_demand": [
                                    [121.5 * 16, 0, 0],
                                    [202.5 * 16, 0, 0],
                                ],
                            }
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoDemandWithInvestment:
    @pytest.fixture
    def scenario_parameters_csv(self, scenario_parameters_csv_name, tmp_path):
        data = [["seconds", "gp1"], [0, 1], [1, 1]]
        file = tmp_path / (scenario_parameters_csv_name + ".csv")
        file.write_text("\n".join(",".join(str(i) for i in row) for row in data))
        return file

    @pytest.fixture
    def model(self, road_network_name, scenario_parameters_csv_name):
        return TrafficDemandCalculation(
            {
                "demand_entity": [[road_network_name, "virtual_node_entities"]],
                "demand_property": [None, "transport.cargo_demand"],
                "scenario_parameters": [scenario_parameters_csv_name],
                "global_parameters": ["gp1"],
                "global_elasticities": [1],
                "investment_multipliers": [[0, 10, 2], [2, 11, 1.5], [2, 11, 2]],
            }
        )

    @pytest.fixture
    def tester(
        self,
        model,
        road_network_name,
        road_network_for_traffic,
        scenario_parameters_csv_name,
        scenario_parameters_csv,
        global_schema,
    ):
        tester = ModelTester(model, global_schema=global_schema)
        tester.add_init_data(road_network_name, road_network_for_traffic)
        tester.add_init_data(scenario_parameters_csv_name, scenario_parameters_csv)
        return tester

    @pytest.fixture
    def assert_demand_equals(self, road_network_name):
        def _assert(update, expected_demand):
            demand = update[road_network_name]["virtual_node_entities"]["transport.cargo_demand"]
            assert demand == expected_demand

        return _assert

    def test_single_investment(self, model, tester, road_network_name, assert_demand_equals):
        model.config["investment_multipliers"] = [[0, 10, 2]]

        tester.initialize()
        result, next_time = tester.update(
            0,
            {
                road_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.cargo_demand": [
                            [0, 2, 0],
                            [3, 0, 0],
                            [4, 0, 0],
                        ],
                    }
                }
            },
        )
        assert_demand_equals(
            result,
            [
                [0, 2 * 2, 0],
                [3 * 2, 0, 0],
                [4 * 2, 0, 0],
            ],
        )
        assert next_time == 1

        assert tester.update(1, None) == (None, None)

    def test_multiple_investments(self, model, tester, road_network_name, assert_demand_equals):
        model.config["investment_multipliers"] = [[0, 10, 2], [1, 11, 1.5], [1, 11, 2]]

        tester.initialize()
        tester.update(
            0,
            {
                road_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.cargo_demand": [
                            [0, 2, 0],
                            [3, 0, 0],
                            [4, 1, 0],
                        ],
                    }
                }
            },
        )
        result, next_time = tester.update(1, None)

        assert_demand_equals(
            result,
            [
                [0, 2 * 2 * 1.5 * 2, 0],
                [3 * 2 * 1.5 * 2, 0, 0],
                [4 * 2, 1 * 1.5 * 2, 0],
            ],
        )
        assert next_time is None


class TestCargoWithLocalRouting:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        water_network_name,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
            {"name": water_network_name, "data": waterways},
        ]

    @pytest.fixture
    def model_config(self, model_name, road_network_name, water_network_name):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[water_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "local_entity_groups": [[road_network_name, "road_segment_entities"]],
            "local_properties": [
                ["traffic_properties", "average_time"],
            ],
            "local_mapping_type": ["route"],
            "local_geometries": ["line"],
            "local_prop_is_iterative": [False],
            "local_elasticities": [2],
        }

    def test_demand_calculation(
        self, config, model_name, road_network_name, water_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12, 13],
                                # maps virt_node [12, 12, 10, 10] -> path_length 12->10=2, 10->12=1
                                "point_properties": {
                                    "position_x": [97702, 97702, 97700, 97700],
                                    "position_y": [434000, 434000, 434000, 434000],
                                },
                                "transport.cargo_demand": [
                                    [0, 0, 14, 5],
                                    [10, 0, 0, 0],
                                    [11, 0, 0, 0],
                                    [1, 0, 2, 0],
                                ],
                            },
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "traffic_properties": {"average_time": [1, 1, 1, 1]},
                            }
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102],
                                "traffic_properties": {"average_time": [2, 2]},
                            }
                        }
                    },
                },
                {"time": 2, "data": None},
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [103, 104],
                                "traffic_properties": {"average_time": [3, 3]},
                            }
                        }
                    },
                },
                {"time": 4, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                    "next_time": 1,
                },
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [12, 13],
                                "transport.cargo_demand": [
                                    [11 * 4, 0, 0, 0],
                                    [1 * 4, 0, 2, 0],
                                ],
                            },
                        },
                    },
                },
                {
                    "time": 3,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10],
                                "transport.cargo_demand": [
                                    [0, 0, 14 * (5 / 2) ** 2, 5 * (5 / 2) ** 2],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 4,
                    "data": None,
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoWithLocalRoutingIterative:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        water_network_name,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
            {"name": water_network_name, "data": waterways},
        ]

    @pytest.fixture
    def model_config(self, model_name, road_network_name, water_network_name):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[water_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "local_entity_groups": [[road_network_name, "road_segment_entities"]],
            "local_properties": [
                ["traffic_properties", "average_time"],
            ],
            "local_mapping_type": ["route"],
            "local_geometries": ["line"],
            "local_prop_is_iterative": [True],
            "local_elasticities": [2],
        }

    def test_demand_calculation(
        self, config, model_name, road_network_name, water_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12, 13],
                                # maps virt_node [12, 12, 10, 10] -> path_length 12->10=2, 10->12=1
                                "point_properties": {
                                    "position_x": [97702, 97702, 97700, 97700],
                                    "position_y": [434000, 434000, 434000, 434000],
                                },
                                "transport.cargo_demand": [
                                    [0, 0, 14, 5],
                                    [10, 0, 0, 0],
                                    [11, 0, 0, 0],
                                    [1, 0, 2, 0],
                                ],
                            },
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "traffic_properties": {"average_time": [1, 1, 1, 1]},
                            }
                        }
                    },
                },
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102],
                                "traffic_properties": {"average_time": [2, 2]},
                            }
                        }
                    },
                },
                {"time": 2, "data": None},
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [103, 104],
                                "traffic_properties": {"average_time": [3, 3]},
                            }
                        }
                    },
                },
                {"time": 4, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [12, 13],
                                "transport.cargo_demand": [
                                    [11 * 4, 0, 0, 0],
                                    [1 * 4, 0, 2, 0],
                                ],
                            },
                        },
                    },
                },
                {
                    "time": 2,
                    "data": None,
                },
                {
                    "time": 3,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10],
                                "transport.cargo_demand": [
                                    [0.0, 0, 14 * (5 / 2) ** 2, 5 * (5 / 2) ** 2],
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 4,
                    "data": None,
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )


class TestCargoWithInducedDemand:
    @pytest.fixture
    def init_data(
        self,
        road_network_name,
        road_network_for_traffic,
        scenario_parameters_csv_path,
        waterways,
    ):
        return [
            {"name": road_network_name, "data": road_network_for_traffic},
        ]

    @pytest.fixture
    def model_config(self, model_name, road_network_name):
        return {
            "name": model_name,
            "type": "traffic_demand_calculation",
            "demand_entity": [[road_network_name, "virtual_node_entities"]],
            "demand_property": [None, "transport.cargo_demand"],
            "local_entity_groups": [[road_network_name, "road_segment_entities"]],
            "local_properties": [
                [None, "transport.layout"],
            ],
            "local_mapping_type": ["extended_route"],
            "local_geometries": ["line"],
            "local_prop_is_iterative": [False],
            "local_elasticities": [2],
        }

    def test_demand_calculation(self, config, model_name, road_network_name, global_schema):
        scenario = {
            "updates": [
                {
                    # Publish road lengths, required for induced demand
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                # maps virt_node [12, 12, 10, 10] -> path_length 12->10=2, 10->12=1
                                "line_properties": {"length": [1, 2, 3, 42]},
                                "traffic_properties": {"average_time": [5, 6, 7, 8]},
                            },
                        }
                    },
                },
                {
                    # Publish demands lengths, required to calculate any demand at all
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.cargo_demand": [
                                    [0, 0, 14],
                                    [10, 0, 0],
                                    [11, 0, 0],
                                ],
                            },
                        }
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101],
                                "transport.layout": [[2, 0, 0, 0]],
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {"time": 0, "data": None},
                {"time": 0, "data": None},
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [11, 12],
                                "transport.cargo_demand": [
                                    [10 * ((2 * 1) / (1 * 1)) ** 2, 0, 0],
                                    [11 * ((2 * 1 + 2 * 3) / (1 * 1 + 2 * 3)) ** 2, 0, 0],
                                ],
                            },
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=TrafficDemandCalculation,
            model_name=model_name,
            scenario=scenario,
            rtol=0.01,
            global_schema=global_schema,
        )
