"""A minimal "combiner" solver helper. The canonical worked example from issue #127: two
or more regular models publish the same attribute; the combiner takes ownership at
priority :class:`Priority.SOLVER_HELPER` and reduces the per-publisher internal variants
into a single canonical value using the configured method (``sum``, ``mean``, ``min``,
``max``).

Scope and current limitations:

* Only :class:`UniformAttribute` (dense, one value per entity) inputs are supported. CSR
  attributes (variable-length per entity) raise at remap time with a clear error.
* The combiner only emits a canonical value once **every** registered input variant has
  data — partial aggregations are ambiguous (``sum`` would silently drop one publisher,
  ``mean`` would shift) so the combiner waits for the last input to publish before
  emitting.
"""

from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import (
    OPT,
    PUB,
    AttributeObject,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.core.priority import Priority
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState

_METHODS: t.Dict[str, t.Callable[[np.ndarray], np.ndarray]] = {
    "sum": lambda stacked: np.sum(stacked, axis=0),
    "mean": lambda stacked: np.mean(stacked, axis=0),
    "min": lambda stacked: np.min(stacked, axis=0),
    "max": lambda stacked: np.max(stacked, axis=0),
}


class Combiner(TrackedModel, name="combiner"):
    """Combine multiple internal variants of an attribute into the canonical value. See
    issue #127.

    Configuration:

    .. code-block:: json

        {
            "name": "combiner_demand",
            "type": "combiner",
            "attribute": {
                "dataset": "the_dataset",
                "entity_group": "the_entities",
                "name": "cargo_demand"
            },
            "method": "sum"
        }
    """

    priority = int(Priority.SOLVER_HELPER)

    state: t.Optional[TrackedState] = None
    schema: t.Optional[AttributeSchema] = None
    output: t.Optional[AttributeObject] = None
    inputs: t.List[AttributeObject]

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        method = self.config.get("method", "sum")
        if method not in _METHODS:
            raise ValueError(
                f"combiner: unsupported method '{method}'. Choose one of: {sorted(_METHODS)}"
            )
        self._method = method
        self.inputs = []

    def setup(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        **_,
    ):
        self.state = state
        self.schema = schema
        attribute = self.config["attribute"]
        spec = schema.get_spec(attribute["name"], default_data_type=DataType(float))
        self.output = state.register_attribute(
            attribute["dataset"], attribute["entity_group"], spec, flags=PUB
        )

    def initialize(self, state: TrackedState):
        # The combiner does not need any data to be ready at initialization — it produces
        # its first value once subscribers have published their variants.
        return

    def update(self, state: TrackedState, **_):
        if not self.inputs:
            return None
        # Refuse to emit until every input has published — see the module docstring on
        # partial-aggregation ambiguity.
        if not all(attr.has_data() for attr in self.inputs):
            return None
        stacked = np.stack([attr.array for attr in self.inputs])
        combined = _METHODS[self._method](stacked)
        if not isinstance(self.output, UniformAttribute):
            return None
        if not self.output.has_data():
            # The output's backing array tracks the entity-group length, which is set when
            # any update touches the group. By the time we have data on every input we are
            # guaranteed the entity count, so initialise the output to match.
            self.output.initialize(len(combined))
        elif np.array_equal(self.output.array, combined):
            return None
        self.output.array[:] = combined
        return None

    def remap(self, payload: dict) -> t.Optional[bool]:
        """Register the internal-variant attribute fields the orchestrator instructs us to
        subscribe to. We return ``False`` so the adapter still installs the rest of the
        REMAP plumbing (pub-side, sub-side if it were one-to-one), but the connector will
        skip the sub-rename middleware on its own because the sub remap is many-to-one."""
        sub = payload.get("sub") or {}
        for ds, entity_groups in sub.items():
            for eg, mapping in entity_groups.items():
                for variant in mapping.keys():
                    spec = self.schema.get_spec(variant, default_data_type=DataType(float))
                    attr = self.state.register_attribute(ds, eg, spec, flags=OPT)
                    if isinstance(attr, CSRAttribute):
                        raise ValueError(
                            "combiner does not support CSR (variable-length) attributes. "
                            f"Found CSR variant at '{ds}/{eg}/{variant}'."
                        )
                    self.inputs.append(attr)
        return False
