"""Rules Model for conditional attribute updates.

This model updates entity attributes based on conditions defined in
rules datasets or model configuration.
"""

import logging
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timezone

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import OPT, PUB, SUB
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector import InitDataHandler
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from .expression import ParsedCondition, parse_condition

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models" / "rules.json"


@dataclass
class Rule:
    """A single rule that updates a target attribute based on a condition."""

    condition: ParsedCondition
    to_dataset: str  # Required: target dataset
    output: str  # Required: output attribute name
    value: t.Any  # Required: value to set when condition is true
    from_dataset: t.Optional[str] = None
    from_id: t.Optional[int] = None
    from_reference: t.Optional[str] = None
    to_id: t.Optional[int] = None
    to_reference: t.Optional[str] = None
    else_value: t.Any = None

    # Resolved during setup
    from_entity_idx: t.Optional[int] = None
    to_entity_idx: t.Optional[int] = None
    from_entity_group: t.Optional[str] = None
    to_entity_group: t.Optional[str] = None
    output_array: t.Any = None
    source_attributes: dict = field(default_factory=dict)


class RuleValidationError(ValueError):
    """Raised when a rule specification is invalid."""

    pass


def validate_rule_spec(rule_spec: dict, defaults: t.Optional[dict] = None) -> None:
    """Validate a rule specification has all required fields.

    :param rule_spec: Rule specification dict
    :param defaults: Default values for from_dataset, to_dataset
    :raises RuleValidationError: If required fields are missing
    """
    defaults = defaults or {}

    # Required fields
    if "if" not in rule_spec:
        raise RuleValidationError("Rule must have an 'if' condition")
    if "output" not in rule_spec:
        raise RuleValidationError("Rule must have an 'output' attribute")
    if "value" not in rule_spec:
        raise RuleValidationError("Rule must have a 'value'")

    # Must have to_dataset (from spec or defaults)
    to_dataset = rule_spec.get("to_dataset", defaults.get("to_dataset"))
    if not to_dataset:
        raise RuleValidationError("Rule must have a 'to_dataset' (or default)")

    # Must have exactly one of to_id or to_reference
    has_to_id = "to_id" in rule_spec
    has_to_ref = "to_reference" in rule_spec
    if not (has_to_id ^ has_to_ref):
        raise RuleValidationError("Rule must have exactly one of 'to_id' or 'to_reference'")

    # If condition references attributes, must have from_dataset and from entity
    # (This is checked during attribute registration)


def parse_rule(rule_spec: dict, defaults: t.Optional[dict] = None) -> Rule:
    """Parse a rule specification into a Rule object.

    :param rule_spec: Rule specification dict
    :param defaults: Default values for from_dataset, to_dataset
    :returns: Parsed Rule object
    :rtype: Rule
    :raises RuleValidationError: If the rule specification is invalid
    """
    defaults = defaults or {}

    # Validate required fields
    validate_rule_spec(rule_spec, defaults)

    condition = parse_condition(rule_spec["if"])

    # Check if condition needs source attributes
    attr_names = condition.get_attribute_names()
    from_dataset = rule_spec.get("from_dataset", defaults.get("from_dataset"))
    from_id = rule_spec.get("from_id")
    from_reference = rule_spec.get("from_reference")

    # If condition has attributes, validate source entity specification
    if attr_names:
        if not from_dataset:
            raise RuleValidationError(
                f"Rule condition references attributes {attr_names} "
                "but no 'from_dataset' specified"
            )
        if not (from_id is not None) ^ (from_reference is not None):
            raise RuleValidationError(
                "Rule with attribute condition must have exactly one of "
                "'from_id' or 'from_reference'"
            )

    return Rule(
        condition=condition,
        to_dataset=rule_spec.get("to_dataset", defaults.get("to_dataset")),
        output=rule_spec["output"],
        value=rule_spec["value"],
        from_dataset=from_dataset,
        from_id=from_id,
        from_reference=from_reference,
        to_id=rule_spec.get("to_id"),
        to_reference=rule_spec.get("to_reference"),
        else_value=rule_spec.get("else_value"),
    )


class Model(TrackedModel, name="rules"):
    """Model that applies conditional rules to update entity attributes.

    Rules can be defined in the model config or in a separate rules dataset.
    Both sources are merged if both are provided.

    Each rule specifies:

    - A condition (time-based or attribute-based)
    - A target entity (by id or reference)
    - An output attribute and value to set when the condition is true
    - Optionally, an else_value when the condition is false
    """

    def __init__(self, config: dict) -> None:
        config = ensure_valid_config(
            config,
            "1",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_PATH},
            },
        )
        super().__init__(config)
        self.rules: list[Rule] = []
        self.logger: t.Optional[logging.Logger] = None
        self.timeline_info: t.Optional[t.Any] = None
        # Cache for loaded dataset data to avoid repeated reads
        self._dataset_cache: dict[str, dict] = {}

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
        """Load and merge rules from config and/or rules dataset.

        If both config and dataset specify rules, they are merged.
        Config rules take precedence for defaults.

        :param init_data_handler: Handler for loading datasets
        :returns: Rules specification dict with 'defaults' and 'rules' keys
        :rtype: dict
        """
        merged_rules: list = []
        merged_defaults: dict = {}

        # Load from config if present
        if "rules" in self.config:
            merged_rules.extend(self.config["rules"])
            merged_defaults.update(self.config.get("defaults", {}))

        # Load from dataset if present
        if "rules_dataset" in self.config:
            dataset_name = self.config["rules_dataset"]
            _, path = init_data_handler.get(dataset_name)
            if path is None:
                raise ValueError(f"Rules dataset '{dataset_name}' not found")

            data = path.read_dict()

            # Validate dataset type is "rules"
            dataset_type = data.get("type")
            if dataset_type and dataset_type != "rules":
                raise ValueError(
                    f"Rules dataset '{dataset_name}' has type '{dataset_type}', expected 'rules'"
                )

            # Extract rules from data section
            rules_data = data.get("data", {})
            dataset_rules = rules_data.get("rules", [])
            dataset_defaults = rules_data.get("defaults", {})

            # Merge: dataset defaults are overridden by config defaults
            for key, value in dataset_defaults.items():
                if key not in merged_defaults:
                    merged_defaults[key] = value

            merged_rules.extend(dataset_rules)

        return {"rules": merged_rules, "defaults": merged_defaults}

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
                self._register_target_attribute(rule, state, schema, init_data_handler, registered)

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
        entity_group_name, entity_idx = self._find_entity_group(
            rule.from_dataset,
            rule.from_id,
            rule.from_reference,
            init_data_handler,
        )

        if entity_group_name is None:
            entity_desc = f"id={rule.from_id}" if rule.from_id else f"ref='{rule.from_reference}'"
            if self.logger:
                self.logger.warning(
                    f"Could not find entity group for source entity ({entity_desc}) "
                    f"in dataset '{rule.from_dataset}'"
                )
            return

        rule.from_entity_group = entity_group_name
        rule.from_entity_idx = entity_idx
        key = (rule.from_dataset, entity_group_name)

        # Register entity group if not already done
        if key not in registered:
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
                    self.logger.warning(
                        f"Could not register attribute '{attr_name}' in dataset "
                        f"'{rule.from_dataset}', entity group '{entity_group_name}': {e}"
                    )

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
        entity_group_name, entity_idx = self._find_entity_group(
            rule.to_dataset,
            rule.to_id,
            rule.to_reference,
            init_data_handler,
        )

        if entity_group_name is None:
            entity_desc = f"id={rule.to_id}" if rule.to_id else f"ref='{rule.to_reference}'"
            if self.logger:
                self.logger.warning(
                    f"Could not find entity group for target entity ({entity_desc}) "
                    f"in dataset '{rule.to_dataset}'"
                )
            return

        rule.to_entity_group = entity_group_name
        rule.to_entity_idx = entity_idx
        key = (rule.to_dataset, entity_group_name)

        if key not in registered:
            eg = EntityGroup(entity_group_name)
            state.register_entity_group(rule.to_dataset, eg)
            registered[key] = eg

        # Determine output attribute type from value
        # Note: Check bool first since bool is subclass of int in Python
        if isinstance(rule.value, bool):
            dtype = DataType(bool)
        elif isinstance(rule.value, int):
            dtype = DataType(int)
        elif isinstance(rule.value, float):
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
                self.logger.warning(
                    f"Could not register output attribute '{rule.output}' in dataset "
                    f"'{rule.to_dataset}', entity group '{entity_group_name}': {e}"
                )

    def _find_entity_group(
        self,
        dataset: t.Optional[str],
        entity_id: t.Optional[int],
        reference: t.Optional[str],
        init_data_handler: InitDataHandler,
    ) -> tuple[t.Optional[str], t.Optional[int]]:
        """Find which entity group contains a given entity and its index.

        :param dataset: Dataset name
        :param entity_id: Entity ID to find
        :param reference: Entity reference to find
        :param init_data_handler: Handler for loading entity data
        :returns: Tuple of (entity_group_name, entity_index) or (None, None) if not found
        :rtype: tuple[Optional[str], Optional[int]]
        """
        if dataset is None:
            return None, None

        # Validate: must have exactly one of entity_id or reference
        if not ((entity_id is not None) ^ (reference is not None)):
            return None, None

        # Use cached data if available
        if dataset in self._dataset_cache:
            data = self._dataset_cache[dataset]
        else:
            try:
                _, path = init_data_handler.get(dataset)
                if path is None:
                    return None, None
                data = path.read_dict()
                self._dataset_cache[dataset] = data
            except Exception:
                return None, None

        # Search through entity groups in the dataset
        for key, value in data.get("data", {}).items():
            if not isinstance(value, dict):
                continue

            # Check if this entity group contains the entity
            ids = value.get("id", {}).get("data", [])
            references = value.get("reference", {}).get("data", [])

            if entity_id is not None:
                if entity_id in ids:
                    idx = ids.index(entity_id)
                    return key, idx
            elif reference is not None:
                if reference in references:
                    idx = references.index(reference)
                    return key, idx

        return None, None

    def initialize(self, state: TrackedState) -> None:
        """Initialize the model state.

        :param state: TrackedState instance
        """
        # Entity indices are resolved during setup in _find_entity_group
        # Clear dataset cache after setup to free memory
        self._dataset_cache.clear()

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update entity attributes based on rules.

        :param state: TrackedState instance
        :param moment: Current simulation moment
        :returns: Next moment when an update is needed, or None
        :rtype: Optional[Moment]
        """
        # Use Moment.seconds property for simulation time
        simtime = moment.seconds

        # Calculate clocktime (seconds since midnight) from world_time
        clocktime: t.Optional[float] = None
        try:
            # world_time is unix timestamp, convert to datetime
            world_time = moment.world_time
            if world_time is not None:
                dt = datetime.fromtimestamp(world_time, tz=timezone.utc)
                clocktime = float(dt.hour * 3600 + dt.minute * 60 + dt.second)
        except (AttributeError, TypeError, OSError):
            # If world_time not available or invalid, clocktime remains None
            pass

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
                data = attr.array
                if rule.from_entity_idx is None:
                    # Entity index should have been resolved during setup
                    if self.logger:
                        self.logger.warning(
                            f"Source entity index not resolved for attribute '{attr_name}'"
                        )
                    continue
                if rule.from_entity_idx < len(data):
                    attributes[attr_name] = data[rule.from_entity_idx]

        # Evaluate condition
        result = rule.condition.evaluate(
            simtime=simtime,
            clocktime=clocktime,
            attributes=attributes,
        )

        # Apply output value
        if not rule.output_array.is_initialized():
            return

        if rule.to_entity_idx is None:
            # Entity index should have been resolved during setup
            if self.logger:
                self.logger.warning(f"Target entity index not resolved for output '{rule.output}'")
            return

        output_data = rule.output_array.array
        if rule.to_entity_idx >= len(output_data):
            if self.logger:
                self.logger.warning(
                    f"Target entity index {rule.to_entity_idx} out of bounds "
                    f"for output '{rule.output}' (array length: {len(output_data)})"
                )
            return

        if result:
            output_data[rule.to_entity_idx] = rule.value
        elif rule.else_value is not None:
            output_data[rule.to_entity_idx] = rule.else_value
