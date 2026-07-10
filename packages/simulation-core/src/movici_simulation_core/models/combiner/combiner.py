"""A minimal "combiner" solver helper. The canonical worked example from issue #127: two
or more regular models publish the same attribute; the combiner takes ownership at
priority :class:`Priority.SOLVER_HELPER` and reduces the per-publisher internal variants
into a single canonical value using the configured method (``sum``, ``mean``, ``min``,
``max``).

Scope and current limitations:

* Only uniform (dense, one value per entity) attributes are supported. CSR attributes
  (variable-length per entity) are rejected at setup time.
* String attributes are not supported. Boolean attributes support only ``min`` and
  ``max`` (logical AND/OR respectively).
* The input variants are registered as required (``SUB``) subscriptions, so the combiner
  is only updated once **every** registered input variant is fully defined (every entity
  has a value) — partial aggregations are ambiguous (``sum`` would silently drop one
  publisher, ``mean`` would shift) and aggregating an undefined sentinel would produce
  garbage. Until then the combiner emits nothing.
"""

from __future__ import annotations

import dataclasses
import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import PUB, SUB, UniformAttribute
from movici_simulation_core.core.attribute_spec import AttributeSpec
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.messages import RemapMessage
from movici_simulation_core.types import AutoRemap, Priority

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/combiner.json"

_METHODS: t.Dict[str, t.Callable[[np.ndarray], np.ndarray]] = {
    "sum": lambda stacked: np.sum(stacked, axis=0),
    "mean": lambda stacked: np.mean(stacked, axis=0),
    "min": lambda stacked: np.min(stacked, axis=0),
    "max": lambda stacked: np.max(stacked, axis=0),
}
_BOOL_METHODS = ("min", "max")


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

    __model_config_schema__ = MODEL_CONFIG_SCHEMA_PATH

    priority = int(Priority.SOLVER_HELPER)

    state: t.Optional[TrackedState] = None
    schema: t.Optional[AttributeSchema] = None
    output: t.Optional[UniformAttribute] = None
    inputs: t.List[UniformAttribute]

    def __init__(self, model_config: dict, validate_config=True):
        super().__init__(model_config, validate_config)
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
        self._validate_output_spec(spec)
        self._spec = spec
        self.output = state.register_attribute(
            attribute["dataset"], attribute["entity_group"], spec, flags=PUB
        )

    def _validate_output_spec(self, spec: AttributeSpec):
        data_type = spec.data_type
        if data_type.csr:
            raise ValueError(
                f"combiner does not support CSR (variable-length) attributes: '{spec.name}'"
            )
        if data_type.py_type is str:
            raise ValueError(f"combiner does not support string attributes: '{spec.name}'")
        if data_type.py_type is bool and self._method not in _BOOL_METHODS:
            raise ValueError(
                f"combiner: method '{self._method}' is not supported for boolean attribute "
                f"'{spec.name}'. Choose one of: {sorted(_BOOL_METHODS)}"
            )

    def initialize(self, state: TrackedState):
        # The combiner does not need any data to be ready at initialization — it produces
        # its first value once the other publishers have published their variants.
        return

    def update(self, state: TrackedState, **_):
        if not self.inputs:
            return None
        # The inputs are registered as SUB (required): the adapter only calls update()
        # once every input variant is fully defined, so no undefined handling is needed
        # here.
        stacked = np.stack([attr.array for attr in self.inputs])
        combined = _METHODS[self._method](stacked)
        if np.issubdtype(self.output.array.dtype, np.integer) and np.issubdtype(
            combined.dtype, np.floating
        ):
            # e.g. the mean of integer inputs; round rather than truncate
            combined = np.rint(combined)
        self.output.array[:] = combined
        return None

    def remap(self, payload: RemapMessage) -> AutoRemap:
        """Register the internal-variant attributes the orchestrator instructs us to
        subscribe to as required (``SUB``) inputs. The variants are, by definition, the
        same quantity as the canonical output under a different wire name, so they reuse
        the output attribute's spec. Identity entries (``{canonical: canonical}``,
        back-propagation) are not inputs and are skipped.

        Returns ``AutoRemap(pub=True, sub=False)``: outgoing publications may be renamed
        transparently by the connector, but the incoming many-to-one variant mapping is
        handled by this model itself."""
        sub = payload.sub
        if sub is None:
            return AutoRemap.default()
        for ds, entity_groups in sub.items():
            for eg, mapping in entity_groups.items():
                for variant, original in mapping.items():
                    if variant == original:
                        continue
                    spec = dataclasses.replace(self._spec, name=variant)
                    attr = self.state.register_attribute(ds, eg, spec, flags=SUB)
                    self.inputs.append(attr)
        return AutoRemap(pub=True, sub=False)
