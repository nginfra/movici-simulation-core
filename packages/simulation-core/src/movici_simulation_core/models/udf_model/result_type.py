"""The type of a udf expression's result.

Every expression produces values of a certain python type, with a certain shape. Inferring these
before the simulation runs makes it possible to give the output attribute of a udf the data type
that the expression actually produces, and to reject an expression that can never be written to
its output attribute, instead of failing halfway through a simulation.

A result type may be partially unknown: a function without a registered type rule produces a
result of an unknown python type. Unknown parts propagate, and the caller falls back on a default
rather than treating it as an error.
"""

from __future__ import annotations

import dataclasses
import enum
import typing as t

from movici_simulation_core.core.data_type import DataType


class Shape(enum.Enum):
    """The shape of an expression result relative to the entities of an entity group"""

    SCALAR = "scalar"
    """A single value for the entire entity group, broadcast over the entities"""

    UNIFORM = "uniform"
    """One value per entity"""

    CSR = "csr"
    """A variable number of values per entity"""


# a value of a type earlier in this sequence can always be represented by a type later in it
PROMOTION_ORDER = (bool, int, float)


@dataclasses.dataclass(frozen=True)
class ResultType:
    py_type: t.Optional[t.Type] = None
    """`bool`, `int` or `float`, or `None` when the python type cannot be determined"""

    shape: Shape = Shape.UNIFORM
    unit_shape: t.Tuple[int, ...] = ()

    @classmethod
    def from_data_type(cls, data_type: DataType) -> ResultType:
        return cls(
            py_type=data_type.py_type,
            shape=Shape.CSR if data_type.csr else Shape.UNIFORM,
            unit_shape=data_type.unit_shape,
        )

    def as_data_type(self, default_py_type: t.Type = float) -> DataType:
        """The data type an output attribute needs to hold this result. A scalar result is
        broadcast over the entities, so it needs a uniform attribute just like a uniform result.
        """
        return DataType(
            py_type=self.py_type if self.py_type is not None else default_py_type,
            unit_shape=self.unit_shape,
            csr=self.shape is Shape.CSR,
        )

    def reduced(self, py_type: t.Optional[t.Type] = None, shape: t.Optional[Shape] = None):
        """This result type with its per-entity values reduced to a single value per entity"""
        return dataclasses.replace(
            self,
            py_type=self.py_type if py_type is None else py_type,
            shape=(Shape.UNIFORM if self.shape is Shape.CSR else self.shape)
            if shape is None
            else shape,
            unit_shape=(),
        )


def promote(*py_types: t.Optional[t.Type]) -> t.Optional[t.Type]:
    """The narrowest python type that can represent every one of `py_types`. Unknown types are
    ignored, so that a single unknown operand does not make the whole expression unknown.
    """
    known = [py_type for py_type in py_types if py_type in PROMOTION_ORDER]
    if not known:
        return None
    return max(known, key=PROMOTION_ORDER.index)


def combine_shape(*shapes: Shape) -> Shape:
    """The shape that results from combining operands of the given shapes. A csr operand dominates
    a uniform one, which in turn dominates a scalar, since the shorter operand is broadcast.
    """
    if Shape.CSR in shapes:
        return Shape.CSR
    if Shape.UNIFORM in shapes:
        return Shape.UNIFORM
    return Shape.SCALAR


def combine(*result_types: ResultType, py_type: t.Optional[t.Type] = None) -> ResultType:
    """Combine the result types of the operands of an elementwise operation"""
    unit_shapes = [rt.unit_shape for rt in result_types if rt.unit_shape]
    return ResultType(
        py_type=py_type if py_type is not None else promote(*(rt.py_type for rt in result_types)),
        shape=combine_shape(*(rt.shape for rt in result_types)),
        unit_shape=unit_shapes[0] if unit_shapes else (),
    )
