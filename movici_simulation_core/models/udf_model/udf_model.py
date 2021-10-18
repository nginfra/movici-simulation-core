from __future__ import annotations

import dataclasses
import typing as t

import numpy as np

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.property import (
    SUB,
    PUB,
    PropertyObject,
    UniformProperty,
    CSRProperty,
)
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.udf_model import compiler


class UDFModel(TrackedModel, name="udf"):
    inputs: t.Dict[str, PropertyObject]
    udfs: t.List[UDF]

    def setup(self, state: TrackedState, schema: AttributeSchema, **_):
        self.inputs = get_input_attributes(self.config, state=state, schema=schema)
        self.udfs = [info.make_udf(state, schema=schema) for info in get_udf_infos(self.config)]

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
    output_component: t.Optional[str] = None

    def get_output_attribute(self, state: TrackedState, schema: AttributeSchema, replace_sub=True):
        prop = state.register_property(
            self.dataset,
            self.entity_group,
            schema.get_spec(
                (self.output_component, self.output_attribute), default_data_type=DataType(float)
            ),
            flags=PUB,
        )
        if replace_sub:
            prop.flags = PUB
        return prop

    def make_udf(self, state: TrackedState, schema: AttributeSchema, replace_sub=True):
        func = compiler.compile(self.expression)
        output_attr = self.get_output_attribute(state, schema, replace_sub)
        return UDF(func, output_attr)


class UDF:
    def __init__(self, func, output_attr):
        self.func = func
        self.output = output_attr

    def run(self, inputs: t.Dict[str, PropertyObject]):
        result = self.func(
            {k: (v.array if isinstance(v, UniformProperty) else v.csr) for k, v in inputs.items()}
        )
        if isinstance(self.output, CSRProperty):
            self.output.update(result, np.arange(len(self.output)))
        elif isinstance(self.output, UniformProperty):
            self.output[:] = result


def get_input_attributes(config: dict, schema: AttributeSchema, state: TrackedState):
    dataset, entity_group = config["entity_group"][0]
    inputs = config["inputs"]
    return {
        key: state.register_property(
            dataset,
            entity_group,
            schema.get_spec(val, default_data_type=DataType(float)),
            flags=SUB,
        )
        for key, val in inputs.items()
    }


def get_udf_infos(config):
    dataset, entity_group = config["entity_group"][0]
    for func in config["functions"]:
        yield UDFInfo(
            dataset=dataset,
            entity_group=entity_group,
            expression=func["expression"],
            output_component=func["output"][0],
            output_attribute=func["output"][1],
        )
