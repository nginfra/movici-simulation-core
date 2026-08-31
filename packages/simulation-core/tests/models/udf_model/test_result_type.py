import pytest

from movici_simulation_core.core.schema import DataType
from movici_simulation_core.models.udf_model.compiler import (
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


@pytest.fixture
def variables():
    return {
        "a": UNIFORM_FLOAT,
        "n": UNIFORM_INT,
        "flag": UNIFORM_BOOL,
        "csr": CSR_FLOAT,
        "csr_n": CSR_INT,
        "two_d": ResultType(float, Shape.UNIFORM, (2,)),
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
    [DataType(float), DataType(int, csr=True), DataType(float, (2,)), DataType(bool)],
)
def test_result_type_round_trips_a_data_type(data_type):
    assert ResultType.from_data_type(data_type).as_data_type() == data_type


@pytest.mark.parametrize(
    "expression, expected",
    [
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
        ("csr+a", CSR_FLOAT),
        ("csr_n*2", CSR_FLOAT),
        ("2*a", UNIFORM_FLOAT),
        ("csr<a", ResultType(bool, Shape.CSR)),
        # row wise reductions turn a csr value into a uniform one
        ("sum(csr)", UNIFORM_FLOAT),
        ("sum(csr_n)", UNIFORM_INT),
        ("min(csr)", UNIFORM_FLOAT),
        ("min(csr, a)", CSR_FLOAT),
        # and reduce away a unit shape
        ("sum(two_d)", UNIFORM_FLOAT),
        # functions
        ("sqrt(n)", UNIFORM_FLOAT),
        ("abs(n)", UNIFORM_INT),
        ("sign(n)", UNIFORM_INT),
        ("default(n, 0)", UNIFORM_INT),
        ("if(flag, n, a)", UNIFORM_INT),
        ("clip(n, 0, 1)", UNIFORM_FLOAT),
    ],
)
def test_infer_result_type(expression, expected, variables):
    assert infer_result_type(parse(tokenize(expression)), variables) == expected


def test_unknown_name_is_an_error(variables):
    with pytest.raises(NameError, match="'typo' is not one of the inputs"):
        infer_result_type(parse(tokenize("a+typo")), variables)


def test_unknown_function_is_an_error(variables):
    with pytest.raises(NameError, match="nope is not a valid function name"):
        infer_result_type(parse(tokenize("nope(a)")), variables)
