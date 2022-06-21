import json
import typing as t

import jsonschema
import numpy as np
import pytest

from movici_simulation_core.models.shortest_path import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.shortest_path.model import ShortestPathModel
from movici_simulation_core.validate import validate_and_process


@pytest.fixture
def get_model_config(road_network_name):
    def _get_model_config(calculation: dict, cost_factor="transport.average_time", **kwargs):

        return {
            "transport_segments": [road_network_name, "road_segment_entities"],
            "cost_factor": cost_factor,
            "calculations": [calculation],
            **kwargs,
        }

    return _get_model_config


@pytest.fixture
def model_config(get_model_config):
    return get_model_config(
        {
            "type": "sum",
            "input": "shape.length",
            "output": "transport.shortest_path_length",
        }
    )


@pytest.fixture
def legacy_model_config(road_network_name):
    return {
        "transport_segments": [[road_network_name, "road_segment_entities"]],
        "cost_factor": [None, "transport.average_time"],
        "calculations": [
            {
                "type": "sum",
                "input": [None, "shape.length"],
                "output": [None, "transport.shortest_path_length"],
            }
        ],
    }


@pytest.fixture
def special():
    return -2


@pytest.fixture
def init_data(road_network_name, road_network_for_traffic, special):
    road_network_for_traffic["general"] = {
        "special": {
            "virtual_node_entities.transport.shortest_path_length": special,
            "virtual_node_entities.transport.total_length": special,
        }
    }
    return [(road_network_name, road_network_for_traffic)]


class TestShortestPathModel:
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

    def test_data_mask(self, model_config, create_model_tester, road_network_name):
        tester = create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )
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
                "input": "shape.length",
                "output": "transport.shortest_path_length",
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
                "input": "shape.length",
                "output": "transport.shortest_path_length",
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
                "input": "shape.length",
                "output": "transport.shortest_path_length",
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


class TestShortestPathModelSingleSource:
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

    @pytest.mark.parametrize(
        "calculation_type,source, expected",
        [
            ("sum", "VN2", [1, 0, 3]),
            ("sum", 11, [1, 0, 3]),
            ("weighted_average", 11, [1, -2, (1 * 1 + 2 * 2) / 3]),
        ],
    )
    def test_shortest_path_single_source(
        self,
        create_model_tester,
        get_model_config,
        update_data,
        road_network_name,
        calculation_type,
        source,
        expected,
    ):
        key = (
            "single_source_entity_id"
            if isinstance(source, int)
            else "single_source_entity_reference"
        )
        model_config = get_model_config(
            calculation={
                "type": calculation_type,
                "input": "shape.length",
                "output": "transport.total_length",
                key: source,
            }
        )
        tester = create_model_tester(
            ShortestPathModel, model_config, raise_on_premature_shutdown=False
        )
        tester.initialize()
        result, _ = tester.update(0, update_data)
        length = result[road_network_name]["virtual_node_entities"]["transport.total_length"]
        np.testing.assert_allclose(length, expected)


@pytest.fixture
def json_schema():
    return json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())


@pytest.mark.parametrize(
    "extra_props, calculation",
    [
        (None, None),
        ({"no_update_shortest_path": True}, None),
        ({"no_update_shortest_path": False}, None),
        (
            None,
            {
                "type": "sum",
                "input": "foo_attr",
                "output": "bar_attr",
                "single_source_entity_reference": "ref",
            },
        ),
        (
            None,
            {
                "type": "sum",
                "input": "foo_attr",
                "output": "bar_attr",
                "single_source_entity_id": 42,
            },
        ),
    ],
)
def test_validate_model_config(
    extra_props, calculation, model_config, get_model_config, json_schema
):
    if calculation is not None:
        model_config = get_model_config(calculation)
    if extra_props:
        model_config.update(extra_props)
    assert validate_and_process(model_config, json_schema)


@pytest.mark.parametrize(
    "extra_props, calculation",
    [
        ({"invalid": True}, None),
        (
            None,
            {
                "type": "invalid",
                "input": "foo_attr",
                "output": "bar_attr",
            },
        ),
        (
            None,
            {
                "type": "sum",
                "input": "foo_attr",
                "output": "bar_attr",
                "single_source_entity_reference": 42,
            },
        ),
        (
            None,
            {
                "type": "sum",
                "input": "foo_attr",
                "output": "bar_attr",
                "single_source_entity_id": "ref",
            },
        ),
    ],
)
def test_invalid_model_config(
    extra_props, calculation, model_config, get_model_config, json_schema
):
    if calculation is not None:
        model_config = get_model_config(calculation)
    if extra_props:
        model_config.update(extra_props)
    with pytest.raises(jsonschema.ValidationError):
        validate_and_process(model_config, json_schema)


def test_convert_legacy_model_config(legacy_model_config, model_config):
    assert ShortestPathModel(legacy_model_config).config == model_config
