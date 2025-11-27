"""Control rule management for WNTR simulations"""

from __future__ import annotations

import typing as t

import wntr


class ControlManager:
    """Manages WNTR control rules from configuration and INP files

    Controls in WNTR define when and how to change network element states
    (e.g., open/close valves, start/stop pumps). This manager provides a
    simplified interface for creating common control types from Movici config.
    """

    def __init__(self, wn):
        """Initialize control manager

        :param wn: WNTR WaterNetworkModel instance
        """
        self.wn = wn
        self.controls: t.Dict[str, t.Any] = {}

    def add_time_control(
        self,
        control_name: str,
        target_element: str,
        target_attribute: str,
        value: t.Any,
        time: float,
        time_type: str = "sim_time",
    ):
        """Add a time-based control

        :param control_name: Unique name for the control
            :param target_element: Name of the element to control (pipe, pump, valve)
            target_attribute: Attribute to modify (e.g., 'status', 'speed')
            value: Value to set (use 0/Closed or 1/Open for status)
            time: Time in seconds
            time_type: Type of time ('sim_time' or 'clock_time')
        """
        try:
            # Get the target object
            target = self._get_element(target_element)

            # Convert status values to LinkStatus
            converted_value = self._convert_status_value(target_attribute, value)

            # Create the action
            action = wntr.network.controls.ControlAction(
                target, target_attribute, converted_value
            )

            # Create the condition based on time type
            if time_type == "sim_time":
                condition = wntr.network.controls.SimTimeCondition(
                    self.wn, "=", time
                )
            elif time_type == "clock_time":
                # Convert seconds to hours for ClockTimeCondition
                hours = int(time // 3600)
                minutes = int((time % 3600) // 60)
                seconds = int(time % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                condition = wntr.network.controls.TimeOfDayCondition(
                    self.wn, "at", time_str
                )
            else:
                raise ValueError(f"Unknown time_type: {time_type}")

            # Create and add the control
            control = wntr.network.controls.Control(condition, action)
            self.wn.add_control(control_name, control)
            self.controls[control_name] = control

        except Exception as e:
            raise ValueError(
                f"Failed to create time control '{control_name}': {e}"
            ) from e

    def add_conditional_control(
        self,
        control_name: str,
        target_element: str,
        target_attribute: str,
        value: t.Any,
        source_element: str,
        source_attribute: str,
        operator: str,
        threshold: float,
    ):
        """Add a conditional control based on element state

        :param control_name: Unique name for the control
            :param target_element: Name of element to control
            target_attribute: Attribute to modify
            value: Value to set
            source_element: Name of element to monitor
            source_attribute: Attribute to monitor
            operator: Comparison operator ('>', '<', '>=', '<=', '=', '!=')
            threshold: Threshold value for comparison
        """
        try:
            # Get the target and source objects
            target = self._get_element(target_element)
            source = self._get_element(source_element)

            # Create the action
            action = wntr.network.controls.ControlAction(
                target, target_attribute, value
            )

            # Map operator strings to WNTR operators
            op_map = {
                ">": ">",
                "<": "<",
                ">=": ">=",
                "<=": "<=",
                "=": "=",
                "==": "=",
                "!=": "!=",
            }
            wntr_op = op_map.get(operator, operator)

            # Create the condition
            condition = wntr.network.controls.ValueCondition(
                source, source_attribute, wntr_op, threshold
            )

            # Create and add the control
            control = wntr.network.controls.Control(condition, action)
            self.wn.add_control(control_name, control)
            self.controls[control_name] = control

        except Exception as e:
            raise ValueError(
                f"Failed to create conditional control '{control_name}': {e}"
            ) from e

    def add_rule(
        self,
        rule_name: str,
        if_conditions: t.List[dict],
        then_actions: t.List[dict],
        else_actions: t.Optional[t.List[dict]] = None,
        priority: int = 3,
    ):
        """Add an if-then-else rule

        :param rule_name: Unique name for the rule
            :param if_conditions: List of condition specifications
            then_actions: List of action specifications
            else_actions: Optional list of else action specifications
            priority: Priority level (0-6, default 3=medium)
        """
        try:
            # Parse conditions
            conditions = []
            for cond_spec in if_conditions:
                condition = self._parse_condition(cond_spec)
                conditions.append(condition)

            # Combine conditions with AND if multiple
            if len(conditions) == 1:
                final_condition = conditions[0]
            else:
                final_condition = conditions[0]
                for cond in conditions[1:]:
                    final_condition = final_condition & cond

            # Parse then actions
            then_action_objs = [self._parse_action(act) for act in then_actions]

            # Parse else actions if provided
            else_action_objs = None
            if else_actions:
                else_action_objs = [self._parse_action(act) for act in else_actions]

            # Create and add the rule
            rule = wntr.network.controls.Rule(
                final_condition, then_action_objs, else_action_objs, priority=priority
            )
            self.wn.add_control(rule_name, rule)
            self.controls[rule_name] = rule

        except Exception as e:
            raise ValueError(f"Failed to create rule '{rule_name}': {e}") from e

    def remove_control(self, control_name: str):
        """Remove a control or rule

        :param control_name: Name of the control to remove
        """
        if control_name in self.wn.control_name_list:
            self.wn.remove_control(control_name)
        if control_name in self.controls:
            del self.controls[control_name]

    def get_all_controls(self) -> t.Dict[str, t.Any]:
        """Get all controls in the model

        :return: Dictionary mapping control names to Control objects
        """
        return {name: self.wn.get_control(name) for name in self.wn.control_name_list}

    def _get_element(self, element_name: str) -> t.Any:
        """Get a network element by name

        :param element_name: Name of the element

        :return: WNTR network element object
        """
        # Try to get as link first, then as node
        try:
            return self.wn.get_link(element_name)
        except KeyError:
            return self.wn.get_node(element_name)

    def _convert_status_value(self, attribute: str, value: t.Any) -> t.Any:
        """Convert status values to WNTR LinkStatus enum

        :param attribute: Attribute name
        :param value: Value to convert

        :return: Converted value (LinkStatus enum for status attributes)
        """
        if attribute == "status":
            if isinstance(value, str):
                value_lower = value.lower()
                if value_lower in ("closed", "close", "0"):
                    return wntr.network.LinkStatus.Closed
                elif value_lower in ("open", "1"):
                    return wntr.network.LinkStatus.Open
                elif value_lower == "active":
                    return wntr.network.LinkStatus.Active
                else:
                    raise ValueError(f"Unknown status value: {value}")
            elif isinstance(value, int):
                if value == 0:
                    return wntr.network.LinkStatus.Closed
                elif value == 1:
                    return wntr.network.LinkStatus.Open
                elif value == 2:
                    return wntr.network.LinkStatus.Active
                else:
                    raise ValueError(f"Unknown status value: {value}")
        return value

    def _parse_condition(self, cond_spec: dict) -> t.Any:
        """Parse a condition specification

        :param cond_spec: Dictionary with condition specification

        :return: WNTR Condition object
        """
        cond_type = cond_spec.get("type", "value")

        if cond_type == "sim_time":
            return wntr.network.controls.SimTimeCondition(
                self.wn, cond_spec.get("operator", "="), cond_spec["value"]
            )
        elif cond_type == "time_of_day":
            return wntr.network.controls.TimeOfDayCondition(
                self.wn, cond_spec.get("operator", "at"), cond_spec["value"]
            )
        elif cond_type == "value":
            element = self._get_element(cond_spec["element"])
            return wntr.network.controls.ValueCondition(
                element,
                cond_spec["attribute"],
                cond_spec.get("operator", "="),
                cond_spec["threshold"],
            )
        else:
            raise ValueError(f"Unknown condition type: {cond_type}")

    def _parse_action(self, act_spec: dict) -> t.Any:
        """Parse an action specification

        :param act_spec: Dictionary with action specification

        :return: WNTR ControlAction object
        """
        element = self._get_element(act_spec["element"])
        return wntr.network.controls.ControlAction(
            element, act_spec["attribute"], act_spec["value"]
        )
