"""Rules Model for conditional attribute updates.

This model updates entity attributes based on conditions defined in
rules datasets or model configuration.
"""

import logging
import typing as t
from dataclasses import dataclass, field

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import OPT, PUB, SUB
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.model_connector import InitDataHandler
from movici_simulation_core.settings import Settings

from .condition import Condition, parse_rule_condition


@dataclass
class Rule:
    """A single rule that updates a target attribute based on a condition."""

    condition: Condition
    from_dataset: t.Optional[str] = None
    from_id: t.Optional[int] = None
    from_reference: t.Optional[str] = None
    to_dataset: t.Optional[str] = None
    to_id: t.Optional[int] = None
    to_reference: t.Optional[str] = None
    output: str = ""
    value: t.Any = None
    else_value: t.Any = None

    # Resolved during setup
    from_entity_idx: t.Optional[int] = None
    to_entity_idx: t.Optional[int] = None
    from_entity_group: t.Optional[str] = None
    to_entity_group: t.Optional[str] = None
    output_array: t.Any = None
    source_attributes: dict = field(default_factory=dict)


def parse_rule(rule_spec: dict, defaults: t.Optional[dict] = None) -> Rule:
    """Parse a rule specification into a Rule object.

    :param rule_spec: Rule specification dict
    :param defaults: Default values for from_dataset, to_dataset
    :returns: Parsed Rule object
    :rtype: Rule
    """
    defaults = defaults or {}

    condition = parse_rule_condition(rule_spec["if"])

    return Rule(
        condition=condition,
        from_dataset=rule_spec.get("from_dataset", defaults.get("from_dataset")),
        from_id=rule_spec.get("from_id"),
        from_reference=rule_spec.get("from_reference"),
        to_dataset=rule_spec.get("to_dataset", defaults.get("to_dataset")),
        to_id=rule_spec.get("to_id"),
        to_reference=rule_spec.get("to_reference"),
        output=rule_spec["output"],
        value=rule_spec["value"],
        else_value=rule_spec.get("else_value"),
    )


class Model(TrackedModel, name="rules"):
    """Model that applies conditional rules to update entity attributes.

    Rules can be defined in the model config or in a separate rules dataset.
    Each rule specifies:

    - A condition (time-based or attribute-based)
    - A target entity (by id or reference)
    - An output attribute and value to set when the condition is true
    - Optionally, an else_value when the condition is false
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.rules: list[Rule] = []
        self.logger: t.Optional[logging.Logger] = None
        self.timeline_info: t.Optional[t.Any] = None

    def setup(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        settings: Settings,
        init_data_handler: InitDataHandler,
        logger: logging.Logger,
        **_: t.Any,
    ) -> None:
        """Set up the model with state and schema.

        :param state: TrackedState instance for managing entity data
        :param schema: AttributeSchema for attribute registration
        :param settings: Global settings
        :param init_data_handler: Handler for initial data loading
        :param logger: Logger instance
        """
        self.logger = logger
        self.timeline_info = settings.timeline_info

        # Parse rules from config or load from rules dataset
        rules_spec = self._load_rules(init_data_handler)
        defaults = rules_spec.get("defaults", {})

        for rule_spec in rules_spec.get("rules", []):
            rule = parse_rule(rule_spec, defaults)
            self.rules.append(rule)

        # Register attributes for each rule
        self._register_rule_attributes(state, schema, init_data_handler)

    def _load_rules(self, init_data_handler: InitDataHandler) -> dict:
        """Load rules from config or rules dataset.

        :param init_data_handler: Handler for loading datasets
        :returns: Rules specification dict with 'defaults' and 'rules' keys
        :rtype: dict
        """
        if "rules" in self.config:
            return {"rules": self.config["rules"], "defaults": self.config.get("defaults", {})}

        if "rules_dataset" in self.config:
            dataset_name = self.config["rules_dataset"]
            _, path = init_data_handler.get(dataset_name)
            if path is None:
                raise ValueError(f"Rules dataset '{dataset_name}' not found")
            data = path.read_dict()
            return data.get("data", {})

        return {"rules": [], "defaults": {}}

    def _register_rule_attributes(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
    ) -> None:
        """Register source and target attributes for all rules.

        :param state: TrackedState instance
        :param schema: AttributeSchema for attribute specs
        :param init_data_handler: Handler for loading entity data
        """
        # Track registered datasets/entity groups
        registered: dict[tuple[str, str], t.Any] = {}

        for rule in self.rules:
            # Register source attributes if needed
            attr_names = rule.condition.get_attribute_names()
            if attr_names and rule.from_dataset:
                self._register_source_attributes(
                    rule, attr_names, state, schema, init_data_handler, registered
                )

            # Register target attribute
            if rule.to_dataset and rule.output:
                self._register_target_attribute(
                    rule, state, schema, init_data_handler, registered
                )

    def _register_source_attributes(
        self,
        rule: Rule,
        attr_names: set[str],
        state: TrackedState,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        registered: dict,
    ) -> None:
        """Register source attributes for a rule's condition.

        :param rule: The rule being processed
        :param attr_names: Set of attribute names referenced in the condition
        :param state: TrackedState instance
        :param schema: AttributeSchema
        :param init_data_handler: Handler for loading entity data
        :param registered: Dict tracking registered entity groups
        """
        # Find which entity group contains the source entity
        entity_group_name = self._find_entity_group(
            rule.from_dataset,
            rule.from_id,
            rule.from_reference,
            init_data_handler,
        )

        if entity_group_name is None:
            if self.logger:
                self.logger.warning(
                    f"Could not find entity group for source entity in rule"
                )
            return

        rule.from_entity_group = entity_group_name
        key = (rule.from_dataset, entity_group_name)

        # Register entity group if not already done
        if key not in registered:
            from movici_simulation_core.core.entity_group import EntityGroup

            eg = EntityGroup(entity_group_name)
            state.register_entity_group(rule.from_dataset, eg)
            registered[key] = eg

        # Register each attribute
        for attr_name in attr_names:
            try:
                attr_spec = schema.get_spec(attr_name, DataType(float))
                attr = state.register_attribute(
                    rule.from_dataset,
                    entity_group_name,
                    attr_spec,
                    flags=SUB | OPT,
                )
                rule.source_attributes[attr_name] = attr
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not register attribute {attr_name}: {e}")

    def _register_target_attribute(
        self,
        rule: Rule,
        state: TrackedState,
        schema: AttributeSchema,
        init_data_handler: InitDataHandler,
        registered: dict,
    ) -> None:
        """Register target attribute for a rule's output.

        :param rule: The rule being processed
        :param state: TrackedState instance
        :param schema: AttributeSchema
        :param init_data_handler: Handler for loading entity data
        :param registered: Dict tracking registered entity groups
        """
        entity_group_name = self._find_entity_group(
            rule.to_dataset,
            rule.to_id,
            rule.to_reference,
            init_data_handler,
        )

        if entity_group_name is None:
            if self.logger:
                self.logger.warning(
                    f"Could not find entity group for target entity in rule"
                )
            return

        rule.to_entity_group = entity_group_name
        key = (rule.to_dataset, entity_group_name)

        if key not in registered:
            from movici_simulation_core.core.entity_group import EntityGroup

            eg = EntityGroup(entity_group_name)
            state.register_entity_group(rule.to_dataset, eg)
            registered[key] = eg

        # Determine output attribute type from value
        value_type = type(rule.value)
        if value_type == bool:
            dtype = DataType(bool)
        elif value_type == int:
            dtype = DataType(int)
        elif value_type == float:
            dtype = DataType(float)
        else:
            dtype = DataType(float)

        try:
            attr_spec = schema.get_spec(rule.output, dtype)
            rule.output_array = state.register_attribute(
                rule.to_dataset,
                entity_group_name,
                attr_spec,
                flags=PUB,
            )
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Could not register output attribute {rule.output}: {e}")

    def _find_entity_group(
        self,
        dataset: t.Optional[str],
        entity_id: t.Optional[int],
        reference: t.Optional[str],
        init_data_handler: InitDataHandler,
    ) -> t.Optional[str]:
        """Find which entity group contains a given entity.

        :param dataset: Dataset name
        :param entity_id: Entity ID to find
        :param reference: Entity reference to find
        :param init_data_handler: Handler for loading entity data
        :returns: Entity group name or None if not found
        :rtype: Optional[str]
        """
        if dataset is None:
            return None

        try:
            _, path = init_data_handler.get(dataset)
            if path is None:
                return None
            data = path.read_dict()
        except Exception:
            return None

        # Search through entity groups in the dataset
        for key, value in data.get("data", {}).items():
            if not isinstance(value, dict):
                continue

            # Check if this entity group contains the entity
            ids = value.get("id", {}).get("data", [])
            references = value.get("reference", {}).get("data", [])

            if entity_id is not None and entity_id in ids:
                return key
            if reference is not None and reference in references:
                return key

        # If not found in data, check general section
        general = data.get("general", {})
        if entity_id is not None:
            for key, value in data.get("data", {}).items():
                if isinstance(value, dict):
                    return key  # Return first entity group as fallback

        return None

    def initialize(self, state: TrackedState) -> None:
        """Initialize the model state.

        :param state: TrackedState instance
        """
        # Resolve entity indices for rules
        for rule in self.rules:
            self._resolve_entity_index(rule, state)

    def _resolve_entity_index(self, rule: Rule, state: TrackedState) -> None:
        """Resolve entity ID/reference to array index.

        :param rule: Rule to resolve
        :param state: TrackedState instance
        """
        # This would need access to the entity ID/reference arrays
        # For now, we'll resolve during update if needed
        pass

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update entity attributes based on rules.

        :param state: TrackedState instance
        :param moment: Current simulation moment
        :returns: Next moment when an update is needed, or None
        :rtype: Optional[Moment]
        """
        simtime = float(moment.timestamp)

        # Calculate clocktime (seconds since midnight)
        clocktime = None
        if self.timeline_info is not None:
            # Get reference time and calculate clock time
            ref_time = getattr(self.timeline_info, "reference", None)
            if ref_time is not None:
                from datetime import datetime, timedelta

                current_time = ref_time + timedelta(seconds=simtime)
                clocktime = (
                    current_time.hour * 3600
                    + current_time.minute * 60
                    + current_time.second
                )

        for rule in self.rules:
            self._evaluate_rule(rule, state, simtime, clocktime)

        return None

    def _evaluate_rule(
        self,
        rule: Rule,
        state: TrackedState,
        simtime: float,
        clocktime: t.Optional[float],
    ) -> None:
        """Evaluate a single rule and apply its output.

        :param rule: Rule to evaluate
        :param state: TrackedState instance
        :param simtime: Simulation time in seconds
        :param clocktime: Clock time in seconds since midnight
        """
        if rule.output_array is None:
            return

        # Gather source attribute values
        attributes: dict[str, t.Any] = {}
        for attr_name, attr in rule.source_attributes.items():
            if attr is not None and attr.is_initialized():
                # Get value for the specific source entity
                # For now, get first value if index not resolved
                data = attr.array
                if len(data) > 0:
                    idx = rule.from_entity_idx if rule.from_entity_idx is not None else 0
                    if idx < len(data):
                        attributes[attr_name] = data[idx]

        # Evaluate condition
        result = rule.condition.evaluate(
            simtime=simtime,
            clocktime=clocktime,
            attributes=attributes,
        )

        # Apply output value
        if rule.output_array.is_initialized():
            idx = rule.to_entity_idx if rule.to_entity_idx is not None else 0
            output_data = rule.output_array.array
            if idx < len(output_data):
                if result:
                    output_data[idx] = rule.value
                elif rule.else_value is not None:
                    output_data[idx] = rule.else_value
