"""Rules Model for conditional attribute updates.

This model updates entity attributes based on conditions defined in
rules datasets or model configuration.
"""

from __future__ import annotations

import logging
import typing as t
from dataclasses import dataclass

from movici_simulation_core import UniformAttribute
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import OPT, PUB, SUB
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.model_connector import InitDataHandler
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from .expression import ExpressionType, ParsedCondition, parse_condition

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models" / "rules.json"


@dataclass
class RuleSpec:
    condition: str  # Required: raw "if" condition
    output: str  # Required: output attribute name
    value: bool | int | float | str | None  # Required: value to set when condition is true
    to_dataset: t.Optional[str] = None
    from_dataset: t.Optional[str] = None
    from_id: t.Optional[int] = None
    from_reference: t.Optional[str] = None
    to_id: t.Optional[int] = None
    to_reference: t.Optional[str] = None
    else_value: t.Any = None


@dataclass
class Rule:
    """A single rule that updates a target attribute based on a condition."""

    condition: ParsedCondition
    output: str  # Required: output attribute name
    value: bool | int | float | str  # Required: value to set when condition is true
    else_value: bool | int | float | str | None

    to_entity_idx: int
    output_array: UniformAttribute

    from_entity_idx: t.Optional[int]
    source_attributes: dict[str, UniformAttribute]

    @classmethod
    def from_spec(
        self,
        spec: RuleSpec,
        reference_indices: dict[str, DatasetReferenceIndex],
        state: TrackedState,
        schema: AttributeSchema,
    ):
        if not spec.to_dataset:
            raise RuleValidationError("Rule must have a 'to_dataset'")
        if not spec.condition:
            raise RuleValidationError("Rule must have a 'if' condition")
        if spec.value is None:
            raise RuleValidationError("Rule must have an output value")

        condition = parse_condition(spec.condition)

        # If condition has attributes, validate source entity specification
        attr_names = condition.get_attribute_names()
        source_attributes: dict[str, UniformAttribute] = {}
        from_idx = None
        if attr_names:
            if not spec.from_dataset:
                raise RuleValidationError(
                    f"Rule condition references attributes {attr_names} "
                    "but no 'from_dataset' specified"
                )
            if not (spec.from_id is not None) ^ (spec.from_reference is not None):
                raise RuleValidationError(
                    "Rule with attribute condition must have exactly one of "
                    "'from_id' or 'from_reference'"
                )
            from_entity_group, from_idx = self._get_entity_idx_or_raise(
                spec.from_dataset, spec.from_id, spec.from_reference, reference_indices
            )

            # Register each attribute (register_attribute auto-creates the entity group entry)
            for attr_name in attr_names:
                attr_spec = schema.get_spec(attr_name, DataType(float))
                attr = state.register_attribute(
                    spec.from_dataset, from_entity_group, attr_spec, flags=SUB | OPT
                )
                source_attributes[attr_name] = t.cast(UniformAttribute, attr)

        to_entity_group, to_idx = self._get_entity_idx_or_raise(
            spec.to_dataset, spec.to_id, spec.to_reference, reference_indices
        )
        attr_spec = schema.get_spec(spec.output, DataType(type(spec.value)))
        target_array = t.cast(
            UniformAttribute,
            state.register_attribute(spec.to_dataset, to_entity_group, spec=attr_spec, flags=PUB),
        )

        return Rule(
            condition=condition,
            output=spec.output,
            value=spec.value,
            else_value=spec.else_value,
            from_entity_idx=from_idx,
            source_attributes=source_attributes,
            to_entity_idx=to_idx,
            output_array=target_array,
        )

    @staticmethod
    def _get_entity_idx_or_raise(
        dataset: str,
        entity_id: int | None,
        reference: str | None,
        reference_indices: dict[str, DatasetReferenceIndex],
    ) -> tuple[str, int]:
        ref_idx = reference_indices[dataset]
        idx = None
        if reference is not None:
            entity_group, idx = ref_idx.get_entity_idx_by_reference(reference)
            if idx is None or entity_group is None:
                raise RuleValidationError(f"Reference {reference} not found in dataset {dataset}")
            return entity_group, idx
        elif entity_id is not None:
            entity_group, idx = ref_idx.get_entity_idx_by_id(entity_id)
            if idx is None or entity_group is None:
                raise ValueError(f"ID {entity_id} not found in dataset {dataset}")
            return entity_group, idx
        raise RuleValidationError(
            f"Cannot find entity in dataset {dataset} without ID or reference"
        )


@dataclass
class DatasetReferenceIndex:
    ids: dict[str, dict[int, int]]  # dict[entity_group, dict[id, idx]]
    references: dict[str, dict[str, int]]  # dict[entity_group, dict[reference, idx]]

    def get_entity_idx_by_reference(self, ref: str) -> tuple[str, int] | tuple[None, None]:
        """Retrieve location of an entity by reference
        :param ref: an entity reference

        :return: A tuple (entity group name, entity_idx)
        """
        for entity_group, refs in self.references.items():
            if ref in refs:
                return entity_group, refs[ref]
        return None, None

    def get_entity_idx_by_id(self, entity_id: int) -> tuple[str, int] | tuple[None, None]:
        """Retrieve location of an entity id
        :param entity_id: an entity id

        :return: A tuple (entity group name, entity_idx)
        """
        for entity_group, ids in self.ids.items():
            if entity_id in ids:
                return entity_group, ids[entity_id]
        return None, None


class RuleValidationError(ValueError):
    """Raised when a rule specification is invalid."""

    pass


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
        self.timeline_info: t.Optional[t.Any] = None
        self._simtime_thresholds: list[float] = []
        self._clocktime_thresholds: list[float] = []
        # Cache for loaded dataset data to avoid repeated reads

    def setup(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        settings: Settings,
        init_data_handler: InitDataHandler,
        logger: logging.Logger,
        **__: t.Any,
    ) -> None:
        """Set up the model with state and schema.

        :param state: TrackedState instance for managing entity data
        :param schema: AttributeSchema for attribute registration
        :param settings: Global settings
        :param init_data_handler: Handler for initial data loading
        :param logger: Logger instance
        """
        self.timeline_info = settings.timeline_info

        # Parse rules from config or load from rules dataset
        rule_specs = self._load_rule_specs(init_data_handler)
        reference_indices = self._get_dataset_reference_indices(rule_specs, init_data_handler)
        self.rules = [
            Rule.from_spec(spec, reference_indices=reference_indices, state=state, schema=schema)
            for spec in rule_specs
        ]

        # Pre-compute time thresholds from all rule conditions
        for rule in self.rules:
            for expr_type, value in rule.condition.get_time_thresholds():
                if expr_type == ExpressionType.SIMTIME:
                    self._simtime_thresholds.append(value)
                elif expr_type == ExpressionType.CLOCKTIME:
                    self._clocktime_thresholds.append(value)

    def _get_dataset_reference_indices(
        self, rules: t.Iterable[RuleSpec], init_data_handler: InitDataHandler
    ) -> dict[str, DatasetReferenceIndex]:
        result = {}
        for rule in rules:
            for dataset in (rule.from_dataset, rule.to_dataset):
                if dataset is None or dataset in result:
                    continue
                result[dataset] = self._get_dataset_reference_index(dataset, init_data_handler)

        return result

    def _get_dataset_reference_index(self, dataset_name: str, init_data_handler: InitDataHandler):
        _, path = init_data_handler.get(dataset_name)
        if path is None:
            raise ValueError(f"Dataset '{dataset_name}' not found")

        dataset = path.read_dict()
        references: dict[str, dict[str, int]] = {}
        entity_ids: dict[str, dict[int, int]] = {}
        for entity_group, attributes in dataset.get("data", {}).items():
            ids = attributes["id"]["data"]
            reference_array = attributes["reference"]["data"] if "reference" in attributes else []
            references[entity_group] = {str(ref): idx for idx, ref in enumerate(reference_array)}
            entity_ids[entity_group] = {int(id): idx for idx, id in enumerate(ids)}

        return DatasetReferenceIndex(entity_ids, references)

    def _load_rule_specs(self, init_data_handler: InitDataHandler) -> list[RuleSpec]:
        """Load and merge rules from config and/or rules dataset.

        If both config and dataset specify rules, they are merged.
        Config rules take precedence for defaults.

        :param init_data_handler: Handler for loading datasets
        :returns: Rules specification dict with 'defaults' and 'rules' keys
        :rtype: dict
        """
        merged_rules: list = []
        merged_defaults: dict = {}

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

            merged_rules.extend(dataset_rules)
            merged_defaults.update(dataset_defaults)

        # Load from config if present
        if "rules" in self.config:
            merged_rules.extend(self.config["rules"])
            merged_defaults.update(self.config.get("defaults", {}))

        return [
            RuleSpec(
                condition=spec.get("if", ""),
                to_dataset=spec.get("to_dataset", merged_defaults.get("to_dataset")),
                output=spec.get("output", ""),
                value=spec.get("value"),
                from_dataset=spec.get("from_dataset", merged_defaults.get("from_dataset")),
                from_id=spec.get("from_id"),
                from_reference=spec.get("from_reference"),
                to_id=spec.get("to_id"),
                to_reference=spec.get("to_reference"),
                else_value=spec.get("else_value"),
            )
            for spec in merged_rules
        ]

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        """Update entity attributes based on rules.

        :param state: TrackedState instance
        :param moment: Current simulation moment
        :returns: Next moment when an update is needed, or None
        :rtype: Optional[Moment]
        """
        simtime = moment.seconds

        clocktime: t.Optional[float] = None
        dt = moment.datetime
        if dt is not None:
            clocktime = float(dt.hour * 3600 + dt.minute * 60 + dt.second)

        for rule in self.rules:
            self._evaluate_rule(rule, simtime, clocktime)

        return self._next_trigger(simtime, clocktime)

    def _evaluate_rule(
        self,
        rule: Rule,
        simtime: float,
        clocktime: t.Optional[float],
    ) -> None:
        """Evaluate a single rule and apply its output.

        :param rule: Rule to evaluate
        :param simtime: Simulation time in seconds
        :param clocktime: Clock time in seconds since midnight
        """
        # Gather source attribute values; skip rule if any are undefined
        attributes: dict[str, t.Any] = {}
        for attr_name, attr in rule.source_attributes.items():
            if not attr.has_data():
                return
            attributes[attr_name] = attr.array[rule.from_entity_idx]

        # Evaluate condition
        result = rule.condition.evaluate(
            simtime=simtime,
            clocktime=clocktime,
            attributes=attributes,
        )

        # Apply output value
        output_data = rule.output_array.array
        if result:
            output_data[rule.to_entity_idx] = rule.value
        elif rule.else_value is not None:
            output_data[rule.to_entity_idx] = rule.else_value

    def _next_trigger(
        self,
        simtime: float,
        clocktime: t.Optional[float],
    ) -> t.Optional[Moment]:
        """Compute the next Moment when a time-based condition would trigger.

        :param simtime: Current simulation time in seconds
        :param clocktime: Current clock time in seconds since midnight
        :returns: Next trigger Moment, or None if no time thresholds
        :rtype: Optional[Moment]
        """
        candidates: list[float] = []

        # Next simtime threshold strictly greater than current simtime
        future_simtimes = [th for th in self._simtime_thresholds if th > simtime]
        if future_simtimes:
            candidates.append(min(future_simtimes))

        # Next clocktime threshold, converted to simtime
        if clocktime is not None and self._clocktime_thresholds:
            future_clocks = [th for th in self._clocktime_thresholds if th > clocktime]
            if future_clocks:
                delta = min(future_clocks) - clocktime
            else:
                # Wrap to next day
                delta = (86400 - clocktime) + min(self._clocktime_thresholds)
            candidates.append(simtime + delta)

        if not candidates:
            return None
        return Moment.from_seconds(min(candidates), self.timeline_info)
