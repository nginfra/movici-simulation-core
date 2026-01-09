"""Expression parser for Rules Model conditions.

Parses condition expressions including compound boolean expressions like:

- ``"<simtime> == 34h"``
- ``"<clocktime> == 12:00"``
- ``"drinking_water.level >= 23"``
- ``"drinking_water.level <= 21 & drinking_water.level >= 23"``
- ``"(level < 10 | level > 90) & status == true"``

Uses pyparsing with infixNotation for proper operator precedence.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Protocol, Union

import pyparsing as pp


class ExpressionType(Enum):
    """Type of the left-hand side of a condition expression."""

    SIMTIME = "simtime"
    CLOCKTIME = "clocktime"
    ATTRIBUTE = "attribute"


class ComparisonOperator(Enum):
    """Comparison operators with their evaluation functions."""

    EQ = "=="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="

    def evaluate(self, left: Any, right: Any) -> bool:
        """Evaluate the comparison between left and right values.

        :param left: Left-hand side value
        :param right: Right-hand side value
        :returns: Result of the comparison
        :rtype: bool
        """
        if left is None or right is None:
            return False

        evaluators: dict[ComparisonOperator, Callable[[Any, Any], bool]] = {
            ComparisonOperator.EQ: lambda a, b: a == b,
            ComparisonOperator.NE: lambda a, b: a != b,
            ComparisonOperator.LT: lambda a, b: a < b,
            ComparisonOperator.LE: lambda a, b: a <= b,
            ComparisonOperator.GT: lambda a, b: a > b,
            ComparisonOperator.GE: lambda a, b: a >= b,
        }
        return evaluators[self](left, right)


# Time unit multipliers in seconds
_TIME_UNITS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}

# Pattern for duration expressions like "1d5h30m10s" or "34h"
_DURATION_PATTERN = re.compile(r"(\d+)([dhms])", re.IGNORECASE)


def parse_duration(expr: str) -> float:
    """Parse a duration expression to seconds.

    Supports formats like:

    - ``"34h"`` → 122400 seconds
    - ``"5m"`` → 300 seconds
    - ``"1d5h30s"`` → 104430 seconds
    - ``"12h30m"`` → 45000 seconds

    :param expr: Duration expression string (e.g., "1d5h30m")
    :returns: Duration in seconds
    :rtype: float
    :raises ValueError: If the expression cannot be parsed
    """
    matches = _DURATION_PATTERN.findall(expr)
    if not matches:
        raise ValueError(f"Invalid duration expression: {expr!r}")

    # Validate that the entire expression is consumed (no extra characters)
    reconstructed = "".join(f"{value}{unit}" for value, unit in matches)
    if reconstructed.lower() != expr.lower():
        raise ValueError(
            f"Invalid duration expression: {expr!r} "
            f"(contains invalid characters or format)"
        )

    total_seconds = 0.0
    for value_str, unit in matches:
        total_seconds += int(value_str) * _TIME_UNITS[unit.lower()]

    return total_seconds


def parse_clock_time(expr: str) -> float:
    """Parse a clock time expression to seconds since midnight.

    Supports formats like:

    - ``"12:30"`` → 45000 seconds (12 hours 30 minutes)
    - ``"08:15"`` → 29700 seconds
    - ``"23:59:59"`` → 86399 seconds

    :param expr: Clock time expression string (HH:MM or HH:MM:SS)
    :returns: Seconds since midnight
    :rtype: float
    :raises ValueError: If the expression cannot be parsed
    """
    try:
        # Try HH:MM:SS format first
        if expr.count(":") == 2:
            dt = datetime.strptime(expr, "%H:%M:%S")
        else:
            dt = datetime.strptime(expr, "%H:%M")
        return dt.hour * 3600 + dt.minute * 60 + dt.second
    except ValueError as err:
        raise ValueError(f"Invalid clock time expression: {expr!r}") from err


@dataclass
class Comparison:
    """A single comparison expression (e.g., ``level >= 23``)."""

    expr_type: ExpressionType
    operator: ComparisonOperator
    value: Union[float, bool]
    attribute_name: Optional[str] = None

    def evaluate(
        self,
        simtime: Optional[float] = None,
        clocktime: Optional[float] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Evaluate this comparison.

        :param simtime: Simulation time in seconds since start
        :param clocktime: Clock time in seconds since midnight
        :param attributes: Dict mapping attribute names to values
        :returns: True if comparison is satisfied
        :rtype: bool
        """
        if self.expr_type == ExpressionType.SIMTIME:
            left_value = simtime
        elif self.expr_type == ExpressionType.CLOCKTIME:
            left_value = clocktime
        else:
            attributes = attributes or {}
            left_value = attributes.get(self.attribute_name)

        return self.operator.evaluate(left_value, self.value)

    def get_attribute_names(self) -> set[str]:
        """Return set of attribute names referenced by this comparison.

        :returns: Set of attribute names (empty if simtime/clocktime)
        :rtype: set[str]
        """
        if self.expr_type == ExpressionType.ATTRIBUTE and self.attribute_name:
            return {self.attribute_name}
        return set()


@dataclass
class BooleanExpression:
    """A compound boolean expression with AND/OR/NOT operators."""

    operator: str
    operands: list[Union["BooleanExpression", Comparison]] = field(default_factory=list)

    def evaluate(
        self,
        simtime: Optional[float] = None,
        clocktime: Optional[float] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Evaluate this boolean expression.

        :param simtime: Simulation time in seconds since start
        :param clocktime: Clock time in seconds since midnight
        :param attributes: Dict mapping attribute names to values
        :returns: True if expression is satisfied
        :rtype: bool
        """
        if self.operator == "NOT":
            return not self.operands[0].evaluate(simtime, clocktime, attributes)
        elif self.operator == "AND":
            return all(op.evaluate(simtime, clocktime, attributes) for op in self.operands)
        elif self.operator == "OR":
            return any(op.evaluate(simtime, clocktime, attributes) for op in self.operands)
        return False

    def get_attribute_names(self) -> set[str]:
        """Return set of all attribute names referenced in this expression.

        :returns: Set of attribute names
        :rtype: set[str]
        """
        names: set[str] = set()
        for operand in self.operands:
            names.update(operand.get_attribute_names())
        return names


class Evaluable(Protocol):
    """Protocol for objects that can be evaluated as conditions."""

    def evaluate(
        self,
        simtime: Optional[float] = None,
        clocktime: Optional[float] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Evaluate this expression."""
        ...

    def get_attribute_names(self) -> set[str]:
        """Return set of attribute names referenced by this expression."""
        ...


ParsedCondition = Union[Comparison, BooleanExpression]


class _ExprWrapper(Protocol):
    """Protocol for intermediate expression wrappers used during parsing."""

    def to_expr(self) -> ParsedCondition:
        """Convert to a ParsedCondition."""
        ...


def _unwrap_expr(token: Any) -> ParsedCondition:
    """Unwrap an expression token to a ParsedCondition.

    :param token: Either a Comparison, BooleanExpression, or wrapper with to_expr()
    :returns: Unwrapped ParsedCondition
    """
    if isinstance(token, (_NotExpr, _BinaryExpr)):
        return token.to_expr()
    return token


class _NotExpr:
    """Helper class for NOT expression parsing."""

    def __init__(self, tokens: pp.ParseResults) -> None:
        self.operand = tokens[0][1]

    def to_expr(self) -> BooleanExpression:
        """Convert to BooleanExpression.

        :returns: BooleanExpression with NOT operator
        :rtype: BooleanExpression
        """
        return BooleanExpression(operator="NOT", operands=[_unwrap_expr(self.operand)])


class _BinaryExpr:
    """Helper class for binary expression parsing."""

    def __init__(self, tokens: pp.ParseResults) -> None:
        self.tokens = tokens[0]

    def to_expr(self) -> Union[Comparison, BooleanExpression]:
        """Convert to BooleanExpression or Comparison.

        :returns: Parsed expression
        :rtype: Union[Comparison, BooleanExpression]
        """
        operands = []
        operator = None

        for i, token in enumerate(self.tokens):
            if i % 2 == 0:
                # Even indices are operands
                operands.append(_unwrap_expr(token))
            else:
                # Odd indices are operators
                op = token.upper() if isinstance(token, str) else token
                if op in ("&&", "AND"):
                    operator = "AND"
                elif op in ("||", "OR"):
                    operator = "OR"

        if len(operands) == 1:
            return operands[0]

        return BooleanExpression(operator=operator, operands=operands)


def _build_grammar() -> pp.ParserElement:
    """Build the pyparsing grammar for condition expressions.

    :returns: Pyparsing grammar for parsing condition expressions
    :rtype: pp.ParserElement
    """
    # Numeric literals
    integer = pp.Word(pp.nums).setParseAction(lambda t: int(t[0]))
    decimal = pp.Combine(pp.Optional(pp.Word(pp.nums)) + "." + pp.Word(pp.nums)).setParseAction(
        lambda t: float(t[0])
    )
    number = decimal | integer

    # Time expressions: durations (34h, 5m, 1d5h30s) and clock times (12:30, 12:30:45)
    time_unit = pp.oneOf("h m s d", caseless=True)
    single_duration = pp.Combine(pp.Word(pp.nums) + time_unit)
    duration = pp.Combine(pp.OneOrMore(single_duration)).setParseAction(
        lambda t: parse_duration(t[0])
    )
    # Clock time: H:MM, HH:MM, H:MM:SS, or HH:MM:SS (single-digit hour allowed)
    clock_time = pp.Combine(
        pp.Word(pp.nums, min=1, max=2)
        + ":"
        + pp.Word(pp.nums, exact=2)
        + pp.Optional(":" + pp.Word(pp.nums, exact=2))
    ).setParseAction(lambda t: parse_clock_time(t[0]))

    # Boolean literals
    boolean = pp.CaselessKeyword("true").setParseAction(lambda: True) | pp.CaselessKeyword(
        "false"
    ).setParseAction(lambda: False)

    value = duration | clock_time | number | boolean

    # Comparison operators
    comparison_op = pp.oneOf("== != <= >= < >")

    # Special time variables - simplified patterns
    simtime_var = pp.Literal("<simtime>").setParseAction(lambda: ExpressionType.SIMTIME)
    clocktime_var = pp.Literal("<clocktime>").setParseAction(
        lambda: ExpressionType.CLOCKTIME
    )

    # Attribute names: support multiple dots (e.g., "a.b.c.d")
    identifier = pp.Word(pp.alphas + "_", pp.alphanums + "_")
    attribute_name = pp.Combine(identifier + pp.ZeroOrMore("." + identifier))

    lhs = simtime_var | clocktime_var | attribute_name

    def make_comparison(tokens: pp.ParseResults) -> Comparison:
        lhs_val = tokens[0]
        op_str = tokens[1]
        rhs_val = tokens[2]

        if isinstance(lhs_val, ExpressionType):
            expr_type = lhs_val
            attr_name = None
        else:
            expr_type = ExpressionType.ATTRIBUTE
            attr_name = lhs_val

        op_map = {
            "==": ComparisonOperator.EQ,
            "!=": ComparisonOperator.NE,
            "<": ComparisonOperator.LT,
            "<=": ComparisonOperator.LE,
            ">": ComparisonOperator.GT,
            ">=": ComparisonOperator.GE,
        }

        return Comparison(
            expr_type=expr_type,
            operator=op_map[op_str],
            value=rhs_val,
            attribute_name=attr_name,
        )

    comparison = (lhs + comparison_op + value).setParseAction(make_comparison)

    # Boolean operators (support both single and double symbols)
    NOT = pp.CaselessKeyword("NOT") | pp.Literal("!")
    AND = pp.CaselessKeyword("AND") | pp.Literal("&&")
    OR = pp.CaselessKeyword("OR") | pp.Literal("||")

    # Build boolean expression with proper operator precedence using infixNotation
    # The second element in each tuple is the operand count:
    #   1 = unary operator (e.g., NOT takes one operand)
    #   2 = binary operator (e.g., AND/OR take two operands)
    bool_expr = pp.infixNotation(
        comparison,
        [
            (NOT, 1, pp.opAssoc.RIGHT, _NotExpr),  # 1 operand, right-associative
            (AND, 2, pp.opAssoc.LEFT, _BinaryExpr),  # 2 operands, left-associative
            (OR, 2, pp.opAssoc.LEFT, _BinaryExpr),  # 2 operands, left-associative
        ],
    )

    return bool_expr


_GRAMMAR = _build_grammar()


def parse_condition(expr_string: str) -> ParsedCondition:
    """Parse a condition expression string.

    Supports simple comparisons and compound boolean expressions:

    - ``"<simtime> == 34h"``
    - ``"level >= 23"``
    - ``"level <= 21 & level >= 23"``
    - ``"(level < 10 | level > 90) & status == true"``
    - ``"NOT status == true"``

    :param expr_string: Condition expression string
    :returns: Parsed condition (Comparison or BooleanExpression)
    :rtype: ParsedCondition
    :raises ValueError: If the expression cannot be parsed
    """
    try:
        result = _GRAMMAR.parseString(expr_string.strip(), parseAll=True)
    except pp.ParseException as e:
        raise ValueError(f"Invalid condition expression: {expr_string!r}") from e

    parsed = result[0]

    # Unwrap intermediate expression wrappers to final ParsedCondition
    if isinstance(parsed, (_NotExpr, _BinaryExpr)):
        return parsed.to_expr()

    return parsed
