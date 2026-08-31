"""Compiler for the expressions used by the
:class:`~movici_simulation_core.models.udf_model.udf_model.UDFModel`.

An expression is tokenized, parsed into an abstract syntax tree and then compiled into a tree of
closures over numpy operations. Evaluating the result is vectorized over the entities of an entity
group: every name in an expression refers to a whole attribute, not to a single entity.

**Grammar.** Operators, from lowest to highest precedence::

    or   ||                      elementwise disjunction
    and  &&                      elementwise conjunction
    not  !                       elementwise negation
    ==  !=  <  <=  >  >=         comparison, may not be chained
    +  -                         addition, subtraction
    *  /  %                      multiplication, division, remainder
    +  -                         unary sign
    **                           exponentiation, right associative

Operands are numbers (``1``, ``2.5``, ``1.5e-3``), the booleans ``true`` and ``false``, attribute
names (which may contain digits, eg. ``co2_2030``), function calls and parenthesized expressions.

**Values.** Every operator and function accepts uniform attributes, csr attributes and scalars
in any combination. A scalar or uniform operand is broadcast along the rows of a csr operand, so
``csr * 2`` and ``2 * csr`` both scale every value, while ``csr * uniform`` multiplies each row by
the value belonging to that entity.

**Reductions.** ``sum``, ``min`` and ``max`` reduce the values of each entity separately, turning
a csr attribute into a uniform one. ``total``, ``mean``, ``count``, ``any`` and ``all`` instead
reduce the whole entity group to a single number, which is then broadcast back over the entities,
so ``flow / total(flow)`` gives each entity its share of the whole. A group reduction skips
undefined values rather than being poisoned by them.

Undefined values propagate: an expression over an undefined input results in an undefined value.
Arithmetic that cannot produce a finite number (division by zero, the logarithm of zero) also
results in an undefined value, since a Movici dataset has no representation for infinity. Use the
``default`` function to substitute undefined values with something else.
"""

from __future__ import annotations

import dataclasses
import functools
import operator
import re
import typing as t

from movici_simulation_core.models.udf_model import functions
from movici_simulation_core.models.udf_model.result_type import (
    ResultType,
    Shape,
    combine,
    combine_shape,
)

# The tokenizer tries these patterns in order and takes the first match, so longer operators must
# be listed before the shorter ones they start with, and keywords before `name`
TOKENS = {
    "**": r"\*\*",
    "*": r"\*",
    "/": r"/",
    "%": r"%",
    "+": r"\+",
    "-": r"-",
    "==": r"==",
    "!=": r"!=",
    ">=": r">=",
    "<=": r"<=",
    "<": r"<",
    ">": r">",
    "and": r"(&&|and\b)",
    "or": r"(\|\||or\b)",
    "not": r"(!|not\b)",
    "(": r"\(",
    ")": r"\)",
    ",": r",",
    "bool": r"(true|false)\b",
    "name": r"[A-Za-z_][A-Za-z0-9_]*",
    "ws": r"\s+",
    "num": r"([0-9]*[.])?[0-9]+([eE][-+]?[0-9]+)?",
}

COMPARISONS = ("==", "!=", "<", ">", "<=", ">=")


class Token(t.NamedTuple):
    type: str
    text: str


def compile(string):
    return compile_func(parse(tokenize(string)))


def tokenize(string: str, patterns: t.Optional[dict] = None) -> t.Iterator[Token]:
    patterns = patterns or TOKENS
    matchers: t.Dict[str, re.Pattern] = {
        k: re.compile(rf"^(?P<tok>{tok})(?P<tail>.*)$") for k, tok in patterns.items()
    }
    while string:
        for tok, pattern in matchers.items():
            if match := pattern.match(string):
                yield Token(tok, match.group("tok"))
                string = match.group("tail")
                break
        else:
            raise SyntaxError(f"Invalid syntax: '{string[:10]}")


def parse(tokens: t.Iterable[Token]):
    return Parser(tokens).parse()


def get_vars(node: Node):
    vis = VariableNameCollector()
    node.accept(vis)
    return vis.vars


def infer_result_type(node: Node, variables: t.Dict[str, ResultType]) -> ResultType:
    """Determine the type and shape of the values an expression produces.

    :param node: the root of the expression
    :param variables: the result type of every name that may appear in the expression
    :raises NameError: when the expression references a name that is not in `variables`
    """
    return node.accept_node(TypeInferrer(variables))


def compile_func(node: Node):
    return node.accept_node(UDFCompiler())


@dataclasses.dataclass
class Node:
    val: str

    def accept_node(self, visitor):
        """Accept a visitor but do not traverse any children. The visitor is responsible for
        traversing the tree.
        """
        return visitor.visit(self)

    def accept(self, visitor, top_down=False):
        """Accept a visitor and traverse the tree. Branch nodes must override
        `Node.accept_children`

        :param visitor: the Visitor
        :param top_down: whether to first the branch nodes and then the children (top_down=True) or
            first the children and then the branch nodes (top_down=False)
        """
        if top_down:
            visitor.visit(self)
        self.accept_children(visitor)
        if not top_down:
            visitor.visit(self)
        self.accept_node(visitor)

    def accept_children(self, visitor):
        """Branch nodes should override this to let the visitor visit the node's children"""
        pass


@dataclasses.dataclass
class Num(Node):
    pass


@dataclasses.dataclass
class Bool(Node):
    pass


@dataclasses.dataclass
class Var(Node):
    pass


@dataclasses.dataclass
class BinOp(Node):
    left: t.Optional[Node] = None
    right: t.Optional[Node] = None

    def accept_children(self, visitor):
        if self.left:
            self.left.accept(visitor)
        if self.right:
            self.right.accept(visitor)


@dataclasses.dataclass
class Func(Node):
    args: t.Tuple[Node, ...] = ()

    def accept_children(self, visitor):
        for arg in self.args:
            arg.accept(visitor)


class Parser:
    """A simple recursive descent parser"""

    ignore = ("ws",)
    current_token: Token

    def __init__(self, tokenizer: t.Iterable):
        self.tokenizer = iter(tokenizer)
        self.next_valid_token()

    def next_valid_token(self):
        try:
            tok = next(self.tokenizer)
            while tok.type in self.ignore:
                tok = next(self.tokenizer)
        except StopIteration:
            tok = None
        self.current_token = tok

    def error(self):
        raise SyntaxError("Invalid syntax")

    def peek(self, *token_type):
        if (tok := self.current_token) and tok.type in token_type:
            return tok
        return False

    def expect(self, *token_type: str):
        if self.peek(*token_type):
            self.next_valid_token()
            return True
        else:
            return False

    def expr(self):
        return self.or_expr()

    def or_expr(self):
        """or_expr : and_expr (("or" | "||") and_expr)*"""
        node = self.and_expr()
        while self.expect("or"):
            node = BinOp("or", left=node, right=self.and_expr())
        return node

    def and_expr(self):
        """and_expr : not_expr (("and" | "&&") not_expr)*"""
        node = self.not_expr()
        while self.expect("and"):
            node = BinOp("and", left=node, right=self.not_expr())
        return node

    def not_expr(self):
        """not_expr : ("not" | "!") not_expr | comp_expr"""
        if self.expect("not"):
            return Func("not", (self.not_expr(),))
        return self.comp_expr()

    def comp_expr(self):
        """comp_expr: add_expr (("==" | "!=" | "<" | ">" | "<=" | ">=") add_expr)?"""
        node = self.add_expr()
        if op := self.peek(*COMPARISONS):
            self.expect(op.type)
            node = BinOp(op.type, left=node, right=self.add_expr())

        return node

    def add_expr(self):
        """add_expr : mul_expr (("+" | "-") mul_expr)*"""
        node = self.mul_expr()
        while op := self.peek("+", "-"):
            self.expect(op.type)
            node = BinOp(op.type, left=node, right=self.mul_expr())

        return node

    def mul_expr(self):
        """mul_expr : unary_expr (("*" | "/" | "%") unary_expr)*"""
        node = self.unary_expr()

        while op := self.peek("*", "/", "%"):
            self.expect(op.type)
            node = BinOp(op.type, left=node, right=self.unary_expr())
        return node

    def unary_expr(self):
        """unary_expr : ("+" | "-") unary_expr | power_expr"""
        if op := self.peek("+", "-"):
            self.expect(op.type)
            return BinOp(op.type, Num("0"), self.unary_expr())
        return self.power_expr()

    def power_expr(self):
        """power_expr : atom ("**" unary_expr)?

        Exponentiation is right associative and binds tighter than unary minus, so that
        `-a ** 2` is `-(a ** 2)` and `a ** -2` is valid
        """
        node = self.atom()
        if self.expect("**"):
            node = BinOp("**", left=node, right=self.unary_expr())
        return node

    def atom(self):
        """atom : num | bool | function_or_name | "(" expr ")" """
        token = self.current_token
        if self.expect("num"):
            return Num(token.text)

        if self.expect("bool"):
            return Bool(token.text)

        if self.peek("name"):
            return self.function_or_name()

        if self.expect("("):
            node = self.expr()
            if self.expect(")"):
                return node
        self.error()

    def function_or_name(self):
        """function_or_name : name "(" expr? ("," expr)*  ")" | name"""
        token = self.current_token

        if self.expect("name"):
            if self.peek("("):
                self.expect("(")
                nodes = []
                if not self.peek(")"):
                    nodes.append(self.expr())
                    while self.peek(","):
                        self.expect(",")
                        nodes.append(self.expr())
                if self.expect(")"):
                    return Func(token.text, tuple(nodes))
                self.error()
            else:
                return Var(token.text)

        self.error()

    def parse(self):
        expr = self.expr()
        if self.current_token:
            self.error()
        return expr


BINARY_OPERATORS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": functions.divide,
    "%": functions.modulo,
    "**": functions.power,
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "and": functions.logical_and,
    "or": functions.logical_or,
}


BOOLEAN_OPERATORS = frozenset(COMPARISONS) | {"and", "or"}

# operators whose result type does not follow from promoting their operands
OPERATOR_RESULT_TYPES = {
    **{op: bool for op in BOOLEAN_OPERATORS},
    # numpy true division always produces floating point values
    "/": float,
}


class NodeVisitor:
    def visit(self, node: Node):
        pass


class VariableNameCollector(NodeVisitor):
    def __init__(self):
        self.vars = set()

    @functools.singledispatchmethod
    def visit(self, node: Node):
        pass

    @visit.register
    def _(self, node: Var):
        self.vars.add(node.val)


class TypeInferrer(NodeVisitor):
    """Walks an expression and determines the type and shape of its result. An unknown python type
    propagates instead of raising, so that a function without a type rule only makes the result
    less precise. A name that is not bound to an attribute is an error: it can never be evaluated.
    """

    def __init__(self, variables: t.Dict[str, ResultType]):
        self.variables = variables

    @functools.singledispatchmethod
    def visit(self, node: Node) -> ResultType:
        raise TypeError(f"Unsupported node of type {type(node)}")

    @visit.register
    def _(self, node: Num) -> ResultType:
        # numeric literals are compiled as floats
        return ResultType(float, Shape.SCALAR)

    @visit.register
    def _(self, node: Bool) -> ResultType:
        return ResultType(bool, Shape.SCALAR)

    @visit.register
    def _(self, node: Var) -> ResultType:
        try:
            return self.variables[node.val]
        except KeyError:
            raise NameError(
                f"'{node.val}' is not one of the inputs of this expression, "
                f"expected one of {sorted(self.variables)}"
            ) from None

    @visit.register
    def _(self, node: BinOp) -> ResultType:
        if node.left is None or node.right is None:
            raise ValueError("Invalid tree")
        left = node.left.accept_node(self)
        right = node.right.accept_node(self)
        return combine(left, right, py_type=OPERATOR_RESULT_TYPES.get(node.val))

    @visit.register
    def _(self, node: Func) -> ResultType:
        if node.val not in functions.functions:
            raise NameError(f"{node.val} is not a valid function name")
        args = [arg.accept_node(self) for arg in node.args]
        rule = functions.result_types.get(node.val)
        if rule is None or not args:
            return ResultType(None, combine_shape(*(arg.shape for arg in args)))
        return rule(args)


class UDFCompiler(NodeVisitor):
    @functools.singledispatchmethod
    def visit(self, node: Node):
        raise TypeError(f"Unsupported node of type {type(node)}")

    @visit.register
    def _(self, node: Var):
        return lambda v: v[node.val]

    @visit.register
    def _(self, node: Num):
        numeric = float(node.val)
        return lambda x: numeric

    @visit.register
    def _(self, node: Bool):
        boolean = node.val == "true"
        return lambda x: boolean

    @visit.register
    def _(self, node: BinOp):
        if node.left is None or node.right is None:
            raise ValueError("Invalid tree")
        op = BINARY_OPERATORS[node.val]
        left = node.left.accept_node(self)
        right = node.right.accept_node(self)
        return lambda x: op(left(x), right(x))

    @visit.register
    def _(self, node: Func):
        try:
            func = functions.functions[node.val]
        except KeyError as e:
            raise NameError(f"{node.val} is not a valid function name") from e
        args = tuple(arg.accept_node(self) for arg in node.args)
        return lambda x: func(*(arg(x) for arg in args))
