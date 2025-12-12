"""Tests for the expression parser."""

import pytest

from movici_simulation_core.models.rules.expression import (
    BooleanExpression,
    Comparison,
    ComparisonOperator,
    ExpressionType,
    parse_condition,
    parse_time_value,
)


class TestParseTimeValue:
    """Tests for time value parsing using timelength."""

    def test_parse_hours(self):
        assert parse_time_value("34h") == 34 * 3600

    def test_parse_minutes(self):
        assert parse_time_value("5m") == 5 * 60

    def test_parse_seconds(self):
        assert parse_time_value("30s") == 30

    def test_parse_days(self):
        assert parse_time_value("1d") == 24 * 3600

    def test_parse_combined(self):
        assert parse_time_value("1h30m") == 3600 + 1800

    def test_parse_clock_format_as_mm_ss(self):
        # timelength interprets HH:MM as MM:SS
        assert parse_time_value("12:30") == 12 * 60 + 30

    def test_invalid_time_raises(self):
        with pytest.raises(ValueError):
            parse_time_value("invalid")


class TestComparisonOperator:
    """Tests for comparison operator evaluation."""

    def test_eq(self):
        assert ComparisonOperator.EQ.evaluate(5, 5)
        assert not ComparisonOperator.EQ.evaluate(5, 6)

    def test_ne(self):
        assert ComparisonOperator.NE.evaluate(5, 6)
        assert not ComparisonOperator.NE.evaluate(5, 5)

    def test_lt(self):
        assert ComparisonOperator.LT.evaluate(5, 6)
        assert not ComparisonOperator.LT.evaluate(6, 5)

    def test_le(self):
        assert ComparisonOperator.LE.evaluate(5, 6)
        assert ComparisonOperator.LE.evaluate(5, 5)
        assert not ComparisonOperator.LE.evaluate(6, 5)

    def test_gt(self):
        assert ComparisonOperator.GT.evaluate(6, 5)
        assert not ComparisonOperator.GT.evaluate(5, 6)

    def test_ge(self):
        assert ComparisonOperator.GE.evaluate(6, 5)
        assert ComparisonOperator.GE.evaluate(5, 5)
        assert not ComparisonOperator.GE.evaluate(5, 6)

    def test_none_returns_false(self):
        assert not ComparisonOperator.EQ.evaluate(None, 5)
        assert not ComparisonOperator.EQ.evaluate(5, None)


class TestParseConditionSimple:
    """Tests for parsing simple condition expressions."""

    def test_simtime_equals(self):
        cond = parse_condition("<simtime> == 34h")
        assert isinstance(cond, Comparison)
        assert cond.expr_type == ExpressionType.SIMTIME
        assert cond.operator == ComparisonOperator.EQ
        assert cond.value == 34 * 3600

    def test_clocktime_equals(self):
        cond = parse_condition("<clocktime> == 12h30m")
        assert isinstance(cond, Comparison)
        assert cond.expr_type == ExpressionType.CLOCKTIME
        assert cond.value == 12 * 3600 + 30 * 60

    def test_clocktime_keyword(self):
        cond = parse_condition("clocktime >= 23h")
        assert cond.expr_type == ExpressionType.CLOCKTIME

    def test_attribute_comparison(self):
        cond = parse_condition("drinking_water.level >= 23")
        assert isinstance(cond, Comparison)
        assert cond.expr_type == ExpressionType.ATTRIBUTE
        assert cond.attribute_name == "drinking_water.level"
        assert cond.operator == ComparisonOperator.GE
        assert cond.value == 23

    def test_simple_attribute_name(self):
        cond = parse_condition("diameter > 89")
        assert cond.expr_type == ExpressionType.ATTRIBUTE
        assert cond.attribute_name == "diameter"

    def test_boolean_value_true(self):
        cond = parse_condition("status == true")
        assert cond.value is True

    def test_boolean_value_false(self):
        cond = parse_condition("status == false")
        assert cond.value is False

    def test_float_value(self):
        cond = parse_condition("level > 23.5")
        assert cond.value == 23.5


class TestParseConditionBoolean:
    """Tests for parsing boolean compound expressions."""

    def test_and_operator(self):
        cond = parse_condition("level >= 10 & level <= 20")
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == "AND"
        assert len(cond.operands) == 2

    def test_or_operator(self):
        cond = parse_condition("level < 10 | level > 90")
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == "OR"
        assert len(cond.operands) == 2

    def test_and_keyword(self):
        cond = parse_condition("level >= 10 AND level <= 20")
        assert cond.operator == "AND"

    def test_or_keyword(self):
        cond = parse_condition("level < 10 OR level > 90")
        assert cond.operator == "OR"

    def test_not_operator(self):
        cond = parse_condition("NOT status == true")
        assert isinstance(cond, BooleanExpression)
        assert cond.operator == "NOT"
        assert len(cond.operands) == 1

    def test_parentheses(self):
        cond = parse_condition("(level < 10 | level > 90) & status == true")
        assert cond.operator == "AND"
        assert len(cond.operands) == 2
        assert cond.operands[0].operator == "OR"

    def test_complex_nested(self):
        cond = parse_condition("a > 1 & b > 2 & c > 3")
        assert cond.operator == "AND"
        assert len(cond.operands) == 3


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


class TestBooleanExpressionEvaluate:
    """Tests for evaluating BooleanExpression objects."""

    def test_evaluate_and_true(self):
        cond = parse_condition("level >= 10 & level <= 20")
        assert cond.evaluate(attributes={"level": 15})

    def test_evaluate_and_false(self):
        cond = parse_condition("level >= 10 & level <= 20")
        assert not cond.evaluate(attributes={"level": 25})

    def test_evaluate_or_true(self):
        cond = parse_condition("level < 10 | level > 90")
        assert cond.evaluate(attributes={"level": 5})
        assert cond.evaluate(attributes={"level": 95})

    def test_evaluate_or_false(self):
        cond = parse_condition("level < 10 | level > 90")
        assert not cond.evaluate(attributes={"level": 50})

    def test_evaluate_not(self):
        cond = parse_condition("NOT status == true")
        assert cond.evaluate(attributes={"status": False})
        assert not cond.evaluate(attributes={"status": True})

    def test_evaluate_complex(self):
        cond = parse_condition("(level < 10 | level > 90) & status == true")
        assert cond.evaluate(attributes={"level": 5, "status": True})
        assert cond.evaluate(attributes={"level": 95, "status": True})
        assert not cond.evaluate(attributes={"level": 50, "status": True})
        assert not cond.evaluate(attributes={"level": 5, "status": False})


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
        cond = parse_condition("level >= 10 & diameter > 5")
        assert cond.get_attribute_names() == {"level", "diameter"}

    def test_multiple_attributes_complex(self):
        cond = parse_condition("(level < 10 | flow > 5) & status == true")
        assert cond.get_attribute_names() == {"level", "flow", "status"}
