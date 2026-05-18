from __future__ import annotations

import dataclasses
import datetime
import pathlib
import typing as t
from operator import methodcaller
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    model_serializer,
)

from movici_data_core import domain_model
from movici_data_core.domain_model import BoundingBox, DatasetFormat, DatasetType, Update

T_dom = t.TypeVar("T_dom")


BoundingBoxField = t.Annotated[
    BoundingBox,
    PlainSerializer(methodcaller("as_tuple_or_none")),
    WithJsonSchema(
        {
            "title": "Bounding Box",
            "type": "array",
            "maxItems": 4,
            "minItems": 4,
            "items": {"type": "number"},
        }
    ),
]


class OutModel(BaseModel, t.Generic[T_dom]):
    model_config = ConfigDict(from_attributes=True)
    __envelope__: t.ClassVar[str | None] = None

    @classmethod
    def from_domain(cls, obj: T_dom):
        if cls.__envelope__ is not None:
            return cls.model_validate({cls.__envelope__: obj})
        return cls.model_validate(obj)


class WorkspaceIn(BaseModel):
    name: str
    display_name: str

    def to_domain(self):
        return domain_model.Workspace(name=self.name, display_name=self.display_name)


class WorkspaceOut(WorkspaceIn, OutModel[domain_model.Workspace]):
    id: UUID
    scenario_count: int
    dataset_count: int


class WorkspaceListOut(OutModel[t.Sequence[domain_model.Workspace]]):
    __envelope__ = "workspaces"
    workspaces: list[WorkspaceOut]


class ShortDatasetIn(BaseModel):
    name: str
    display_name: str = ""
    type: DatasetType | str

    def ensure_dataset_type(self):
        if isinstance(self.type, DatasetType):
            return self.type
        return DatasetType(self.type, format=DatasetFormat.UNKNOWN)

    def to_domain(self):
        return domain_model.Dataset(
            name=self.name,
            display_name=self.display_name or self.name,
            dataset_type=self.ensure_dataset_type(),
        )


class ShortDatasetOut(OutModel[domain_model.Dataset]):
    id: UUID
    name: str
    display_name: str
    type: DatasetType = Field(validation_alias="dataset_type")
    has_data: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DatasetList(OutModel[t.Sequence[domain_model.Dataset]]):
    __envelope__ = "datasets"
    datasets: list[ShortDatasetOut]


class DatasetWithDataIn(ShortDatasetIn):
    """Full input dataset model, only relevant for `ENTITY_BASED` and `UNSTRUCTURED` datasets"""

    epsg_code: int | None = None
    general: dict | None = None
    data: dict | None = None

    def to_domain(self):
        return dataclasses.replace(
            super().to_domain(),
            general=self.general,
            epsg_code=self.epsg_code,
            data=self.data,
        )


class DatasetWithDataOut(ShortDatasetOut):
    """Full output dataset model, only relevant for `ENTITY_BASED` and `UNSTRUCTURED` datasets"""

    epsg_code: int | None = None
    bounding_box: BoundingBoxField | None = None
    general: dict | None = None
    data: dict


class ShortUpdateOut(OutModel[domain_model.Update]):
    id: UUID

    dataset_name: str
    model_name: str
    model_type: str | None
    timestamp: int
    iteration: int
    created_at: datetime.datetime


class UpdateWithDataOut(ShortUpdateOut):
    data: dict | None


class UpdateWithDataIn:
    @classmethod
    def read_from_file(cls, path: pathlib.Path) -> Update: ...


class OperationSuccess(BaseModel):
    resource: str
    id: UUID | str
    verb: str

    @model_serializer
    def serialize(self):
        return {"result": "ok", "id": self.id, "message": f"{self.resource} {self.verb}"}
