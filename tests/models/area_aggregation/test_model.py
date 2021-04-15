import pytest
from model_engine import testing
from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.data_tracker.property import INIT, SUB, UNDEFINED
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.models.area_aggregation.model import Model


@pytest.fixture
def source_entity_group1(knotweed_dataset_name):
    return [knotweed_dataset_name, "knotweed_entities"]


@pytest.fixture
def source_entity_group2(road_network_name):
    return [road_network_name, "road_segment_entities"]


source_properties1 = [None, "knotweed.stem_density"]
target_properties1 = [None, "construction.year"]

source_properties2 = [None, "monetary.value"]
target_properties2 = [None, "monetary.damage"]


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
    source_props,
    source_geom,
    functions,
    target_entity,
    target_props,
    interval=None,
):
    return {
        "name": model_name,
        "type": "area_aggregation",
        "source_entity_groups": source_entities,
        "source_properties": source_props,
        "source_geometry_types": source_geom,
        "aggregation_functions": functions,
        "target_properties": target_props,
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
    source_props = [source_properties1, source_properties2]
    source_geom = source_geom
    target_props = [target_properties1, target_properties2]
    config = create_model_config(
        model_name=model_name,
        source_entities=source_entities,
        source_props=source_props,
        source_geom=source_geom,
        functions=aggregation_functions,
        target_entity=target_entity_group,
        target_props=target_props,
        interval=output_interval,
    )
    return config


@pytest.fixture
def model(state, model_config):
    model = Model()
    model.setup(state=state, config=model_config)
    return model


def test_model_setup_fills_state(model, state):
    assert model.target_entity.__entity_name__ == "area_entities"
    assert model.target_entity.polygon.is_initialized() is False
    assert len(model.aggregators) == 2
    assert len(model.src_entities) == 2

    assert len(state.all_properties()) >= 9
    assert state.is_ready_for(INIT) is False
    assert state.is_ready_for(SUB) is False


def test_model_raises_not_ready_if_lines_have_no_data(model, state):
    with pytest.raises(NotReady):
        model.initialize(state=state)


class TestAreaAggregation:
    def test_area_aggregation_calculation(
        self, config, model_name, area_dataset_name, road_network_name, knotweed_dataset_name
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
                                "monetary.value": [1, 5, 13],
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
                                "monetary.value": [4],
                            }
                        },
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [1],
                                "knotweed.stem_density": [42],
                            }
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {},
                },
                {
                    "time": 0,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "construction.year": [100, 80],
                                "monetary.damage": [11.5, 6.5],
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
                                "construction.year": [80, UNDEFINED[int]],
                                "monetary.damage": [7, 2],
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


class TestMultiplePropertiesOneEntity:
    @pytest.fixture
    def source_entity_group2(self, source_entity_group1):
        return source_entity_group1

    source_properties1 = [None, "knotweed.stem_density"]
    target_properties1 = [None, "construction.year"]

    source_properties2 = [None, "monetary.value"]
    target_properties2 = [None, "monetary.damage"]

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

    def test_multiple_props_in_one_entity_group(
        self, config, model_name, area_dataset_name, knotweed_dataset_name
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
                                "monetary.value": [1, 5],
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
                                "knotweed.stem_density": [42, UNDEFINED[float]],
                                "monetary.value": [UNDEFINED[float], 4],
                            }
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {},
                },
                {
                    "time": 0,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "construction.year": [100, 80],
                                "monetary.damage": [5.5, 0.5],
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
                                "construction.year": [UNDEFINED[int], 42],
                                "monetary.damage": [4.5, UNDEFINED[float]],
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

    source_properties1 = [None, "knotweed.stem_density"]
    target_properties1 = [None, "construction.year"]

    source_properties2 = [None, "monetary.value"]
    target_properties2 = [None, "monetary.damage"]

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

    def test_time_integration(self, config, model_name, area_dataset_name, knotweed_dataset_name):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "monetary.value": [1, 5],
                            }
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {},
                },
                {
                    "time": 3,
                    "data": {
                        knotweed_dataset_name: {
                            "knotweed_entities": {
                                "id": [0, 1],
                                "knotweed.stem_density": [42, UNDEFINED[float]],
                            }
                        },
                    },
                },
                {
                    "time": 5,
                    "data": {},
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        area_dataset_name: {
                            "area_entities": {
                                "id": [0, 2],
                                "construction.year": [0, 0],  # + [(40,100), 40] per dt
                                "monetary.damage": [5.5, 0.5],
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
                                "construction.year": [280, 80],
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
                                "construction.year": [420, 120],  # + [(21,100), 21] per dt
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
                                "construction.year": [662, 162],
                            },
                        },
                    },
                    "next_time": 7,
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


def valid_prop():
    return [target_properties1]


def valid_target_entity_group():
    return [["bla", "area_entities"]]


def valid_source_entity_group():
    return [["knotweed_dataset_name", "knotweed_entities"]]


class TestModelInputChecking:
    @pytest.mark.parametrize(
        ["source_prop", "target_prop", "target_entity", "error_contains"],
        [
            (
                [[None, "display_name"]],
                valid_prop(),
                valid_target_entity_group(),
                "has string type",
            ),
            (
                [target_properties1, target_properties1],
                valid_prop(),
                valid_target_entity_group(),
                "must have the same length",
            ),
            (
                [[None, "labels"]],
                valid_prop(),
                valid_target_entity_group(),
                "should be of uniform data",
            ),
            (
                [["road_segment_properties", "layout"]],
                valid_prop(),
                valid_target_entity_group(),
                "should be one-dimensional",
            ),
            (
                valid_prop(),
                valid_prop(),
                [["more", "than", "two"]],
                "exactly 1 dataset_name",
            ),
            (
                valid_prop(),
                valid_prop(),
                ["single", "list"],
                "exactly 1 dataset_name",
            ),
        ],
    )
    def test_model_raises_when_given_wrong_types(
        self, source_prop, target_prop, target_entity, error_contains
    ):
        model_config = create_model_config(
            model_name="model_name",
            source_entities=valid_source_entity_group(),
            source_props=source_prop,
            source_geom=["point"],
            functions=["max"],
            target_entity=target_entity,
            target_props=target_prop,
        )
        state = TrackedState()
        model = Model()
        with pytest.raises(ValueError) as e:
            model.setup(state, model_config)
        assert error_contains in str(e.value)
