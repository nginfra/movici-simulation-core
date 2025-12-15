"""Tests for the condition evaluator (JSON-based AND/OR structure)."""

import pytest

from movici_simulation_core.models.rules.condition import parse_rule_condition


class TestParseRuleCondition:
    """Tests for parsing rule conditions from JSON specifications."""

    def test_parse_string_condition(self):
        cond = parse_rule_condition("<simtime> == 34h")
        assert cond.expression is not None
        assert cond.operator is None
        assert cond.children == []

    def test_parse_and_condition(self):
        cond = parse_rule_condition({"and": ["level >= 10", "level <= 20"]})
        assert cond.expression is None
        assert cond.operator == "AND"
        assert len(cond.children) == 2

    def test_parse_or_condition(self):
        cond = parse_rule_condition({"or": ["level < 10", "level > 90"]})
        assert cond.expression is None
        assert cond.operator == "OR"
        assert len(cond.children) == 2

    def test_parse_nested_condition(self):
        spec = {
            "and": [
                "clocktime >= 23h",
                "clocktime < 6h",
                {"or": ["drinking_water.level < 90", "diameter > 89"]},
            ]
        }
        cond = parse_rule_condition(spec)
        assert cond.operator == "AND"
        assert len(cond.children) == 3
        assert cond.children[2].operator == "OR"

    def test_invalid_dict_raises(self):
        with pytest.raises(ValueError, match="expected 'and' or 'or'"):
            parse_rule_condition({"invalid": ["a", "b"]})

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid condition type"):
            parse_rule_condition(123)


class TestConditionEvaluate:
    """Tests for evaluating Condition objects."""

    def test_evaluate_string_simtime(self):
        cond = parse_rule_condition("<simtime> == 3600")
        assert cond.evaluate(simtime=3600)
        assert not cond.evaluate(simtime=7200)

    def test_evaluate_and_true(self):
        cond = parse_rule_condition({"and": ["level >= 10", "level <= 20"]})
        assert cond.evaluate(attributes={"level": 15})

    def test_evaluate_and_false(self):
        cond = parse_rule_condition({"and": ["level >= 10", "level <= 20"]})
        assert not cond.evaluate(attributes={"level": 25})

    def test_evaluate_or_true(self):
        cond = parse_rule_condition({"or": ["level < 10", "level > 90"]})
        assert cond.evaluate(attributes={"level": 5})
        assert cond.evaluate(attributes={"level": 95})

    def test_evaluate_or_false(self):
        cond = parse_rule_condition({"or": ["level < 10", "level > 90"]})
        assert not cond.evaluate(attributes={"level": 50})

    def test_evaluate_nested(self):
        spec = {
            "and": [
                "status == true",
                {"or": ["level < 10", "level > 90"]},
            ]
        }
        cond = parse_rule_condition(spec)
        assert cond.evaluate(attributes={"status": True, "level": 5})
        assert cond.evaluate(attributes={"status": True, "level": 95})
        assert not cond.evaluate(attributes={"status": True, "level": 50})
        assert not cond.evaluate(attributes={"status": False, "level": 5})


class TestConditionGetAttributeNames:
    """Tests for extracting attribute names from Condition objects."""

    def test_string_condition(self):
        cond = parse_rule_condition("drinking_water.level >= 23")
        assert cond.get_attribute_names() == {"drinking_water.level"}

    def test_and_condition(self):
        cond = parse_rule_condition({"and": ["level >= 10", "diameter > 5"]})
        assert cond.get_attribute_names() == {"level", "diameter"}

    def test_nested_condition(self):
        spec = {
            "and": [
                "status == true",
                {"or": ["level < 10", "flow > 5"]},
            ]
        }
        cond = parse_rule_condition(spec)
        assert cond.get_attribute_names() == {"status", "level", "flow"}

    def test_simtime_no_attributes(self):
        cond = parse_rule_condition("<simtime> == 34h")
        assert cond.get_attribute_names() == set()
