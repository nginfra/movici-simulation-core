import numpy as np
import pytest

from movici_simulation_core.models.udf_model.compiler import (
    BinOp,
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
    ],
)
def test_parser(string, expected):
    assert get_ast(string) == expected


@pytest.mark.parametrize(
    "string", [",", "(", "(()", "max(,)", "1++2", "max()a", "a==b==c", "a<b<c"]
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
    ],
)
def test_func(string, expected):
    variables = {"a": 1, "b": 2, "c": 3}
    tree = get_ast(string)
    assert compile_func(tree)(variables) == expected


@pytest.mark.parametrize(
    "string, variables,expected",
    [
        ("a+b", {"a": np.array([1, 2]), "b": np.array([3.0, 4.0])}, [4.0, 6.0]),
        ("sum(a+1)", {"a": np.array([[1, 2], [3, 4]])}, [5, 9]),
        ("a==b", {"a": np.array([1, 2]), "b": np.array([1, 1])}, [True, False]),
    ],
)
def test_with_arrays(string, variables, expected):
    np.testing.assert_array_equal(compile_func(get_ast(string))(variables), expected)
