import pytest

from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.data_tracker.attribute import INIT, SUB
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.models.area_aggregation.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def source_entity_group1(knotweed_dataset_name):
    return [knotweed_dataset_name, "knotweed_entities"]


@pytest.fixture
def source_entity_group2(road_network_name):
    return [road_network_name, "road_segment_entities"]


source_attributes1 = [None, "source_a"]
target_attributes1 = [None, "target_a"]

source_attributes2 = [None, "source_b"]
target_attributes2 = [None, "target_b"]


@pytest.fixture
def additional_attributes():
    return [
        AttributeSpec("source_a", DataType(float, (), False)),
        AttributeSpec("source_b", DataType(float, (), False)),
        AttributeSpec("target_a", DataType(float, (), False)),
        AttributeSpec("target_b", DataType(float, (), False)),
        AttributeSpec("str_attr", DataType(str, (), False)),
        AttributeSpec("csr_attr", DataType(int, (), True)),
        AttributeSpec("multi_dimensional", DataType(float, (2,), False)),
        AttributeSpec("knotweed.stem_density", DataType(float, (), False)),
    ]


@pytest.fixture
def knotweed_dataset(knotweed_dataset):
    knotweed_dataset["data"]["knotweed_entities"]["source_a"] = knotweed_dataset["data"][
        "knotweed_entities"
    ]["knotweed.stem_density"]
    return knotweed_dataset


@pytest.fixture
def init_data(
    knotweed_dataset_name,
    area_dataset_name,
    road_network_name,
    knotweed_dataset,
    area_dataset,
    road_network,
):
    return [
        {"name": knotweed_dataset_name, "data": knotweed_dataset},
        {"name": area_dataset_name, "data": area_dataset},
        {"name": road_network_name, "data": road_network},
    ]


@pytest.fixture
def target_entity_group(area_dataset_name):
    return [[area_dataset_name, "area_entities"]]


def create_model_config(
    model_name,
    source_entities,
    source_attrs,
    source_geom,
    functions,
    target_entity,
    target_attrs,
    interval=None,
):
    return {
        "name": model_name,
        "type": "area_aggregation",
        "source_entity_groups": source_entities,
        "source_properties": source_attrs,
        "source_geometry_types": source_geom,
        "aggregation_functions": functions,
        "target_properties": target_attrs,
        "target_entity_group": target_entity,
        "output_interval": interval,
    }


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def source_geom():
    return ["point", "line"]


@pytest.fixture
def output_interval():
    return None


@pytest.fixture
def aggregation_functions():
    return ["max", "sum"]


@pytest.fixture
def model_config(
    model_name,
    area_dataset_name,
    target_entity_group,
    aggregation_functions,
    source_entity_group1,
    source_entity_group2,
    source_geom,
    output_interval,
):
    source_entities = [source_entity_group1, source_entity_group2]
    source_attrs = [source_attributes1, source_attributes2]
    source_geom = source_geom
    target_attrs = [target_attributes1, target_attributes2]
    config = create_model_config(
        model_name=model_name,
        source_entities=source_entities,
        source_attrs=source_attrs,
        source_geom=source_geom,
        functions=aggregation_functions,
        target_entity=target_entity_group,
        target_attrs=target_attrs,
        interval=output_interval,
    )
    return config


@pytest.fixture
def model(state, model_config, global_schema):
    model = Model(model_config)
    model.setup(state=state, schema=global_schema)
    return model


def test_model_setup_fills_state(model, state):
    assert model.target_entity.__entity_name__ == "area_entities"
    assert model.target_entity.polygon.is_initialized() is False
    assert len(model.aggregators) == 2
    assert len(model.src_entities) == 2

    assert len(state.all_attributes()) >= 9
    assert state.is_ready_for(INIT) is False
    assert state.is_ready_for(SUB) is False


def test_model_raises_not_ready_if_lines_have_no_data(model, state):
    with pytest.raises(NotReady):
        model.initialize(state=state)


class TestAreaAggregation:
    def test_area_aggregation_calculation(
        self,
        config,
        model_name,
        area_dataset_name,
        road_network_name,
        knotweed_dataset_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": {}},
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "source_b": [1, 5, 13],
                            }
                        },
                    },
                },
                {
                    "time": 10,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [3],
                                "source_b": [4],
                            }
                        },
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [1],
                                "source_a": [42],
                            }
                        },
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
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [100, 80],
                                "target_b": [11.5, 6.5],
                            },
                        },
                    },
                },
                {
                    "time": 10,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [80, None],
                                "target_b": [7, 2],
                            },
                        },
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


class TestMultipleAttributesOneEntity:
    @pytest.fixture
    def source_entity_group2(self, source_entity_group1):
        return source_entity_group1

    source_attributes1 = [None, "source_a"]
    target_attributes1 = [None, "target_a"]

    source_attributes2 = [None, "source_b"]
    target_attributes2 = [None, "target_b"]

    @pytest.fixture
    def source_geom(self):
        return ["point", "point"]

    @pytest.fixture
    def init_data(
        self,
        knotweed_dataset_name,
        area_dataset_name,
        knotweed_dataset,
        area_dataset,
    ):
        return [
            {"name": knotweed_dataset_name, "data": knotweed_dataset},
            {"name": area_dataset_name, "data": area_dataset},
        ]

    def test_multiple_attrs_in_one_entity_group(
        self, config, model_name, area_dataset_name, knotweed_dataset_name, global_schema
    ):
        scenario = {
            "updates": [
                {"time": 0, "data": {}},
                {
                    "time": 0,
                    "data": {
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "source_b": [1, 5],
                            }
                        },
                    },
                },
                {
                    "time": 10,
                    "data": {
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "source_a": [42.0, None],
                                "source_b": [None, 4.0],
                            }
                        },
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
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [100, 80],
                                "target_b": [5.5, 0.5],
                            },
                        },
                    },
                },
                {
                    "time": 10,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [None, 42],
                                "target_b": [4.5, None],
                            },
                        },
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


class TestTimeIntegration:
    @pytest.fixture
    def output_interval(self):
        return 2

    @pytest.fixture
    def aggregation_functions(self):
        return ["integral", "sum"]

    @pytest.fixture
    def source_entity_group2(self, source_entity_group1):
        return source_entity_group1

    source_attributes1 = [None, "source_a"]
    target_attributes1 = [None, "target_a"]

    source_attributes2 = [None, "source_b"]
    target_attributes2 = [None, "target_b"]

    @pytest.fixture
    def source_geom(self):
        return ["point", "point"]

    @pytest.fixture
    def init_data(
        self,
        knotweed_dataset_name,
        area_dataset_name,
        knotweed_dataset,
        area_dataset,
    ):
        return [
            {"name": knotweed_dataset_name, "data": knotweed_dataset},
            {"name": area_dataset_name, "data": area_dataset},
        ]

    def test_time_integration(
        self, config, model_name, area_dataset_name, knotweed_dataset_name, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "source_b": [1, 5],
                            }
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
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "source_a": [42, None],
                            }
                        },
                    },
                },
                {
                    "time": 5,
                    "data": None,
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [0, 0],  # + [(40,100), 40] per dt
                                "target_b": [5.5, 0.5],
                            },
                        },
                    },
                    "next_time": 2,
                },
                {
                    "time": 2,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [280, 80],
                            },
                        },
                    },
                    "next_time": 4,
                },
                {
                    "time": 3,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [420, 120],  # + [(21,100), 21] per dt
                            },
                        },
                    },
                    "next_time": 5,
                },
                {
                    "time": 5,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "target_a": [662, 162],
                            },
                        },
                    },
                    "next_time": 7,
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


def valid_attr():
    return [target_attributes1]


def valid_target_entity_group():
    return [["bla", "area_entities"]]


def valid_source_entity_group():
    return [["knotweed_dataset_name", "knotweed_entities"]]
