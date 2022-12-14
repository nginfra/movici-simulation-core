import pytest

from movici_simulation_core.core.schema import AttributeSpec
from movici_simulation_core.models.time_window_status.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def time_scale():
    return 86400


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
def legacy_model_config(model_name, road_network_name, mv_network_name):
    return {
        "name": model_name,
        "type": "time_window_status",
        "time_window_dataset": [("a_maintenance_agenda", "maintenance_job_entities")],
        "status_datasets": [
            (road_network_name, "road_segment_entities"),
            (mv_network_name, "electrical_node_entities"),
        ],
        "time_window_begin": (None, "begin"),
        "time_window_end": (None, "end"),
        "time_window_status": (None, "status"),
    }


@pytest.fixture
def model_config(model_name, road_network_name, mv_network_name):
    return {
        "name": model_name,
        "type": "time_window_status",
        "source": ["a_maintenance_agenda", "maintenance_job_entities"],
        "targets": [
            {"entity_group": [road_network_name, "road_segment_entities"], "attribute": "status"},
            {"entity_group": [mv_network_name, "electrical_node_entities"], "attribute": "status"},
        ],
        "time_window_begin": "begin",
        "time_window_end": "end",
    }


@pytest.fixture
def additional_attributes():
    from movici_simulation_core.core import DataType

    return [
        AttributeSpec("topology.node_id", data_type=DataType(int, (), False)),
        AttributeSpec(
            "operational.is_working_properly",
            data_type=DataType(bool, (), False),
        ),
    ]


class TestTimeWindowStatus:
    @pytest.fixture
    def model_config(self, model_name, road_network_name, mv_network_name):
        return {
            "name": model_name,
            "type": "time_window_status",
            "source": ["a_maintenance_agenda", "maintenance_job_entities"],
            "targets": [
                {
                    "entity_group": [road_network_name, "road_segment_entities"],
                    "attribute": "status",
                },
                {
                    "entity_group": [mv_network_name, "electrical_node_entities"],
                    "attribute": "other_status",
                },
            ],
            "time_window_begin": "begin",
            "time_window_end": "end",
        }

    def test_maintenance_window(
        self,
        get_entity_update,
        config,
        model_name,
        mv_network_name,
        road_network_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": None},
                {"time": 9, "data": None},
                {"time": 31, "data": None},
                {"time": 40, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[True, False, False],
                                key_name="status",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                attributes=[False, False, False, False, False],
                                key_name="other_status",
                            ),
                        },
                    },
                    "next_time": 9,
                },
                {
                    "time": 9,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1],
                                attributes=[False],
                                key_name="status",
                            )
                        }
                    },
                    "next_time": 31,
                },
                {
                    "time": 31,
                    "data": {
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [2, 4],
                                attributes=[True, True],
                                key_name="other_status",
                            ),
                        }
                    },
                    "next_time": 40,
                },
                {
                    "time": 40,
                    "data": {
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [2, 4],
                                attributes=[False, False],
                                key_name="other_status",
                            ),
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
        )


class TestTimeWindowStatusSameEntity:
    @pytest.fixture
    def model_config(self, model_name, road_network_name):
        return {
            "name": model_name,
            "type": "time_window_status",
            "source": ["a_maintenance_agenda", "maintenance_job_entities"],
            "targets": [
                {
                    "entity_group": (road_network_name, "road_segment_entities"),
                    "attribute": "status",
                },
            ],
            "time_window_begin": "job_begin",
            "time_window_end": "job_end",
        }

    @pytest.fixture
    def maintenance_agenda(self, maintenance_agenda_dataset_name):
        return {
            "version": 3,
            "name": maintenance_agenda_dataset_name,
            "type": "maintenance_agenda",
            "display_name": "Test Maintenance Agenda",
            "data": {
                "maintenance_job_entities": {
                    "job_begin": ["2019-01-01", "2020-01-02"],
                    "job_end": ["2020-01-10", "2020-02-10"],
                    "id": [0, 1],
                    "connection.to_dataset": ["a_road_network", "a_road_network"],
                    "connection.to_references": [["100"], ["100"]],
                }
            },
        }

    def test_multiple_maintenance_same_entity(
        self, get_entity_update, config, model_name, road_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": None},
                {"time": 1, "data": None},
                {"time": 9, "data": None},
                {"time": 40, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[True, False, False],
                                key_name="status",
                            ),
                        },
                    },
                    "next_time": 1,
                },
                {"time": 1, "data": None, "next_time": 9},
                {"time": 9, "data": None, "next_time": 40},
                {
                    "time": 40,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1],
                                attributes=[False],
                                key_name="status",
                            )
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            global_schema=global_schema,
        )


class TestTimeWindowUndefinedWindow:
    @pytest.fixture
    def model_config(self, model_name, road_network_name, mv_network_name):
        return {
            "name": model_name,
            "type": "time_window_status",
            "source": ["a_maintenance_agenda", "maintenance_job_entities"],
            "targets": [
                {
                    "entity_group": (road_network_name, "road_segment_entities"),
                    "attribute": "status",
                },
            ],
            "time_window_begin": "job_begin",
            "time_window_end": "job_end",
        }

    @pytest.fixture
    def maintenance_agenda(self, maintenance_agenda_dataset_name):
        return {
            "version": 3,
            "name": maintenance_agenda_dataset_name,
            "type": "maintenance_agenda",
            "data": {
                "maintenance_job_entities": {
                    "job_begin": [None, "2019-01-01"],
                    "job_end": [None, "2020-02-10"],
                    "id": [0, 1],
                    "connection.to_dataset": ["a_road_network", "a_road_network"],
                    "connection.to_references": [["100"], ["101"]],
                }
            },
        }

    def test_maintenance_with_undefined_window(
        self,
        get_entity_update,
        config,
        model_name,
        mv_network_name,
        road_network_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": None},
                {"time": 40, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, True, False],
                                key_name="status",
                            ),
                        },
                    },
                    "next_time": 40,
                },
                {
                    "time": 40,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [2],
                                attributes=[False],
                                key_name="status",
                            )
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            global_schema=global_schema,
        )


class TestTimeWindowInEntitiesDataset:
    @pytest.fixture
    def model_config(self, model_name, road_network_name):

        return {
            "name": model_name,
            "type": "time_window_status",
            "source": [road_network_name, "road_segment_entities"],
            "targets": [
                {
                    "entity_group": (road_network_name, "road_segment_entities"),
                    "attribute": "status",
                },
            ],
            "time_window_begin": "begin",
            "time_window_end": "end",
        }

    @pytest.fixture
    def road_network(self, road_network_name):
        return {
            "version": 3,
            "name": road_network_name,
            "type": "random_type",
            "display_name": "",
            "epsg_code": 28992,
            "general": None,
            "data": {
                "road_segment_entities": {
                    "id": [1, 2, 3],
                    "reference": ["100", "101", "102"],
                    "begin": ["2020-01-11", None, "2020-01-11"],
                    "end": ["2020-01-21", None, "2020-02-01"],
                    "geometry.linestring_3d": [
                        [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                        [[1.6, 0.5, 1.0], [1.5, 0.5, -1.0]],
                        [[-0.5, 0.5, 0.0], [0.5, 0.5, -1.0], [1.5, 0.5, 1.0], [2.5, 0.5, 1.0]],
                    ],
                }
            },
        }

    def test_window_in_entities_dataset(
        self, get_entity_update, config, model_name, road_network_name, global_schema
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": None},
                {"time": 10, "data": None},
                {"time": 20, "data": None},
                {"time": 31, "data": None},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="status",
                            ),
                        },
                    },
                    "next_time": 10,
                },
                {
                    "time": 10,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 3],
                                attributes=[True, True],
                                key_name="status",
                            ),
                        },
                    },
                    "next_time": 20,
                },
                {
                    "time": 20,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1],
                                attributes=[False],
                                key_name="status",
                            ),
                        },
                    },
                    "next_time": 31,
                },
                {
                    "time": 31,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [3],
                                attributes=[False],
                                key_name="status",
                            )
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            global_schema=global_schema,
        )


def test_convert_legacy_model_config(legacy_model_config, model_config):
    del model_config["name"]
    del model_config["type"]
    assert Model(legacy_model_config).config == model_config
