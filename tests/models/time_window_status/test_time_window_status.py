import pytest
from model_engine import testing
from movici_simulation_core.models.time_window_status.model import Model


@pytest.fixture
def time_scale():
    return 86400


@pytest.fixture
def model_name():
    return "test_time_window_status"


@pytest.fixture
def maintenance_agenda_dataset_name():
    return "a_maintenance_agenda"


@pytest.fixture
def config(
    model_config, init_data, time_scale,
):
    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 730,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture
def init_data(
    maintenance_agenda_dataset_name,
    maintenance_agenda,
    road_network_name,
    road_network,
    mv_network_name,
    mv_network,
):
    return [
        {"name": maintenance_agenda_dataset_name, "data": maintenance_agenda},
        {"name": road_network_name, "data": road_network},
        {"name": mv_network_name, "data": mv_network},
    ]


@pytest.fixture
def model_config(model_name, road_network_name, mv_network_name):
    return {
        "name": model_name,
        "type": "time_window_status",
        "time_window_dataset": [("a_maintenance_agenda", "maintenance_job_entities")],
        "status_datasets": [
            (road_network_name, "road_segment_entities"),
            (mv_network_name, "electrical_node_entities"),
        ],
        "time_window_begin": (None, "maintenance.window_begin.date"),
        "time_window_end": (None, "maintenance.window_end.date"),
        "time_window_status": ("operation_status_properties", "is_working_properly"),
    }


class TestTimeWindowStatus:
    def test_maintenance_window(
        self, get_entity_update, config, model_name, mv_network_name, road_network_name, time_scale
    ):
        scenario = {
            "updates": [{"time": 0, "data": {}}],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                properties=[True, False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                properties=[False, False, False, False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                    "next_time": 9 * time_scale,
                },
                {
                    "time": 9,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1],
                                properties=[False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            )
                        }
                    },
                    "next_update": 30 * time_scale,
                },
                {
                    "time": 31,
                    "data": {
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [2, 4],
                                properties=[True, True],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        }
                    },
                    "next_update": 39 * time_scale,
                },
                {
                    "time": 40,
                    "data": {
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [2, 4],
                                properties=[False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=Model, name=model_name, scenario=scenario, atol=0.01,
        )


class TestTimeWindowStatusSameEntity:
    @pytest.fixture
    def model_config(self, model_name, road_network_name, mv_network_name):
        return {
            "name": model_name,
            "type": "time_window_status",
            "time_window_dataset": [("a_maintenance_agenda", "maintenance_job_entities")],
            "status_datasets": [(road_network_name, "road_segment_entities")],
            "time_window_begin": (None, "maintenance.job_begin.date"),
            "time_window_end": (None, "maintenance.job_end.date"),
            "time_window_status": (None, "maintenance.under_maintenance"),
        }

    @pytest.fixture
    def maintenance_agenda(self, maintenance_agenda_dataset_name):
        return {
            "version": 3,
            "name": maintenance_agenda_dataset_name,
            "type": "maintenance_agenda",
            "display_name": "Test Maintenance Agenda",
            "general": {"enum": {"maintenance_job_entities": {"type": ["replacement"]}}},
            "data": {
                "maintenance_job_entities": {
                    "maintenance.job_begin.date": ["2019-01-01", "2020-01-02"],
                    "maintenance.job_end.date": ["2020-01-10", "2020-02-10"],
                    "maintenance.job_duration.days": [200, 40],
                    "id": [0, 1],
                    "type": [0, 0],
                    "connection_properties": {
                        "to_dataset_type": ["road_network", "road_network"],
                        "to_dataset": ["a_road_network", "a_road_network"],
                        "to_references": [["100"], ["100"]],
                    },
                }
            },
        }

    def test_multiple_maintence_same_entity(
        self, get_entity_update, config, model_name, mv_network_name, road_network_name, time_scale
    ):
        scenario = {
            "updates": [{"time": 0, "data": {}}],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                properties=[True, False, False],
                                key_name="maintenance.under_maintenance",
                            ),
                        },
                    },
                    "next_time": 1 * time_scale,
                },
                {"time": 1, "data": {}, "next_time": 10 * time_scale},
                {"time": 10, "data": {}, "next_time": 31 * time_scale},
                {
                    "time": 31,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1], properties=[False], key_name="maintenance.under_maintenance",
                            )
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=Model, name=model_name, scenario=scenario, atol=0.01,
        )
