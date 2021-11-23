from unittest.mock import Mock

import numpy as np
import pytest

from movici_simulation_core.core.schema import DataType
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.index import Index
from movici_simulation_core.data_tracker.property import UniformProperty, CSRProperty
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.common.entities import GeometryEntity
from movici_simulation_core.models.traffic_demand_calculation.global_contributors import (
    GlobalElasticityParameter,
    ScalarParameter,
)
from movici_simulation_core.models.traffic_demand_calculation.common import (
    DemandEstimation,
    LocalMapper,
)
from movici_simulation_core.models.traffic_demand_calculation.local_contributors import (
    get_ratio_for_node,
    calculate_localized_contribution_1d,
    LocalParameterInfo,
    NearestValue,
    RouteCostFactor,
    Investment,
    InvestmentContributor,
)
from movici_simulation_core.testing.road_network import generate_road_network
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings


@pytest.fixture
def simple_demand():
    return np.array([[0, 1], [2, 0]], dtype=float)


@pytest.fixture
def simple_network():
    return generate_road_network(nodes=[(0, 0), (0, 1)], links=[(0, 1)])


@pytest.mark.parametrize(
    "curr, prev, elasticity, factor, expected",
    [
        (1, 1, 1, 1, 1),
        (3, 1, 1, 1, (3 / 1) ** (2 * 1)),
        (2, 1, 2, 1, (2 / 1) ** (2 * 2)),
        (1, 2, 2, 1, (1 / 2) ** (2 * 2)),
        (1, 2, 2, 5, 5 * (1 / 2) ** (2 * 2)),
        (0, 0, 2, 1, 1),
        (2, 1, 0, 1, 1),
    ],
)
def test_global_elasticiy_parameter(prev, curr, elasticity, factor, expected):
    tape = {"param": curr}
    calc = GlobalElasticityParameter("param", tape, elasticity)
    calc.curr = prev
    assert calc.update_factor(factor) == expected


def test_global_elasticity_captures_current_value():
    tape = {"param": 42}
    calc = GlobalElasticityParameter("param", tape, 1)
    calc.curr = 1
    calc.update_factor(1)
    assert calc.curr == 42


@pytest.mark.parametrize(
    "curr_factor, value, expected",
    [
        (1, 1, 1),
        (2, 1, 2),
        (2, 2, 4),
    ],
)
def test_scalar_parameter(curr_factor, value, expected):
    tape = {"param": value}
    calc = ScalarParameter("param", tape)
    assert calc.update_factor(curr_factor) == expected


class TestNearestValueContributor:
    @pytest.fixture
    def property(self):
        return UniformProperty(np.arange(1, 6, dtype=float), data_type=DataType(float))

    @pytest.fixture
    def mapping_indices(self):
        return [0, 1]

    @pytest.fixture
    def mapper(self, mapping_indices):
        mock = Mock(LocalMapper)
        mock.get_nearest.return_value = np.asarray(mapping_indices)
        return mock

    @pytest.fixture
    def parameter_info(self, property):
        return LocalParameterInfo(
            target_dataset="dataset",
            target_entity_group="entities",
            target_geometry="line",
            target_property=property,
            elasticity=2,
        )

    @pytest.fixture
    def state(self):
        return TrackedState()

    @pytest.fixture
    def calculator(self, state, parameter_info, mapper):
        rv = NearestValue(parameter_info)
        rv.setup(state)
        rv.initialize(mapper)
        return rv

    def test_setup(self, calculator, state):
        assert isinstance(
            state.properties["dataset"]["entities"][("shape_properties", "linestring_2d")],
            CSRProperty,
        )
        assert isinstance(calculator._target_entity, GeometryEntity)

    def test_initialize(self, calculator, mapper):
        np.testing.assert_array_equal(calculator._indices, [0, 1])

    def test_update_demand_first_time_doesnt_change_demand(self, calculator):
        input_matrix = np.array([[0, 1], [1, 0]])
        result = calculator.update_demand(input_matrix)
        np.testing.assert_array_equal(result, input_matrix)

    @pytest.mark.parametrize("force", [True, False])
    def test_demand_stays_equal_on_no_change_property(self, calculator, force):
        input_matrix = np.array([[0, 1], [1, 0]])
        calculator.update_demand(input_matrix)
        result = calculator.update_demand(input_matrix, force_update=force)
        np.testing.assert_array_equal(result, input_matrix)

    def test_update_demand(self, calculator, property):
        input_matrix = np.array([[0, 1], [1, 0]])
        calculator.update_demand(input_matrix)
        property[:] = [4, 4, 4, 4, 4]
        result = calculator.update_demand(input_matrix)
        exp = (4 / 1 * 4 / 2) ** 2
        np.testing.assert_array_equal(
            result,
            [
                [0, exp],
                [exp, 0],
            ],
        )


def test_calculate_localized_multiplication_factor():
    values = np.array([1, 2, 3])
    old_values = np.array([2, 3, 4])
    indices = np.array([0, 1, 2])
    elasticity = 2
    result = calculate_localized_contribution_1d(values, old_values, indices, elasticity)

    exp = (values / old_values) ** elasticity  # [0.25000, 0.44444, 0.56250]

    # result should be a matrix where every value at ij = exp[i]*exp[j]. We can achieve
    # this by calculating the outer product of exp x exp
    np.testing.assert_array_equal(result, np.outer(exp, exp))


@pytest.mark.parametrize("node_i, expected", zip(range(5), [1 / 2, 2 / 3, 3 / 4, 1, 1]))
def test_get_ratio_for_node(node_i, expected):
    values = np.array([1, 2, 3, 0, 5])
    old_values = np.array([2, 3, 4, 5, 0])
    indices = np.arange(len(values))
    assert get_ratio_for_node(node_i, values, old_values, indices) == expected


class TestRouteCostFactor:
    @pytest.fixture
    def state(self):
        return TrackedState()

    @pytest.fixture
    def property(self, state, road_network_name):
        return UniformProperty(np.ones((4,)), DataType(float))

    @pytest.fixture
    def mapping_indices(self):
        return np.array([2, 2, 0])

    @pytest.fixture
    def mapper(self, mapping_indices):
        mock = Mock(LocalMapper)
        mock.get_nearest.return_value = np.asarray(mapping_indices)
        return mock

    @pytest.fixture
    def parameter_info(self, road_network_name, property):
        return LocalParameterInfo(
            target_dataset=road_network_name,
            target_entity_group="road_segment_entities",
            target_geometry="line",
            target_property=property,
            elasticity=2,
        )

    @pytest.fixture
    def update_data(self, road_network_name, road_network_for_traffic, global_schema):
        data_format = EntityInitDataFormat(global_schema)
        return {road_network_name: data_format.load_json(road_network_for_traffic)["data"]}

    @pytest.fixture
    def calculator(
        self, road_network_name, update_data, parameter_info, state, mapper
    ) -> RouteCostFactor:
        calc = RouteCostFactor(parameter_info)
        calc.setup(state, Settings())

        state.receive_update(update_data)
        calc.initialize(mapper)
        return calc

    @pytest.mark.parametrize("input_val", [2, 3])
    def test_calculate_values(self, calculator, property, input_val):
        base_path_travel_costs = np.array([[0, 0, 2], [0, 0, 2], [1, 1, 0]])
        property[:] = input_val
        assert np.array_equal(calculator.calculate_values(), base_path_travel_costs * input_val)

    def test_update_demand(self, calculator, property):
        base_costs = np.array([[0, 0, 2], [0, 0, 2], [1, 1, 0]])
        input_matrix = np.ones_like(base_costs, dtype=float)

        calculator.update_demand(input_matrix)
        property[:] = 2
        result = calculator.update_demand(input_matrix)

        expected = np.ones_like(input_matrix)
        expected[np.nonzero(base_costs)] = 2 ** 2  # (2*bc/bc) ** elasticity
        np.testing.assert_array_equal(result, expected)


def test_demand_estimation_global_parameters_update_demand(simple_demand):
    class FakeCSVTape(dict, CsvTape):
        def has_update(self):
            return True

    tape = FakeCSVTape(a=0.5, b=3)
    estimator = DemandEstimation(
        global_params=[
            GlobalElasticityParameter("a", tape, 2),
            ScalarParameter("b", tape),
        ]
    )
    estimator.global_params[0].curr = 1
    expected_factor = (0.5 / 1) ** (2 * 2) * 3
    updated = estimator.update(simple_demand, moment=Moment(0))
    np.testing.assert_array_equal(updated, simple_demand * expected_factor)


class TestInvestmentContributor:
    @pytest.fixture
    def demand_node_index(self):
        return Index([2, 3, 4])

    @pytest.fixture
    def investments(self):
        return [Investment(0, 2, 2), Investment(2, 3, 3)]

    @pytest.fixture
    def contributor(self, investments, demand_node_index):
        return InvestmentContributor([Investment(*tup) for tup in investments], demand_node_index)

    @pytest.mark.parametrize(
        "investments, seconds, expected, exp_remaining",
        [
            (
                [],
                0,
                [
                    [1, 1, 1],
                    [1, 1, 1],
                    [1, 1, 1],
                ],
                0,
            ),
            (
                [(1, 2, 2)],
                0,
                [
                    [1, 1, 1],
                    [1, 1, 1],
                    [1, 1, 1],
                ],
                1,
            ),
            (
                [(0, 2, 2)],
                0,
                [
                    [2, 2, 2],
                    [2, 1, 1],
                    [2, 1, 1],
                ],
                0,
            ),
            (
                [(0, 2, 2), (1, 3, 3)],
                1,
                [
                    [2, 2 * 3, 2],
                    [2 * 3, 3, 3],
                    [2, 3, 1],
                ],
                0,
            ),
        ],
    )
    def test_update_demand(self, contributor, investments, seconds, expected, exp_remaining):
        matrix = np.ones((3, 3), dtype=float)
        result = contributor.update_demand(matrix, moment=Moment.from_seconds(seconds))
        np.testing.assert_array_equal(result, expected)
        assert len(contributor.investments) == exp_remaining
