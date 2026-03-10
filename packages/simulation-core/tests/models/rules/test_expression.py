"""Tests for the expression parser."""

import pytest

from movici_simulation_core.models.rules.expression import (
    BooleanExpression,
    Comparison,
    ComparisonOperator,
    ExpressionType,
    parse_clock_time,
    parse_condition,
    parse_duration,
)


class TestParseDuration:
    """Tests for duration parsing."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("34h", 34 * 3600),
            ("5m", 5 * 60),
            ("30s", 30),
            ("1d", 24 * 3600),
            ("1h30m", 3600 + 1800),
            ("1d5h30m10s", 86400 + 5 * 3600 + 30 * 60 + 10),
            ("2H", 2 * 3600),  # Case insensitive
        ],
    )
    def test_parse_duration(self, expr, expected):
        assert parse_duration(expr) == expected

    def test_invalid_duration_raises(self):
        with pytest.raises(ValueError):
            parse_duration("invalid")

    @pytest.mark.parametrize(
        "expr",
        [
            "1h garbage",  # trailing garbage
            "1h2",  # trailing number without unit
            "abc1h",  # leading garbage
            "1h 30m",  # space between units
        ],
    )
    def test_invalid_duration_with_extra_chars_raises(self, expr):
        with pytest.raises(ValueError, match="contains invalid characters"):
            parse_duration(expr)


class TestParseClockTime:
    """Tests for clock time parsing."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("12:30", 12 * 3600 + 30 * 60),
            ("08:15", 8 * 3600 + 15 * 60),
            ("23:59", 23 * 3600 + 59 * 60),
            ("00:00", 0),
            ("12:30:45", 12 * 3600 + 30 * 60 + 45),
            ("9:45", 9 * 3600 + 45 * 60),  # single-digit hour
        ],
    )
    def test_parse_clock_time(self, expr, expected):
        assert parse_clock_time(expr) == expected

    def test_invalid_clock_time_raises(self):
        with pytest.raises(ValueError):
            parse_clock_time("invalid")

    @pytest.mark.parametrize(
        "expr",
        [
            "24:00",  # hour 24 is invalid
            "12:60",  # minute 60 is invalid
            "00:00:60",  # second 60 is invalid
        ],
    )
    def test_invalid_clock_time_values_raise(self, expr):
        with pytest.raises(ValueError, match="Invalid clock time"):
            parse_clock_time(expr)


class TestComparisonOperator:
    """Tests for comparison operator evaluation."""

    @pytest.mark.parametrize(
        "op,left,right,expected",
        [
            # EQ tests
            (ComparisonOperator.EQ, 5, 5, True),
            (ComparisonOperator.EQ, 5, 6, False),
            (ComparisonOperator.EQ, "a", "a", True),
            # NE tests
            (ComparisonOperator.NE, 5, 6, True),
            (ComparisonOperator.NE, 5, 5, False),
            # LT tests
            (ComparisonOperator.LT, 5, 6, True),
            (ComparisonOperator.LT, 6, 5, False),
            (ComparisonOperator.LT, 5, 5, False),
            # LE tests
            (ComparisonOperator.LE, 5, 6, True),
            (ComparisonOperator.LE, 5, 5, True),
            (ComparisonOperator.LE, 6, 5, False),
            # GT tests
            (ComparisonOperator.GT, 6, 5, True),
            (ComparisonOperator.GT, 5, 6, False),
            (ComparisonOperator.GT, 5, 5, False),
            # GE tests
            (ComparisonOperator.GE, 6, 5, True),
            (ComparisonOperator.GE, 5, 5, True),
            (ComparisonOperator.GE, 5, 6, False),
        ],
    )
    def test_comparison_operators(self, op, left, right, expected):
        assert op.evaluate(left, right) == expected

    @pytest.mark.parametrize(
        "op,left,right",
        [
            (ComparisonOperator.EQ, None, 5),
            (ComparisonOperator.EQ, 5, None),
            (ComparisonOperator.EQ, None, None),
            (ComparisonOperator.LT, None, 5),
            (ComparisonOperator.GT, 5, None),
        ],
    )
    def test_none_returns_false(self, op, left, right):
        """Any comparison involving None should return False."""
        assert not op.evaluate(left, right)


class TestParseConditionSimple:
    """Tests for parsing simple condition expressions."""

    def test_simtime_equals(self):
        cond = parse_condition("<simtime> == 34h")
        assert isinstance(cond, Comparison)
        assert cond.left.expr_type == ExpressionType.SIMTIME
        assert cond.operator == ComparisonOperator.EQ
        assert cond.right.value == 34 * 3600

    def test_clocktime_equals(self):
        cond = parse_condition("<clocktime> == 12h30m")
        assert isinstance(cond, Comparison)
        assert cond.left.expr_type == ExpressionType.CLOCKTIME
        assert cond.right.value == 12 * 3600 + 30 * 60

    def test_attribute_comparison(self):
        cond = parse_condition("drinking_water.level >= 23")
        assert isinstance(cond, Comparison)
        assert cond.left.expr_type == ExpressionType.ATTRIBUTE
        assert cond.left.attribute_name == "drinking_water.level"
        assert cond.operator == ComparisonOperator.GE
        assert cond.right.value == 23

    def test_simple_attribute_name(self):
        cond = parse_condition("diameter > 89")
        assert cond.left.expr_type == ExpressionType.ATTRIBUTE
        assert cond.left.attribute_name == "diameter"

    def test_boolean_value_true(self):
        cond = parse_condition("status == true")
        assert cond.right.value is True

    def test_boolean_value_false(self):
        cond = parse_condition("status == false")
        assert cond.right.value is False

    def test_float_value(self):
        cond = parse_condition("level > 23.5")
        assert cond.right.value == 23.5

    def test_attribute_vs_attribute(self):
        cond = parse_condition("a > b")
        assert isinstance(cond, Comparison)
        assert cond.left.expr_type == ExpressionType.ATTRIBUTE
        assert cond.left.attribute_name == "a"
        assert cond.right.expr_type == ExpressionType.ATTRIBUTE
        assert cond.right.attribute_name == "b"

    def test_dotted_attributes_both_sides(self):
        cond = parse_condition("a.x >= b.y")
        assert cond.left.attribute_name == "a.x"
        assert cond.right.attribute_name == "b.y"

    def test_literal_lhs(self):
        cond = parse_condition("23 > level")
        assert cond.left.expr_type == ExpressionType.LITERAL
        assert cond.left.value == 23
        assert cond.right.expr_type == ExpressionType.ATTRIBUTE
        assert cond.right.attribute_name == "level"


class TestParseConditionBoolean:
    """Tests for parsing boolean compound expressions."""

    @pytest.mark.parametrize(
        "expr,expected_op",
        [
            ("level >= 10 && level <= 20", "AND"),  # Double symbol
            ("level >= 10 AND level <= 20", "AND"),  # Keyword
            ("level >= 10 and level <= 20", "AND"),  # Lowercase keyword
        ],
    )
    def test_and_operators(self, expr, expected_op):
        cond = parse_condition(expr)
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == expected_op
        assert len(cond.operands) == 2

    @pytest.mark.parametrize(
        "expr,expected_op",
        [
            ("level < 10 || level > 90", "OR"),  # Double symbol
            ("level < 10 OR level > 90", "OR"),  # Keyword
            ("level < 10 or level > 90", "OR"),  # Lowercase keyword
        ],
    )
    def test_or_operators(self, expr, expected_op):
        cond = parse_condition(expr)
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == expected_op
        assert len(cond.operands) == 2

    @pytest.mark.parametrize(
        "expr",
        [
            "NOT status == true",
            "! status == true",
        ],
    )
    def test_not_operators(self, expr):
        cond = parse_condition(expr)
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == "NOT"
        assert len(cond.operands) == 1

    def test_parentheses(self):
        cond = parse_condition("(level < 10 || level > 90) && status == true")
        assert cond.operator == "AND"
        assert len(cond.operands) == 2
        assert cond.operands[0].operator == "OR"

    def test_parentheses_and_inside_or(self):
        """Test (a && b) || (c && d) pattern for correct precedence."""
        cond = parse_condition("(a > 1 && b > 2) || (c > 3 && d > 4)")
        assert cond.operator == "OR"
        assert len(cond.operands) == 2
        assert cond.operands[0].operator == "AND"
        assert cond.operands[1].operator == "AND"

    def test_parentheses_or_inside_and(self):
        """Test a && (b || c) && d pattern for correct precedence."""
        cond = parse_condition("a > 1 && (b > 2 || c > 3) && d > 4")
        assert cond.operator == "AND"
        assert len(cond.operands) == 3
        assert cond.operands[1].operator == "OR"

    @pytest.mark.parametrize(
        "expr,expected_op,expected_operand_count",
        [
            ("a > 1 && b > 2 && c > 3", "AND", 3),
            ("a > 1 || b > 2 || c > 3", "OR", 3),
        ],
    )
    def test_chained_operators(self, expr, expected_op, expected_operand_count):
        cond = parse_condition(expr)
        assert cond.operator == expected_op
        assert len(cond.operands) == expected_operand_count


class TestComparisonEvaluate:
    """Tests for evaluating Comparison objects."""

    def test_evaluate_simtime(self):
        cond = parse_condition("<simtime> == 3600")
        assert cond.evaluate(simtime=3600)
        assert not cond.evaluate(simtime=7200)

    def test_evaluate_clocktime(self):
        cond = parse_condition("<clocktime> >= 12h")
        assert cond.evaluate(clocktime=12 * 3600)
        assert cond.evaluate(clocktime=18 * 3600)
        assert not cond.evaluate(clocktime=6 * 3600)

    def test_evaluate_attribute(self):
        cond = parse_condition("level >= 23")
        assert cond.evaluate(attributes={"level": 25})
        assert cond.evaluate(attributes={"level": 23})
        assert not cond.evaluate(attributes={"level": 20})

    def test_evaluate_missing_attribute(self):
        cond = parse_condition("level >= 23")
        assert not cond.evaluate(attributes={})
        assert not cond.evaluate(attributes=None)

    def test_evaluate_attribute_vs_attribute(self):
        cond = parse_condition("a > b")
        assert cond.evaluate(attributes={"a": 10, "b": 5})
        assert not cond.evaluate(attributes={"a": 3, "b": 5})

    def test_evaluate_literal_lhs(self):
        cond = parse_condition("23 >= level")
        assert cond.evaluate(attributes={"level": 20})
        assert not cond.evaluate(attributes={"level": 30})


class TestBooleanExpressionEvaluate:
    """Tests for evaluating BooleanExpression objects."""

    def test_evaluate_and_true(self):
        cond = parse_condition("level >= 10 && level <= 20")
        assert cond.evaluate(attributes={"level": 15})

    def test_evaluate_and_false(self):
        cond = parse_condition("level >= 10 && level <= 20")
        assert not cond.evaluate(attributes={"level": 25})

    def test_evaluate_or_true(self):
        cond = parse_condition("level < 10 || level > 90")
        assert cond.evaluate(attributes={"level": 5})
        assert cond.evaluate(attributes={"level": 95})

    def test_evaluate_or_false(self):
        cond = parse_condition("level < 10 || level > 90")
        assert not cond.evaluate(attributes={"level": 50})

    def test_evaluate_not(self):
        cond = parse_condition("NOT status == true")
        assert cond.evaluate(attributes={"status": False})
        assert not cond.evaluate(attributes={"status": True})

    def test_evaluate_complex(self):
        cond = parse_condition("(level < 10 || level > 90) && status == true")
        assert cond.evaluate(attributes={"level": 5, "status": True})
        assert cond.evaluate(attributes={"level": 95, "status": True})
        assert not cond.evaluate(attributes={"level": 50, "status": True})
        assert not cond.evaluate(attributes={"level": 5, "status": False})

    def test_evaluate_with_float_values(self):
        """Test evaluation with floating point values."""
        cond = parse_condition("level > 23.5 && level < 24.5")
        assert cond.evaluate(attributes={"level": 24.0})
        assert cond.evaluate(attributes={"level": 23.7})
        assert not cond.evaluate(attributes={"level": 23.5})  # not > 23.5
        assert not cond.evaluate(attributes={"level": 24.5})  # not < 24.5

    def test_evaluate_with_boolean_values(self):
        """Test evaluation with boolean attribute values."""
        cond = parse_condition("active == true && enabled == false")
        assert cond.evaluate(attributes={"active": True, "enabled": False})
        assert not cond.evaluate(attributes={"active": True, "enabled": True})
        assert not cond.evaluate(attributes={"active": False, "enabled": False})


class TestGetAttributeNames:
    """Tests for extracting attribute names from expressions."""

    def test_simtime_no_attributes(self):
        cond = parse_condition("<simtime> == 34h")
        assert cond.get_attribute_names() == set()

    def test_single_attribute(self):
        cond = parse_condition("level >= 23")
        assert cond.get_attribute_names() == {"level"}

    def test_dotted_attribute(self):
        cond = parse_condition("drinking_water.level >= 23")
        assert cond.get_attribute_names() == {"drinking_water.level"}

    def test_multiple_attributes_and(self):
        cond = parse_condition("level >= 10 && diameter > 5")
        assert cond.get_attribute_names() == {"level", "diameter"}

    def test_multiple_attributes_complex(self):
        cond = parse_condition("(level < 10 || flow > 5) && status == true")
        assert cond.get_attribute_names() == {"level", "flow", "status"}

    def test_attributes_both_sides(self):
        cond = parse_condition("a > b")
        assert cond.get_attribute_names() == {"a", "b"}

    def test_literal_lhs_only_rhs_attribute(self):
        cond = parse_condition("23 > level")
        assert cond.get_attribute_names() == {"level"}

    def test_compound_with_both_side_attrs(self):
        cond = parse_condition("a > b && c == true")
        assert cond.get_attribute_names() == {"a", "b", "c"}


class TestMultiDotAttributeNames:
    """Tests for attribute names with multiple dots."""

    @pytest.mark.parametrize(
        "expr,expected_name",
        [
            ("a.b >= 1", "a.b"),
            ("a.b.c >= 1", "a.b.c"),
            ("a.b.c.d >= 1", "a.b.c.d"),
            ("drinking_water.network.level >= 1", "drinking_water.network.level"),
        ],
    )
    def test_multi_dot_attribute_parsing(self, expr, expected_name):
        cond = parse_condition(expr)
        assert cond.left.attribute_name == expected_name

    def test_multi_dot_in_boolean_expression(self):
        cond = parse_condition("a.b.c >= 10 && x.y.z <= 20")
        assert cond.get_attribute_names() == {"a.b.c", "x.y.z"}


class TestInvalidExpressions:
    """Tests for invalid expression handling."""

    @pytest.mark.parametrize(
        "expr",
        [
            "",  # Empty
            "level",  # Missing operator and value
            "level >",  # Missing value
            "> 5",  # Missing left-hand side
            "level >> 5",  # Invalid operator
            "level === 5",  # Invalid operator
            "and",  # Just an operator
            "and a",  # Operator followed by incomplete expression
            "a > 1 and and b > 2",  # Double operator
            "a > 1 or and b > 2",  # Mixed double operator
            "a > 1 and",  # Trailing operator
        ],
    )
    def test_invalid_expression_raises(self, expr):
        with pytest.raises(ValueError, match="Invalid condition expression"):
            parse_condition(expr)


class TestNoSpaceExpressions:
    """Tests for expressions without spaces between tokens."""

    @pytest.mark.parametrize(
        "expr,expected_attr,expected_op,expected_value",
        [
            ("attribute>3", "attribute", ComparisonOperator.GT, 3),
            ("level>=23", "level", ComparisonOperator.GE, 23),
            ("status==true", "status", ComparisonOperator.EQ, True),
        ],
    )
    def test_no_space_attribute_comparison(self, expr, expected_attr, expected_op, expected_value):
        cond = parse_condition(expr)
        assert isinstance(cond, Comparison)
        assert cond.left.attribute_name == expected_attr
        assert cond.operator == expected_op
        assert cond.right.value == expected_value

    def test_no_space_simtime(self):
        cond = parse_condition("<simtime>==34h")
        assert cond.left.expr_type == ExpressionType.SIMTIME
        assert cond.operator == ComparisonOperator.EQ
        assert cond.right.value == 34 * 3600

    def test_no_space_clocktime(self):
        cond = parse_condition("<clocktime>>=12:00")
        assert cond.left.expr_type == ExpressionType.CLOCKTIME
        assert cond.operator == ComparisonOperator.GE
        assert cond.right.value == 12 * 3600


class TestClockTimeInConditions:
    """Tests for clock time expressions in conditions."""

    def test_clock_time_format_in_condition(self):
        """Clock time with HH:MM format should be parsed correctly."""
        cond = parse_condition("<clocktime> == 12:30")
        assert cond.right.value == 12 * 3600 + 30 * 60

    def test_clock_time_format_hms_in_condition(self):
        """Clock time with HH:MM:SS format should be parsed correctly."""
        cond = parse_condition("<clocktime> >= 08:30:00")
        assert cond.right.value == 8 * 3600 + 30 * 60


class TestGetTimeThresholds:
    """Tests for extracting time thresholds from expressions."""

    def test_simtime_comparison(self):
        cond = parse_condition("<simtime> >= 3600")
        result = cond.get_time_thresholds()
        assert result == [(ExpressionType.SIMTIME, 3600)]

    def test_simtime_duration(self):
        cond = parse_condition("<simtime> == 1h30m")
        result = cond.get_time_thresholds()
        assert result == [(ExpressionType.SIMTIME, 5400)]

    def test_clocktime_comparison(self):
        cond = parse_condition("<clocktime> >= 12:30")
        result = cond.get_time_thresholds()
        assert result == [(ExpressionType.CLOCKTIME, 12 * 3600 + 30 * 60)]

    def test_attribute_comparison_returns_empty(self):
        cond = parse_condition("level >= 23")
        assert cond.get_time_thresholds() == []

    def test_attribute_vs_attribute_returns_empty(self):
        cond = parse_condition("a > b")
        assert cond.get_time_thresholds() == []

    def test_literal_vs_literal_returns_empty(self):
        """Two literals: no time variable, so no thresholds."""
        cond = parse_condition("23 >= 10")
        assert cond.get_time_thresholds() == []

    def test_boolean_and_collects_all(self):
        cond = parse_condition("<simtime> >= 3600 && <clocktime> >= 12:00")
        result = cond.get_time_thresholds()
        assert (ExpressionType.SIMTIME, 3600) in result
        assert (ExpressionType.CLOCKTIME, 12 * 3600) in result
        assert len(result) == 2

    def test_boolean_or_collects_all(self):
        cond = parse_condition("<simtime> >= 100 || <simtime> >= 200")
        result = cond.get_time_thresholds()
        assert (ExpressionType.SIMTIME, 100) in result
        assert (ExpressionType.SIMTIME, 200) in result

    def test_nested_boolean_collects_all(self):
        cond = parse_condition("(<simtime> >= 3600 && level > 10) || <clocktime> >= 8:00")
        result = cond.get_time_thresholds()
        assert (ExpressionType.SIMTIME, 3600) in result
        assert (ExpressionType.CLOCKTIME, 8 * 3600) in result

    def test_not_expression_collects(self):
        cond = parse_condition("NOT <simtime> >= 3600")
        result = cond.get_time_thresholds()
        assert result == [(ExpressionType.SIMTIME, 3600)]

    def test_mixed_time_and_attribute_only_time(self):
        cond = parse_condition("<simtime> >= 3600 && level > 10")
        result = cond.get_time_thresholds()
        assert result == [(ExpressionType.SIMTIME, 3600)]
