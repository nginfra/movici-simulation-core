import numpy as np
import pytest

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.schema import DataType, infer_data_type_from_array
from movici_simulation_core.models.udf_model.compiler import (
    compile_func,
    infer_result_type,
    parse,
    tokenize,
)
from movici_simulation_core.models.udf_model.result_type import (
    ResultType,
    Shape,
    combine,
    combine_shape,
    promote,
)

UNIFORM_FLOAT = ResultType(float, Shape.UNIFORM)
UNIFORM_INT = ResultType(int, Shape.UNIFORM)
UNIFORM_BOOL = ResultType(bool, Shape.UNIFORM)
CSR_FLOAT = ResultType(float, Shape.CSR)
CSR_INT = ResultType(int, Shape.CSR)


ROW_PTR = np.array([0, 2, 3, 3])


@pytest.fixture
def values():
    """Actual attribute data for every name in `variables`, of exactly the types declared there"""
    return {
        "a": np.array([1.0, 2.0, 3.0]),
        "n": np.array([1, 2, 3], dtype="<i4"),
        "flag": np.array([True, False, True]),
        "csr": TrackedCSRArray(np.array([1.0, 2.0, 3.0]), ROW_PTR),
        "csr_n": TrackedCSRArray(np.array([1, 2, 3], dtype="<i4"), ROW_PTR),
        "csr_flag": TrackedCSRArray(np.array([True, True, False]), ROW_PTR),
        "two_d": np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]),
        "csr_two_d": TrackedCSRArray(np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]), ROW_PTR),
    }


@pytest.fixture
def variables():
    return {
        "a": UNIFORM_FLOAT,
        "n": UNIFORM_INT,
        "flag": UNIFORM_BOOL,
        "csr": CSR_FLOAT,
        "csr_n": CSR_INT,
        "csr_flag": ResultType(bool, Shape.CSR),
        "two_d": ResultType(float, Shape.UNIFORM, (2,)),
        "csr_two_d": ResultType(float, Shape.CSR, (2,)),
    }


@pytest.mark.parametrize(
    "py_types, expected",
    [
        ((bool, int), int),
        ((int, float), float),
        ((bool, bool), bool),
        # an operand of unknown type does not make the whole expression unknown
        ((None, int), int),
        ((None, None), None),
        ((), None),
    ],
)
def test_promote(py_types, expected):
    assert promote(*py_types) is expected


@pytest.mark.parametrize(
    "shapes, expected",
    [
        ((Shape.SCALAR, Shape.SCALAR), Shape.SCALAR),
        ((Shape.SCALAR, Shape.UNIFORM), Shape.UNIFORM),
        ((Shape.UNIFORM, Shape.CSR), Shape.CSR),
        ((Shape.SCALAR, Shape.CSR), Shape.CSR),
    ],
)
def test_combine_shape(shapes, expected):
    assert combine_shape(*shapes) is expected


def test_combine_keeps_the_unit_shape_of_its_operands():
    result = combine(ResultType(float, Shape.UNIFORM, (2,)), UNIFORM_FLOAT)
    assert result.unit_shape == (2,)


@pytest.mark.parametrize(
    "data_type",
    [
        DataType(float),
        DataType(int, csr=True),
        DataType(float, (2,)),
        DataType(float, (2,), csr=True),
        DataType(bool),
    ],
)
def test_result_type_round_trips_a_data_type(data_type):
    assert ResultType.from_data_type(data_type).as_data_type() == data_type


INFERENCE_CASES = [
    # literals
    ("1", ResultType(float, Shape.SCALAR)),
    ("true", ResultType(bool, Shape.SCALAR)),
    ("1+2", ResultType(float, Shape.SCALAR)),
    # arithmetic promotes its operands
    ("n+n", UNIFORM_INT),
    ("n+a", UNIFORM_FLOAT),
    ("flag+n", UNIFORM_INT),
    # true division always produces floating point values
    ("n/n", UNIFORM_FLOAT),
    # comparison and the boolean operators always produce booleans
    ("a<n", UNIFORM_BOOL),
    ("flag and flag", UNIFORM_BOOL),
    ("not flag", UNIFORM_BOOL),
    # a csr operand dominates a uniform one, which dominates a scalar
    # a csr operand determines the shape whichever side of the operator it is on: there is no
    # meaningful way to reduce it to one value per entity, so the result stays csr
    ("csr+a", CSR_FLOAT),
    ("a+csr", CSR_FLOAT),
    ("2*csr", CSR_FLOAT),
    ("csr-2", CSR_FLOAT),
    # every numeric literal is compiled as a float, so an integer attribute scaled by a
    # literal widens. Keeping it an integer would need separate int and float literal nodes
    ("csr_n*2", CSR_FLOAT),
    ("2*a", UNIFORM_FLOAT),
    ("csr<a", ResultType(bool, Shape.CSR)),
    ("a<csr", ResultType(bool, Shape.CSR)),
    ("1+true", ResultType(float, Shape.SCALAR)),
    # a row wise reduction of a single argument turns a csr value into a uniform one, leaves
    # a uniform one uniform and a scalar scalar
    ("sum(csr)", UNIFORM_FLOAT),
    ("sum(csr_n)", UNIFORM_INT),
    ("sum(a)", UNIFORM_FLOAT),
    ("sum(2)", ResultType(float, Shape.SCALAR)),
    ("min(csr)", UNIFORM_FLOAT),
    ("min(a)", UNIFORM_FLOAT),
    ("max(csr_n)", UNIFORM_INT),
    # summing booleans counts them, taking their extreme does not
    ("sum(flag)", UNIFORM_INT),
    ("sum(csr_flag)", UNIFORM_INT),
    ("min(flag)", UNIFORM_BOOL),
    ("max(flag)", UNIFORM_BOOL),
    # with several arguments they are elementwise, so a csr argument dominates
    ("min(csr, a)", CSR_FLOAT),
    ("min(a, csr)", CSR_FLOAT),
    ("min(a, 2)", UNIFORM_FLOAT),
    ("max(n, 2)", UNIFORM_FLOAT),
    ("min(csr, a, 2)", CSR_FLOAT),
    # a reduction collapses a unit shape along with the values it reduces
    ("sum(two_d)", UNIFORM_FLOAT),
    ("min(two_d)", UNIFORM_FLOAT),
    ("sum(csr_two_d)", UNIFORM_FLOAT),
    ("min(csr_two_d)", UNIFORM_FLOAT),
    # but an elementwise operation keeps it
    ("two_d+1", ResultType(float, Shape.UNIFORM, (2,))),
    ("csr_two_d*2", ResultType(float, Shape.CSR, (2,))),
    # functions
    ("sqrt(n)", UNIFORM_FLOAT),
    ("abs(n)", UNIFORM_INT),
    ("sign(n)", UNIFORM_INT),
    # `default` fills an attribute in place, so it keeps that attribute's type even though
    # the literal it is given is a float
    ("default(n, 0)", UNIFORM_INT),
    ("default(a, 0)", UNIFORM_FLOAT),
    ("default(csr, 0)", CSR_FLOAT),
    # `if` takes its type from both branches, so that it does not truncate either of them
    ("if(flag, n, a)", UNIFORM_FLOAT),
    ("if(flag, n, n)", UNIFORM_INT),
    ("clip(n, 0, 1)", UNIFORM_FLOAT),
    # group reductions produce a single value for the whole entity group
    ("total(a)", ResultType(float, Shape.SCALAR)),
    ("total(n)", ResultType(int, Shape.SCALAR)),
    # summing booleans counts them
    ("total(flag)", ResultType(int, Shape.SCALAR)),
    ("total(csr)", ResultType(float, Shape.SCALAR)),
    ("mean(n)", ResultType(float, Shape.SCALAR)),
    ("count(a)", ResultType(int, Shape.SCALAR)),
    ("any(flag)", ResultType(bool, Shape.SCALAR)),
    ("all(flag)", ResultType(bool, Shape.SCALAR)),
    # a scalar is broadcast back over the entities
    ("a/total(a)", UNIFORM_FLOAT),
    ("a>mean(a)", UNIFORM_BOOL),
    ("csr/total(csr)", CSR_FLOAT),
    # a group reduction collapses whatever shape it is given, scalars included
    ("total(2)", ResultType(float, Shape.SCALAR)),
    ("mean(2)", ResultType(float, Shape.SCALAR)),
    ("count(2)", ResultType(int, Shape.SCALAR)),
    ("any(true)", ResultType(bool, Shape.SCALAR)),
    ("total(two_d)", ResultType(float, Shape.SCALAR)),
    ("total(csr_two_d)", ResultType(float, Shape.SCALAR)),
]
"""Expressions and the result type they are expected to produce. `test_infer_result_type` checks
that inference says so, `test_inference_matches_the_runtime` checks that evaluating the expression
really does produce it, so that the two can never drift apart.
"""


@pytest.mark.parametrize("expression, expected", INFERENCE_CASES)
def test_infer_result_type(expression, expected, variables):
    assert infer_result_type(parse(tokenize(expression)), variables) == expected


def observed_result_type(value) -> ResultType:
    """The result type an evaluated expression actually produced"""
    if isinstance(value, TrackedCSRArray):
        return ResultType(
            infer_data_type_from_array(value.data).py_type, Shape.CSR, value.data.shape[1:]
        )
    array = np.asarray(value)
    py_type = infer_data_type_from_array(array).py_type
    if array.ndim == 0:
        return ResultType(py_type, Shape.SCALAR)
    return ResultType(py_type, Shape.UNIFORM, array.shape[1:])


@pytest.mark.parametrize("expression", [case[0] for case in INFERENCE_CASES])
def test_inference_matches_the_runtime(expression, values):
    """Inference is only worth having if it agrees with what evaluating actually produces. It
    decides the data type of a udf's output attribute, so where the two disagree an expression
    publishes values of a type its attribute was not built for.
    """
    expected = dict(INFERENCE_CASES)[expression]

    assert observed_result_type(compile_func(parse(tokenize(expression)))(values)) == expected


def test_unknown_name_is_an_error(variables):
    with pytest.raises(NameError, match="'typo' is not one of the inputs"):
        infer_result_type(parse(tokenize("a+typo")), variables)


def test_unknown_function_is_an_error(variables):
    with pytest.raises(NameError, match="nope is not a valid function name"):
        infer_result_type(parse(tokenize("nope(a)")), variables)
