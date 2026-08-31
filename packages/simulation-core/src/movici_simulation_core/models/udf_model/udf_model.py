from __future__ import annotations

import dataclasses
import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import (
    PUB,
    REQUIRED,
    SUB,
    AttributeObject,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.udf_model import compiler, functions
from movici_simulation_core.models.udf_model.result_type import ResultType, Shape
from movici_simulation_core.validate import ModelConfigSchema

MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/udf.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/udf.json"


def convert_v1_v2(config):
    return {
        **config,
        "entity_group": config["entity_group"][0],
        "functions": [
            {
                **func,
                "output": func["output"][1],
            }
            for func in config["functions"]
        ],
        "inputs": {name: attr[1] for name, attr in config["inputs"].items()},
    }


class UDFModel(TrackedModel, name="udf"):
    __model_config_schema__ = [
        ModelConfigSchema(MODEL_CONFIG_SCHEMA_LEGACY_PATH),
        ModelConfigSchema(MODEL_CONFIG_SCHEMA_PATH, convert_from_previous=convert_v1_v2),
    ]
    inputs: t.Dict[str, AttributeObject]
    udfs: t.List[UDF]

    def __init__(self, model_config: dict):
        super().__init__(model_config)

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        self.inputs = get_input_attributes(self.config, state=state, schema=schema)
        prepare_optional_attributes(self.config, self.inputs)
        self.udfs = [
            info.make_udf(state, schema=schema, inputs=self.inputs)
            for info in get_udf_infos(self.config)
        ]

    def update(self, **_):
        self.run_udfs()

    def run_udfs(self):
        for udf in self.udfs:
            udf.run(self.inputs)


@dataclasses.dataclass
class UDFInfo:
    dataset: str
    entity_group: str
    expression: str
    output_attribute: str

    def get_output_attribute(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        replace_sub=True,
        default_data_type: t.Optional[DataType] = None,
    ):
        attr = state.register_attribute(
            self.dataset,
            self.entity_group,
            schema.get_spec(
                self.output_attribute, default_data_type=default_data_type or DataType(float)
            ),
            flags=PUB,
        )
        if replace_sub:
            attr.flags = PUB
        return attr

    def make_udf(
        self,
        state: TrackedState,
        schema: AttributeSchema,
        replace_sub=True,
        inputs: t.Optional[t.Dict[str, AttributeObject]] = None,
    ):
        """Compile the expression and bind it to its output attribute.

        When `inputs` is given, the type and shape of the expression's result are inferred and used
        as the data type of the output attribute, unless the attribute schema already defines one.
        The expression is also checked against the output attribute, so that an expression that can
        never be stored fails here rather than during the simulation.
        """
        node = compiler.parse(compiler.tokenize(self.expression))
        result_type = None
        if inputs is not None:
            result_type = compiler.infer_result_type(node, get_input_result_types(inputs))

        output_attr = self.get_output_attribute(
            state,
            schema,
            replace_sub,
            default_data_type=result_type.as_data_type() if result_type else None,
        )
        if result_type is not None:
            self.check_output_attribute(result_type, output_attr)

        return UDF(
            compiler.compile_func(node),
            output_attr,
            input_names=sorted(compiler.get_vars(node)),
            # a group reduction reads every entity, so a change anywhere changes its result
            incremental=not (compiler.get_funcs(node) & functions.GROUP_REDUCERS),
        )

    def check_output_attribute(self, result_type: ResultType, output_attr: AttributeObject):
        produces_csr = result_type.shape is Shape.CSR
        if produces_csr == output_attr.data_type.csr:
            return
        if produces_csr:
            raise ValueError(
                f"Expression '{self.expression}' produces a variable number of values per entity, "
                f"which cannot be stored in uniform attribute '{self.output_attribute}'"
            )
        raise ValueError(
            f"Expression '{self.expression}' produces a single value per entity, which cannot be "
            f"stored in csr attribute '{self.output_attribute}'"
        )


class UDF:
    """A compiled expression together with the attribute its result is written to.

    An expression is evaluated for the entities whose inputs changed since the previous update,
    rather than for the entire entity group, which for a large entity group with few changes is
    the difference between calculating three values and three hundred thousand. Writing a result
    back is the most expensive part of a udf by some margin, so writing only the entities that
    changed is where most of the saving is.

    Nothing is evaluated at all when none of the inputs received data, which is decided without
    comparing any values and therefore costs nothing. The entity group is evaluated as a whole
    when there is nothing to compare against yet, when the entity group has grown, when so many
    entities changed that selecting them costs more than it saves, or when the expression contains
    a group reduction and therefore depends on every entity.
    """

    incremental_threshold = 0.3
    """The fraction of changed entities above which evaluating the entire entity group is cheaper
    than selecting the changed entities, evaluating those and writing them back. Measured on a
    200.000 entity group, the two are worth about the same somewhere between a third and a half of
    the entities changing, the exact point depending on how much work the expression itself is.
    """

    NOTHING_TO_DO: t.ClassVar[np.ndarray] = np.empty(0, dtype=int)

    def __init__(
        self,
        func,
        output_attr,
        input_names: t.Sequence[str] = (),
        incremental: bool = True,
    ):
        self.func = func
        self.output = output_attr
        self.input_names = tuple(input_names)
        self.incremental = incremental
        self.evaluated_size: t.Optional[int] = None

    def run(self, inputs: t.Dict[str, AttributeObject]):
        indices = self.get_changed_indices(inputs)
        if indices is None:
            self.write(self.func(self.get_values(inputs)))
        elif len(indices):
            self.write(self.func(self.get_values(inputs, indices)), indices)

    def get_changed_indices(self, inputs: t.Dict[str, AttributeObject]) -> t.Optional[np.ndarray]:
        """The entities that need to be recalculated, or `None` when the entire entity group does.
        An empty result means there is nothing to do at all.
        """
        size, evaluated_size = len(self.output), self.evaluated_size
        self.evaluated_size = size
        if evaluated_size != size:
            return None

        # ruling out the inputs that were not written to at all costs nothing, and an update that
        # brings this model no data at all is common enough to be worth checking for first
        touched = [inputs[name] for name in self.input_names if inputs[name].may_have_changes()]
        if not touched:
            return self.NOTHING_TO_DO
        if not self.incremental:
            return None

        # `written` rather than `changed`: recalculating an entity whose input was overwritten
        # with a marginally different value gives the same answer, and asking the cheaper question
        # keeps the saving from being eaten by the cost of finding out
        written = np.zeros(size, dtype=bool)
        for attribute in touched:
            written |= attribute.written

        if np.count_nonzero(written) > size * self.incremental_threshold:
            return None
        return np.flatnonzero(written)

    def get_values(
        self, inputs: t.Dict[str, AttributeObject], indices: t.Optional[np.ndarray] = None
    ) -> dict:
        values = {}
        for name in self.input_names:
            attribute = inputs[name]
            if isinstance(attribute, UniformAttribute):
                # viewing the array as a plain ndarray avoids TrackedArray.__getitem__, which
                # copies the entire array to start tracking changes we are not interested in
                value = np.asarray(attribute.array)
                values[name] = value if indices is None else value[indices]
            else:
                value = attribute.csr
                values[name] = value if indices is None else value.slice(indices)
        return values

    def write(self, result, indices: t.Optional[np.ndarray] = None):
        if isinstance(self.output, CSRAttribute):
            self.output.update(result, np.arange(len(self.output)) if indices is None else indices)
        elif isinstance(self.output, UniformAttribute):
            self.output[slice(None) if indices is None else indices] = result


def get_input_attributes(config: dict, schema: AttributeSchema, state: TrackedState):
    dataset, entity_group = config["entity_group"]
    inputs = config["inputs"]
    return {
        key: state.register_attribute(
            dataset,
            entity_group,
            schema.get_spec(val, default_data_type=DataType(float)),
            flags=SUB,
        )
        for key, val in inputs.items()
    }


def get_input_result_types(inputs: t.Dict[str, AttributeObject]) -> t.Dict[str, ResultType]:
    return {name: ResultType.from_data_type(attr.data_type) for name, attr in inputs.items()}


def prepare_optional_attributes(config, inputs: t.Dict[str, AttributeObject]):
    for attr in config.get("optional", []):
        inputs[attr].flags &= ~REQUIRED  # unset the REQUIRED bit


def get_udf_infos(config):
    dataset, entity_group = config["entity_group"]
    for func in config["functions"]:
        yield UDFInfo(
            dataset=dataset,
            entity_group=entity_group,
            expression=func["expression"],
            output_attribute=func["output"],
        )
