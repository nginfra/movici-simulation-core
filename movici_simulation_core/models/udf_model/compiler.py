from __future__ import annotations

import dataclasses
import functools
import operator
import re
import typing as t

from movici_simulation_core.models.udf_model import functions

TOKENS = {
    "*": r"\*",
    "/": r"/",
    "+": r"\+",
    "-": r"-",
    "(": r"\(",
    ")": r"\)",
    ",": r",",
    "name": r"[A-Za-z_]+",
    "ws": r"\s+",
    "num": r"([0-9]*[.])?[0-9]+",
}


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
        """expr   : ["+"|"-"] term (("+" | "-") term)*"""
        if op := self.peek("+", "-"):
            self.expect(op.type)
            node = BinOp(op.type, Num("0"), self.term())
        else:
            node = self.term()
        while op := self.peek("+", "-"):
            self.expect(op.type)
            node = BinOp(op.type, left=node, right=self.term())

        return node

    def term(self):
        """term : atom ((MUL | DIV) atom)*"""
        node = self.atom()

        while op := self.peek("*", "/"):
            self.expect(op.type)
            node = BinOp(op.type, left=node, right=self.atom())
        return node

    def atom(self):
        """factor : num | function_or_name | "(" expr ")" """
        token = self.current_token
        if self.expect("num"):
            return Num(token.text)

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
    def _(self, node: BinOp):

        if node.left is None or node.right is None:
            raise ValueError("Invalid tree")
        op = {
            "+": operator.add,
            "-": operator.sub,
            "*": operator.mul,
            "/": operator.truediv,
        }[node.val]
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
