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
from movici_simulation_core.models.udf_model import compiler
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
        return UDF(compiler.compile_func(node), output_attr)

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
    def __init__(self, func, output_attr):
        self.func = func
        self.output = output_attr

    def run(self, inputs: t.Dict[str, AttributeObject]):
        result = self.func(
            {k: (v.array if isinstance(v, UniformAttribute) else v.csr) for k, v in inputs.items()}
        )
        if isinstance(self.output, CSRAttribute):
            self.output.update(result, np.arange(len(self.output)))
        elif isinstance(self.output, UniformAttribute):
            self.output[:] = result


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
