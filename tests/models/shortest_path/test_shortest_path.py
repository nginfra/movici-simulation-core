import json
import typing as t

from movici_simulation_core.models.shortest_path import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.shortest_path.model import ShortestPathModel
from movici_simulation_core.testing.model_schema import model_config_validator
from movici_simulation_core.testing.model_tester import ModelTester
import numpy as np
import pytest


@pytest.fixture
def get_model_config(road_network_name):
    def _get_model_config(calculation: dict, cost_factor="transport.average_time", **kwargs):

        return {
            "name": "my_shortest_path",
            "type": "shortest_path",
            "transport_segments": [[road_network_name, "road_segment_entities"]],
            "cost_factor": [None, cost_factor],
            "calculations": [calculation],
            **kwargs,
        }

    return _get_model_config


@pytest.fixture
def model_config(get_model_config):
    return get_model_config(
        {
            "type": "sum",
            "input": [None, "shape.length"],
            "output": [None, "transport.shortest_path_length"],
        }
    )


class TestShortestPathModel:
    @pytest.fixture
    def special(self):
        return -2

    @pytest.fixture
    def init_data(self, road_network_name, road_network_for_traffic, special):
        road_network_for_traffic["general"] = {
            "special": {"virtual_node_entities.transport.shortest_path_length": special}
        }
        return [(road_network_name, road_network_for_traffic)]

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )

    @pytest.fixture
    def update_data(self, road_network_name):
        return {
            road_network_name: {
                "road_segment_entities": {
                    "id": [101, 102, 103, 104],
                    "transport.average_time": [1, 2, 3, 10],
                    "shape.length": [1, 2, 3, 4],
                }
            }
        }

    def test_data_mask(self, tester: ModelTester, road_network_name):
        datamask = tester.initialize()

        def setify(dm):
            for k, v in dm.items():
                if isinstance(v, t.Sequence):
                    dm[k] = set(v)
                else:
                    setify(v)
            return datamask

        assert setify(datamask) == {
            "pub": {
                road_network_name: {
                    "virtual_node_entities": {
                        "transport.shortest_path_length",
                    }
                },
            },
            "sub": {
                road_network_name: {
                    "virtual_node_entities": {
                        "reference",
                        "geometry.x",
                        "geometry.y",
                    },
                    "virtual_link_entities": {
                        "reference",
                        "topology.from_node_id",
                        "topology.to_node_id",
                        "geometry.linestring_2d",
                        "geometry.linestring_3d",
                    },
                    "transport_node_entities": {
                        "reference",
                        "geometry.x",
                        "geometry.y",
                    },
                    "road_segment_entities": {
                        "reference",
                        "topology.from_node_id",
                        "topology.to_node_id",
                        "geometry.linestring_2d",
                        "geometry.linestring_3d",
                        "shape.length",
                        "transport.average_time",
                        "transport.layout",
                    },
                }
            },
        }

    @pytest.mark.parametrize(
        "calculation_type, expected",
        [
            ("sum", [[0, 5, 2], [1, 0, 3], [4, 3, 0]]),
            (
                "weighted_average",
                [
                    [-2, (2 * 2 + 3 * 3) / 5, 2],
                    [1, -2, (1 * 1 + 2 * 2) / 3],
                    [(1 * 1 + 3 * 3) / 4, 3, -2],
                ],
            ),
        ],
    )
    def test_shortest_path_model(
        self,
        create_model_tester,
        get_model_config,
        update_data,
        road_network_name,
        calculation_type,
        expected,
    ):
        model_config = get_model_config(
            calculation={
                "type": calculation_type,
                "input": [None, "shape.length"],
                "output": [None, "transport.shortest_path_length"],
            }
        )
        tester = create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )
        tester.initialize()
        result, _ = tester.update(0, update_data)
        length = result[road_network_name]["virtual_node_entities"][
            "transport.shortest_path_length"
        ]
        np.testing.assert_allclose(length, expected)

    def test_update_shortest_path(
        self,
        create_model_tester,
        get_model_config,
        update_data,
        road_network_name,
    ):
        def extract_length(result):
            return result[road_network_name]["virtual_node_entities"][
                "transport.shortest_path_length"
            ]

        model_config = get_model_config(
            # no_update_shortest_path=True,
            calculation={
                "type": "sum",
                "input": [None, "shape.length"],
                "output": [None, "transport.shortest_path_length"],
            },
        )
        tester = create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )
        tester.initialize()
        result, _ = tester.update(0, update_data)
        lengths = extract_length(result)
        np.testing.assert_allclose(
            lengths,
            [
                [0, 5, 2],
                [1, 0, 1 + 2],
                [1 + 3, 3, 0],
            ],
        )
        # setting average time so that a the shortest path goes over a new route. However, this
        # route should not be taken for the weighted average calculation. The new average time
        # should be taken to calculate the weights though

        average_time = [2, 3, 4, 0.3]
        update_data[road_network_name]["road_segment_entities"][
            "transport.average_time"
        ] = average_time
        result, _ = tester.update(1, update_data)
        lengths = extract_length(result)
        np.testing.assert_allclose(
            lengths,
            [
                # [0, 5, 2], # first row is not affected
                [4, 0, 4 + 2],
                [7, 3, 0],
            ],
        )

    def test_updated_weighted_average_with_no_update_shortest_path(
        self,
        create_model_tester,
        get_model_config,
        update_data,
        road_network_name,
    ):
        def extract_length(result):
            return result[road_network_name]["virtual_node_entities"][
                "transport.shortest_path_length"
            ]

        model_config = get_model_config(
            no_update_shortest_path=True,
            calculation={
                "type": "weighted_average",
                "input": [None, "shape.length"],
                "output": [None, "transport.shortest_path_length"],
            },
        )
        tester = create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )
        tester.initialize()
        result, _ = tester.update(0, update_data)
        lengths = extract_length(result)
        np.testing.assert_allclose(
            lengths,
            [
                [-2, (2 * 2 + 3 * 3) / 5, 2],
                [1, -2, (1 * 1 + 2 * 2) / 3],
                [(1 * 1 + 3 * 3) / 4, 3, -2],
            ],
        )
        # setting average time so that a the shortest path goes over a new route. However, this
        # route should not be taken for the weighted average calculation. The new average time
        # should be taken to calculate the weights though

        average_time = [2, 3, 4, 0.3]
        update_data[road_network_name]["road_segment_entities"][
            "transport.average_time"
        ] = average_time
        result, _ = tester.update(1, update_data)
        lengths = extract_length(result)
        np.testing.assert_allclose(
            lengths,
            [
                [-2, (2 * 3 + 3 * 4) / 7, 2],
                [1, -2, (1 * 2 + 2 * 3) / 5],
                [(1 * 2 + 3 * 4) / 6, 3, -2],
            ],
        )


@pytest.fixture
def json_schema():
    return json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())


def test_validate_model_config(model_config, json_schema):
    assert model_config_validator(json_schema)(model_config)


@pytest.mark.parametrize("value", [True, False])
def test_validate_config_with_no_update_shortest_path(value, model_config, json_schema):
    model_config["no_update_shortest_path"] = value
    assert model_config_validator(json_schema)(model_config)
