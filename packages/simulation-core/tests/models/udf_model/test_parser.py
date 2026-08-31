import numpy as np
import pytest

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.models.udf_model.compiler import (
    BinOp,
    Bool,
    Func,
    Num,
    Var,
    compile_func,
    get_vars,
    parse,
    tokenize,
)


def get_ast(string):
    return parse(tokenize((string)))


@pytest.mark.parametrize(
    "string, expected",
    [
        ("+", [("+", "+")]),
        ("aa-bb", [("name", "aa"), ("-", "-"), ("name", "bb")]),
        (
            "(a  * b)/c",
            [
                ("(", "("),
                ("name", "a"),
                ("ws", "  "),
                ("*", "*"),
                ("ws", " "),
                ("name", "b"),
                (")", ")"),
                ("/", "/"),
                ("name", "c"),
            ],
        ),
        ("2.3", [("num", "2.3")]),
        ("my_var", [("name", "my_var")]),
        ("1+2.3", [("num", "1"), ("+", "+"), ("num", "2.3")]),
        ("a==b", [("name", "a"), ("==", "=="), ("name", "b")]),
        ("a!=b", [("name", "a"), ("!=", "!="), ("name", "b")]),
        ("a<b", [("name", "a"), ("<", "<"), ("name", "b")]),
        ("attr_1", [("name", "attr_1")]),
        ("1e5", [("num", "1e5")]),
        ("1.5e-3", [("num", "1.5e-3")]),
        ("a**b", [("name", "a"), ("**", "**"), ("name", "b")]),
        ("a%b", [("name", "a"), ("%", "%"), ("name", "b")]),
        ("a and b", [("name", "a"), ("ws", " "), ("and", "and"), ("ws", " "), ("name", "b")]),
        ("a&&b", [("name", "a"), ("and", "&&"), ("name", "b")]),
        ("a||b", [("name", "a"), ("or", "||"), ("name", "b")]),
        ("!a", [("not", "!"), ("name", "a")]),
        ("true", [("bool", "true")]),
        # names that merely start with a keyword are not keywords
        ("android", [("name", "android")]),
        ("nothing", [("name", "nothing")]),
        ("order", [("name", "order")]),
        ("true_value", [("name", "true_value")]),
    ],
)
def test_tokenize(string, expected):
    assert list(tokenize(string)) == expected


@pytest.mark.parametrize(
    "string,expected",
    [
        ("1+2", BinOp("+", Num("1"), Num("2"))),
        ("1 + 2", BinOp("+", Num("1"), Num("2"))),
        ("1+2+3", BinOp("+", BinOp("+", Num("1"), Num("2")), Num("3"))),
        ("(1+2)", BinOp("+", Num("1"), Num("2"))),
        ("1*2", BinOp("*", Num("1"), Num("2"))),
        ("1*2+3", BinOp("+", BinOp("*", Num("1"), Num("2")), Num("3"))),
        ("1*(2+3)", BinOp("*", Num("1"), BinOp("+", Num("2"), Num("3")))),
        ("-a", BinOp("-", Num("0"), Var("a"))),
        ("a==b", BinOp("==", Var("a"), Var("b"))),
        ("a*b==c", BinOp("==", BinOp("*", Var("a"), Var("b")), Var("c"))),
        ("a+b==c+d", BinOp("==", BinOp("+", Var("a"), Var("b")), BinOp("+", Var("c"), Var("d")))),
        ("a*(b==c)", BinOp("*", Var("a"), BinOp("==", Var("b"), Var("c")))),
        ("max(a)", Func("max", (Var("a"),))),
        ("max(a+2)", Func("max", (BinOp("+", Var("a"), Num("2")),))),
        ("max(a+2, b)", Func("max", (BinOp("+", Var("a"), Num("2")), Var("b")))),
        ("max()", Func("max", ())),
        ("if(a<b, a, b)", Func("if", (BinOp("<", Var("a"), Var("b")), Var("a"), Var("b")))),
        ("a**b", BinOp("**", Var("a"), Var("b"))),
        # exponentiation is right associative and binds tighter than unary minus
        ("2**3**4", BinOp("**", Num("2"), BinOp("**", Num("3"), Num("4")))),
        ("-a**2", BinOp("-", Num("0"), BinOp("**", Var("a"), Num("2")))),
        ("a**-2", BinOp("**", Var("a"), BinOp("-", Num("0"), Num("2")))),
        ("a%b", BinOp("%", Var("a"), Var("b"))),
        # a unary sign is allowed anywhere an atom is
        ("a*-b", BinOp("*", Var("a"), BinOp("-", Num("0"), Var("b")))),
        ("true", Bool("true")),
        ("false", Bool("false")),
        ("not a", Func("not", (Var("a"),))),
        ("!a", Func("not", (Var("a"),))),
        ("a and b", BinOp("and", Var("a"), Var("b"))),
        ("a && b", BinOp("and", Var("a"), Var("b"))),
        ("a or b", BinOp("or", Var("a"), Var("b"))),
        ("a || b", BinOp("or", Var("a"), Var("b"))),
        # `and` binds tighter than `or`, comparison binds tighter than both
        ("a or b and c", BinOp("or", Var("a"), BinOp("and", Var("b"), Var("c")))),
        ("a<b and c", BinOp("and", BinOp("<", Var("a"), Var("b")), Var("c"))),
        ("not a<b", Func("not", (BinOp("<", Var("a"), Var("b")),))),
    ],
)
def test_parser(string, expected):
    assert get_ast(string) == expected


@pytest.mark.parametrize(
    "string", [",", "(", "(()", "max(,)", "max()a", "a==b==c", "a<b<c", "a**", "1 2", "and a"]
)
def test_invalid_strings(string):
    with pytest.raises(SyntaxError):
        get_ast(string)


@pytest.mark.parametrize("string,expected", [("a+b", {"a", "b"})])
def test_get_vars(string, expected):
    assert get_vars(get_ast(string)) == expected


@pytest.mark.parametrize(
    "string,expected",
    [
        ("a", 1),
        ("a", 1),
        ("1.2", 1.2),
        ("a+b", 3),
        ("2*(a+b)", 6),
        ("-2*(a+b)", -6),
        ("sum(a)", 1),
        ("a==b", False),
        ("a!=b", True),
        ("a<b", True),
        ("2**3", 8),
        ("2**3**2", 512),
        ("-2**2", -4),
        ("7%3", 1),
        ("2*-3", -6),
        ("1++2", 3),
        ("1e3", 1000),
        ("1.5e-1", 0.15),
        ("true", True),
        ("false", False),
        ("a<b and b<c", True),
        ("a<b and b>c", False),
        ("a>b or b<c", True),
        ("not a<b", False),
        ("!(a<b)", False),
    ],
)
def test_func(string, expected):
    variables = {"a": 1, "b": 2, "c": 3}
    tree = get_ast(string)
    assert compile_func(tree)(variables) == expected


def test_identifiers_may_contain_digits():
    assert compile_func(get_ast("attr_1+attr_2"))({"attr_1": 1, "attr_2": 2}) == 3


@pytest.mark.parametrize(
    "string, expected",
    [
        # division by zero yields an undefined value rather than an infinity
        ("a/0", np.nan),
        ("0/0", np.nan),
        # undefined operands propagate into the result
        ("undef/a", np.nan),
        ("undef*a", np.nan),
        ("undef+a", np.nan),
        ("log(0)", np.nan),
    ],
)
def test_undefined_propagation(string, expected):
    variables = {"a": np.array([2.0]), "undef": np.array([np.nan])}
    np.testing.assert_array_equal(compile_func(get_ast(string))(variables), [expected])


@pytest.mark.parametrize(
    "string, variables,expected",
    [
        ("a+b", {"a": np.array([1, 2]), "b": np.array([3.0, 4.0])}, [4.0, 6.0]),
        ("sum(a+1)", {"a": np.array([[1, 2], [3, 4]])}, [5, 9]),
        ("a==b", {"a": np.array([1, 2]), "b": np.array([1, 1])}, [True, False]),
        ("a**2", {"a": np.array([2.0, 3.0])}, [4.0, 9.0]),
        ("a%2", {"a": np.array([3.0, 4.0])}, [1.0, 0.0]),
        ("sqrt(a)", {"a": np.array([4.0, 9.0])}, [2.0, 3.0]),
        ("abs(-a)", {"a": np.array([1.0, -2.0])}, [1.0, 2.0]),
        ("clip(a, 1, 2)", {"a": np.array([0.0, 3.0])}, [1.0, 2.0]),
        ("not a", {"a": np.array([True, False])}, [False, True]),
        (
            "a and b",
            {"a": np.array([True, True]), "b": np.array([True, False])},
            [True, False],
        ),
        (
            "a or b",
            {"a": np.array([True, False]), "b": np.array([False, False])},
            [True, False],
        ),
    ],
)
def test_with_arrays(string, variables, expected):
    np.testing.assert_array_equal(compile_func(get_ast(string))(variables), expected)


@pytest.mark.parametrize(
    "string, expected",
    [
        # a scalar or uniform operand on either side of a csr array
        ("1+csr", [11.0, 12.0, 21.0, 23.0]),
        ("csr+1", [11.0, 12.0, 21.0, 23.0]),
        ("2*csr", [20.0, 22.0, 40.0, 44.0]),
        ("-csr", [-10.0, -11.0, -20.0, -22.0]),
        ("220/csr", [22.0, 20.0, 11.0, 10.0]),
        ("csr/a", [5.0, 5.5, 5.0, 5.5]),
        ("csr**2", [100.0, 121.0, 400.0, 484.0]),
        ("sqrt(csr)+0", [10.0**0.5 + 0, 11.0**0.5, 20.0**0.5, 22.0**0.5]),
    ],
)
def test_with_csr_arrays(string, expected):
    variables = {
        "csr": TrackedCSRArray(np.array([10.0, 11.0, 20.0, 22.0]), np.array([0, 2, 4])),
        "a": np.array([2.0, 4.0]),
    }
    result = compile_func(get_ast(string))(variables)
    assert isinstance(result, TrackedCSRArray)
    np.testing.assert_allclose(result.data, expected)


def test_csr_comparison_yields_booleans():
    variables = {
        "csr": TrackedCSRArray(np.array([10.0, 11.0, 20.0, 22.0]), np.array([0, 2, 4])),
        "a": np.array([11.0, 20.0]),
    }
    result = compile_func(get_ast("csr<a"))(variables)
    assert result.data.dtype == bool
    np.testing.assert_array_equal(result.data, [True, False, False, False])
