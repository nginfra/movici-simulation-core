import json
from unittest import mock
import typing as t

from movici_simulation_core.core.schema import DataType
from movici_simulation_core.data_tracker.attribute import CSRAttribute, UniformAttribute
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.network import Network
from movici_simulation_core.models.generalized_journey_time import MODEL_CONFIG_SCHEMA_PATH
from movici_simulation_core.models.generalized_journey_time.crowdedness import crowdedness
from movici_simulation_core.models.generalized_journey_time.gjt_model import (
    GJTCalculator,
    GJTModel,
)
from movici_simulation_core.testing.model_schema import model_config_validator
from movici_simulation_core.testing.model_tester import ModelTester
import numpy as np
import pytest


@pytest.fixture
def model_config(railway_network_name):
    return {
        "type": "gjt",
        "travel_time": [None, "transport.passenger_average_time"],
        "transport_segments": [[railway_network_name, "track_segment_entities"]],
    }


class TestGJTModel:
    @pytest.fixture
    def init_data(self, railway_network_name, railway_network_for_traffic):
        return [(railway_network_name, railway_network_for_traffic)]

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(GJTModel, model_config, raise_on_premature_shutdown=False)

    @pytest.fixture
    def update_data(self, railway_network_name):
        return {
            railway_network_name: {
                "track_segment_entities": {
                    "id": [101, 102, 103, 104, 105],
                    "transport.passenger_average_time": [1, 1, 1, 1, 1],
                    "transport.passenger_flow": [1, 1, 2, 0, 0],
                }
            }
        }

    def test_data_mask(self, tester: ModelTester, railway_network_name):
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
                railway_network_name: {
                    "virtual_node_entities": {
                        "transport.generalized_journey_time",
                    }
                },
            },
            "sub": {
                railway_network_name: {
                    "virtual_node_entities": {
                        "reference",
                        "geometry.x",
                        "geometry.y",
                        "transport.passenger_vehicle_frequency",
                        "transport.passenger_vehicle_capacity",
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
                    "track_segment_entities": {
                        "reference",
                        "topology.from_node_id",
                        "topology.to_node_id",
                        "geometry.linestring_2d",
                        "geometry.linestring_3d",
                        "transport.layout",
                        "transport.passenger_average_time",
                        "transport.passenger_flow",
                    },
                }
            },
        }

    def test_gjt_model(self, tester: ModelTester, update_data, railway_network_name):
        tester.initialize()
        result, _ = tester.update(0, update_data)
        gjt = result[railway_network_name]["virtual_node_entities"][
            "transport.generalized_journey_time"
        ]
        gjt_1 = 3.461
        gjt_2 = 4.352
        np.testing.assert_allclose(
            gjt,
            [
                [np.inf, gjt_1, gjt_2],
                [gjt_1, np.inf, gjt_2],
                [gjt_2, gjt_2, np.inf],
            ],
            atol=1e-3,
        )


class TestGJTCalculator:
    @pytest.fixture
    def state(self):
        return TrackedState()

    @pytest.fixture
    def init_data(self, railway_network_name, railway_network_for_traffic, global_schema):
        data_format = EntityInitDataFormat(global_schema)
        return {railway_network_name: data_format.load_json(railway_network_for_traffic)["data"]}

    @pytest.fixture
    def travel_time(
        self,
    ):
        return UniformAttribute([1, 1, 1, 1, 1], data_type=DataType(float))

    @pytest.fixture
    def passenger_flow(self):
        return UniformAttribute(np.array([1.0, 1, 2, 0, 0]), DataType(float))

    @pytest.fixture
    def frequency(self):
        return CSRAttribute([[0, 1, 1], [1, 0, 1], [1, 1, 0]], DataType(float, csr=True))

    @pytest.fixture
    def train_capacity(self):
        return UniformAttribute(np.ones((3,), dtype=float), DataType(float))

    @pytest.fixture
    def network(self, state, init_data, railway_network_name):
        entities = Network.register_required_attributes(
            state, railway_network_name, "track_segment_entities"
        )
        state.receive_update(init_data)
        return Network(**entities)

    @pytest.fixture
    def crowdedness_mock(self):
        with mock.patch(
            GJTCalculator.__module__ + ".crowdedness",
            mock.Mock(side_effect=lambda lf: np.asarray(lf)),
        ):
            yield

    @pytest.fixture
    def calculator(
        self, network, travel_time, passenger_flow, frequency, train_capacity, crowdedness_mock
    ) -> GJTCalculator:
        rv = GJTCalculator(
            network=network,
            travel_time=travel_time,
            passenger_flow=passenger_flow,
            frequency=frequency,
            train_capacity=train_capacity,
        )
        rv.update_travel_time()

        return rv

    def expected_gjt(self, avg_flow, frequency=1, travel_time=2, train_capacity=1):
        return avg_flow / (frequency * train_capacity) * travel_time + 1.5 / (2 * frequency)

    def test_calculate_gjt(self, calculator):
        gjt = calculator.gjt()
        avg_flow_1 = 1
        avg_flow_2 = 1.5
        gjt_1 = self.expected_gjt(avg_flow_1)
        gjt_2 = self.expected_gjt(avg_flow_2)
        np.testing.assert_allclose(
            gjt,
            [
                [np.inf, gjt_1, gjt_2],
                [gjt_1, np.inf, gjt_2],
                [gjt_2, gjt_2, np.inf],
            ],
            atol=1e-3,
        )

    @pytest.mark.parametrize(
        "attribute, new_value, is_csr",
        [
            ("frequency", 2, True),
            ("travel_time", 2, False),
            ("train_capacity", 2, False),
        ],
    )
    def test_change_frequency(self, calculator, request, attribute, new_value, is_csr):
        obj = request.getfixturevalue(attribute)
        if is_csr:
            obj.csr.data = obj.csr.data * new_value
        else:
            obj[:] = obj.array * new_value

        avg_flow_1 = 1
        avg_flow_2 = 1.5
        gjt_1 = self.expected_gjt(avg_flow_1, **{attribute: new_value})
        gjt_2 = self.expected_gjt(avg_flow_2, **{attribute: new_value})
        gjt = calculator.gjt()
        np.testing.assert_allclose(
            gjt,
            np.array(
                [
                    [np.inf, gjt_1, gjt_2],
                    [gjt_1, np.inf, gjt_2],
                    [gjt_2, gjt_2, np.inf],
                ]
            ),
            atol=1e-3,
        )


def test_crowdedness():
    A = 0.8914
    B = 0.4643

    def expected(num):
        return A * num + B

    np.testing.assert_allclose(
        crowdedness([0.1, 0.5, 1, 2, 3]),
        [expected(x) for x in [0.5, 0.5, 1, 2, 3]],
        atol=1e-4,
    )


def test_model_config_schema(model_config):
    schema = json.loads(MODEL_CONFIG_SCHEMA_PATH.read_text())
    assert model_config_validator(schema)(model_config)
