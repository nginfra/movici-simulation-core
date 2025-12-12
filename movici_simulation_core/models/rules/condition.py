"""Condition evaluator for Rules Model.

Handles the JSON-based rule condition structure which can be:

- A string expression: ``"<simtime> == 34h"``
- A dict with ``"and"`` key: ``{"and": ["expr1", "expr2"]}``
- A dict with ``"or"`` key: ``{"or": ["expr1", "expr2"]}``
- Nested combinations of the above
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Union

from .expression import BooleanExpression, Comparison, parse_condition


@dataclass
class Condition:
    """A condition that can be evaluated against simulation state.

    Wraps either a parsed expression or a JSON-based AND/OR structure.
    """

    expression: Union[Comparison, BooleanExpression, None] = None
    operator: Optional[str] = None
    children: list["Condition"] = field(default_factory=list)

    def evaluate(
        self,
        simtime: Optional[float] = None,
        clocktime: Optional[float] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Evaluate this condition.

        :param simtime: Simulation time in seconds since start
        :param clocktime: Clock time in seconds since midnight
        :param attributes: Dict mapping attribute names to values
        :returns: True if condition is satisfied
        :rtype: bool
        """
        if self.expression is not None:
            return self.expression.evaluate(simtime, clocktime, attributes)

        if self.operator == "AND":
            return all(c.evaluate(simtime, clocktime, attributes) for c in self.children)
        elif self.operator == "OR":
            return any(c.evaluate(simtime, clocktime, attributes) for c in self.children)

        return False

    def get_attribute_names(self) -> set[str]:
        """Return set of all attribute names referenced in this condition.

        :returns: Set of attribute names
        :rtype: set[str]
        """
        if self.expression is not None:
            return self.expression.get_attribute_names()

        names: set[str] = set()
        for child in self.children:
            names.update(child.get_attribute_names())
        return names


ConditionSpec = Union[str, dict[str, Any]]


def parse_rule_condition(spec: ConditionSpec) -> Condition:
    """Parse a rule condition from JSON specification.

    The specification can be:

    - A string expression: ``"<simtime> == 34h"``
    - A dict with ``"and"`` key containing a list of conditions
    - A dict with ``"or"`` key containing a list of conditions

    :param spec: Condition specification (string or dict)
    :returns: Parsed Condition object
    :rtype: Condition
    :raises ValueError: If the specification is invalid
    """
    if isinstance(spec, str):
        return Condition(expression=parse_condition(spec))

    if isinstance(spec, dict):
        if "and" in spec:
            children = [parse_rule_condition(s) for s in spec["and"]]
            return Condition(operator="AND", children=children)
        elif "or" in spec:
            children = [parse_rule_condition(s) for s in spec["or"]]
            return Condition(operator="OR", children=children)
        else:
            raise ValueError(f"Invalid condition dict, expected 'and' or 'or' key: {spec!r}")

    raise ValueError(f"Invalid condition type: {type(spec).__name__}")
