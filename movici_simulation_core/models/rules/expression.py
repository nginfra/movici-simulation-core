"""Expression parser for Rules Model conditions.

Parses condition expressions including compound boolean expressions like:

- ``"<simtime> == 34h"``
- ``"<clocktime> == 12:00"``
- ``"drinking_water.level >= 23"``
- ``"drinking_water.level <= 21 && drinking_water.level >= 23"``
- ``"(level < 10 || level > 90) && status == true"``
- ``"a > b"`` (attribute vs attribute)
- ``"23 >= level"`` (literal vs attribute)

Both sides of a comparison can be an attribute name, a literal value, or a time variable.

Uses pyparsing with infixNotation for proper operator precedence.
"""

import operator
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Union

import pyparsing as pp


class ExpressionType(Enum):
    """Type of one side of a condition expression."""

    SIMTIME = "simtime"
    CLOCKTIME = "clocktime"
    ATTRIBUTE = "attribute"
    LITERAL = "literal"


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
        return _COMPARISON_OPERATORS[self.value](left, right)


_COMPARISON_OPERATORS = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


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
            f"Invalid duration expression: {expr!r} (contains invalid characters or format)"
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
class ComparisonSide:
    """One side of a comparison expression."""

    expr_type: ExpressionType
    attribute_name: Optional[str] = None
    value: Any = None


@dataclass
class Comparison:
    """A single comparison expression (e.g., ``level >= 23``)."""

    left: ComparisonSide
    operator: ComparisonOperator
    right: ComparisonSide

    def _resolve(
        self,
        side: ComparisonSide,
        simtime: Optional[float],
        clocktime: Optional[float],
        attributes: Optional[dict[str, Any]],
    ) -> Any:
        if side.expr_type == ExpressionType.SIMTIME:
            return simtime
        elif side.expr_type == ExpressionType.CLOCKTIME:
            return clocktime
        elif side.expr_type == ExpressionType.LITERAL:
            return side.value
        else:
            return (attributes or {}).get(side.attribute_name)

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
        left_value = self._resolve(self.left, simtime, clocktime, attributes)
        right_value = self._resolve(self.right, simtime, clocktime, attributes)
        return self.operator.evaluate(left_value, right_value)

    def get_attribute_names(self) -> set[str]:
        """Return set of attribute names referenced by this comparison.

        :returns: Set of attribute names (empty if simtime/clocktime/literal only)
        :rtype: set[str]
        """
        names: set[str] = set()
        for side in (self.left, self.right):
            if side.expr_type == ExpressionType.ATTRIBUTE and side.attribute_name:
                names.add(side.attribute_name)
        return names

    def get_time_thresholds(self) -> list[tuple[ExpressionType, float]]:
        """Return time thresholds from this comparison.

        If one side is SIMTIME/CLOCKTIME and the other is LITERAL, returns
        the literal value tagged with the time type.

        :returns: List of (ExpressionType, threshold_value) tuples
        :rtype: list[tuple[ExpressionType, float]]
        """
        result: list[tuple[ExpressionType, float]] = []
        for time_side, value_side in [(self.left, self.right), (self.right, self.left)]:
            if (
                time_side.expr_type
                in (
                    ExpressionType.SIMTIME,
                    ExpressionType.CLOCKTIME,
                )
                and value_side.expr_type == ExpressionType.LITERAL
            ):
                result.append((time_side.expr_type, value_side.value))
        return result


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

    def get_time_thresholds(self) -> list[tuple[ExpressionType, float]]:
        """Return time thresholds from all operands recursively.

        :returns: List of (ExpressionType, threshold_value) tuples
        :rtype: list[tuple[ExpressionType, float]]
        """
        result: list[tuple[ExpressionType, float]] = []
        for operand in self.operands:
            result.extend(operand.get_time_thresholds())
        return result


ParsedCondition = Union[Comparison, BooleanExpression]


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
    clocktime_var = pp.Literal("<clocktime>").setParseAction(lambda: ExpressionType.CLOCKTIME)

    # Attribute names: support multiple dots (e.g., "a.b.c.d")
    identifier = pp.Word(pp.alphas + "_", pp.alphanums + "_")
    attribute_name = pp.Combine(identifier + pp.ZeroOrMore("." + identifier))

    operand = simtime_var | clocktime_var | value | attribute_name

    def _make_side(token: Any) -> ComparisonSide:
        if isinstance(token, ExpressionType):
            return ComparisonSide(expr_type=token)
        elif isinstance(token, str):
            return ComparisonSide(expr_type=ExpressionType.ATTRIBUTE, attribute_name=token)
        else:
            return ComparisonSide(expr_type=ExpressionType.LITERAL, value=token)

    def make_comparison(tokens: pp.ParseResults) -> Comparison:
        op_map = {
            "==": ComparisonOperator.EQ,
            "!=": ComparisonOperator.NE,
            "<": ComparisonOperator.LT,
            "<=": ComparisonOperator.LE,
            ">": ComparisonOperator.GT,
            ">=": ComparisonOperator.GE,
        }

        return Comparison(
            left=_make_side(tokens[0]),
            operator=op_map[tokens[1]],
            right=_make_side(tokens[2]),
        )

    comparison = (operand + comparison_op + operand).setParseAction(make_comparison)

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

    Supports simple comparisons and compound boolean expressions.
    Both sides of a comparison can be an attribute, literal, or time variable:

    - ``"<simtime> == 34h"``
    - ``"level >= 23"``
    - ``"a > b"`` (attribute vs attribute)
    - ``"23 >= level"`` (literal vs attribute)
    - ``"level <= 21 && level >= 23"``
    - ``"(level < 10 || level > 90) && status == true"``
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
