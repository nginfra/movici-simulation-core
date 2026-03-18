import dataclasses
import typing as t

import pytest

from movici_simulation_core.core.attribute import INIT, SUB
from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from movici_simulation_core.models.area_aggregation.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@dataclasses.dataclass
class Aggregation:
    source_entity_group: t.List[str]
    source_attribute: str
    target_attribute: str
    function: str
    source_geometry: str


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
    return [area_dataset_name, "area_entities"]


def create_model_config(
    model_name,
    aggregations,
    target_entity,
    interval=None,
):
    return {
        "name": model_name,
        "type": "area_aggregation",
        "aggregations": [dataclasses.asdict(agg) for agg in aggregations],
        "target_entity_group": target_entity,
        "output_interval": interval,
    }


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def aggregations(knotweed_dataset_name, road_network_name):
    return [
        Aggregation(
            source_entity_group=[knotweed_dataset_name, "knotweed_entities"],
            source_attribute="source_a",
            target_attribute="target_a",
            function="max",
            source_geometry="point",
        ),
        Aggregation(
            source_entity_group=[road_network_name, "road_segment_entities"],
            source_attribute="source_b",
            target_attribute="target_b",
            function="sum",
            source_geometry="line",
        ),
    ]


@pytest.fixture
def output_interval():
    return None


@pytest.fixture
def model_config(
    model_name,
    target_entity_group,
    aggregations,
    output_interval,
):
    config = create_model_config(
        model_name=model_name,
        aggregations=aggregations,
        target_entity=target_entity_group,
        interval=output_interval,
    )
    return config


@pytest.fixture
def model(state, model_config, global_schema):
    model = Model(model_config)
    model.setup(state=state, schema=global_schema)
    return model


def test_model_setup_fills_state(model: Model, state):
    assert model.target_entity.__entity_name__ == "area_entities"
    assert model.target_entity._polygon_legacy.is_initialized() is False
    assert len(model.aggregators) == 2
    assert len(model.src_entities) == 2

    assert len(state.all_attributes()) >= 9
    assert state.is_ready_for(INIT) is False
    assert state.is_ready_for(SUB) is False


def test_model_raises_not_ready_if_lines_have_no_data(model, state):
    with pytest.raises(NotReady):
        model.initialize(state=state)


class TestAreaAggregation:
    def test_datasets_overlap(
        self,
        create_model_tester,
        model_config,
        model_name,
        area_dataset_name,
        road_network_name,
        knotweed_dataset_name,
    ):
        # The area dataset contains two box-like polygons:
        #  * (0, 0) -> (2000, 2000)
        #  * (0, 0) -> (0.5, 0.5)

        tester = create_model_tester(Model, model_config)
        tester.initialize()

        tester.update(
            0,
            {
                road_network_name: {
                    "road_segment_entities": {
                        "id": [1, 2, 3],
                        "source_b": [1, 5, 13],
                    }
                },
            },
        )
        model: Model = tester.model
        knotweed_mapping = list(i.tolist() for i in model.aggregators[0].mapping.iterate())
        roads_mapping = list(i.tolist() for i in model.aggregators[1].mapping.iterate())

        # The knotweed dataset contains two points:
        #   * (0, 0) -> maps to both areas
        #   * (1, 1) -> maps only to the first area
        assert knotweed_mapping == [[0, 1], [0]]

        # The area dataset contains three roads:
        # * [[0, -10], [1,-10]] -> not in any area
        # * [[1.1, 1.0], [1.05, 1.0]] -> In area 0 but not in area 1
        # * [[0, 0], [0.1, 0.0], [1,1], [-0.9, 1]] -> in both areas
        assert roads_mapping == [[1, 2], [2]]

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
                                # target_a is based on source_a which has values [80, 100]
                                # (see knotweed_dataset knotweed.stem_density)
                                # area 0 matches both points while area 1 only matches the first
                                # point. target_a shows the aggregated max
                                "target_a": [100, 80],
                                # target_b is based on source_b which has values [1, 5, 13]
                                # area 0 contains roads 1 and 2
                                # area 1 contains only road 2
                                # target_b shows the weighted sum. road 2 is contributing to two
                                # areas so only counts half for each while road 1 is contributing
                                # to only 1 area and counts fully for that area
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
                                # source_a goes from 100 to 42 for point 0, so the max drops for
                                # area 0. Area 1 is unaffected, so no change
                                "target_a": [80, None],
                                # source_b goes from 13 to 2 for road 3, so it's relative
                                # ontribution drops to 4/2=2
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
    def aggregations(self, aggregations: t.List[Aggregation]):
        agg1, agg2 = aggregations
        return [
            agg1,
            dataclasses.replace(
                agg2,
                source_entity_group=agg1.source_entity_group,
                source_geometry=agg1.source_geometry,
            ),
        ]

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
    def aggregations(self, aggregations: t.List[Aggregation]):
        agg1, agg2 = aggregations
        return [
            dataclasses.replace(
                agg1,
                function="integral",
                source_geometry=agg1.source_geometry,
            ),
            dataclasses.replace(
                agg2,
                function="sum",
                source_entity_group=agg1.source_entity_group,
                source_geometry=agg1.source_geometry,
            ),
        ]

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


@pytest.fixture
def legacy_model_config(
    model_name,
    aggregations: t.List[Aggregation],
    target_entity_group,
    output_interval,
):
    return {
        "name": model_name,
        "type": "area_aggregation",
        "source_entity_groups": [agg.source_entity_group for agg in aggregations],
        "source_properties": [[None, agg.source_attribute] for agg in aggregations],
        "source_geometry_types": [agg.source_geometry for agg in aggregations],
        "aggregation_functions": [agg.function for agg in aggregations],
        "target_properties": [[None, agg.target_attribute] for agg in aggregations],
        "target_entity_group": [target_entity_group],
        "output_interval": output_interval,
    }


def test_convert_legacy_model_config(legacy_model_config, model_config):
    del model_config["name"]
    del model_config["type"]
    assert Model(legacy_model_config).config == model_config
