from __future__ import annotations

import dataclasses
import datetime
import typing as t
from uuid import UUID

from pydantic import AliasPath, BaseModel, Field, model_serializer

from movici_data_core import domain_model


def api_model_from_domain(cls: type[BaseModel], obj: t.Any):
    return cls.model_validate(dataclasses.asdict(obj), by_alias=True)


def api_model_from_domain_many(cls: type[BaseModel], objs: t.Iterable):
    return [api_model_from_domain(cls, obj) for obj in objs]


class ShortDatasetIn(BaseModel):
    name: str
    display_name: str
    type: str

    @staticmethod
    # explicitly annotate so that we can use this function with Depends
    def to_domain(obj: ShortDatasetIn):
        return domain_model.Dataset(
            obj.name, obj.display_name, dataset_type=domain_model.DatasetType(obj.type)
        )


class ShortDatasetOut(BaseModel):
    name: str
    display_name: str
    id: UUID
    has_data: bool
    type: str = Field(validation_alias=AliasPath("dataset_type", "name"))
    created_at: datetime.datetime | None
    updated_at: datetime.datetime | None


class DatasetOut(ShortDatasetOut):
    type: str
    general: dict | None
    epsg_code: int | None
    bounding_box: tuple[float, float, float, float] | None
    data: dict | None

    @classmethod
    def from_domain(cls, obj: domain_model.Dataset):
        return DatasetOut(
            id=t.cast(UUID, obj.id),
            name=obj.name,
            display_name=obj.display_name,
            has_data=obj.has_data,
            type=obj.dataset_type.name,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
            general=obj.general,
            epsg_code=obj.epsg_code,
            bounding_box=obj.bounding_box.as_tuple_or_none(),
            data=t.cast(dict, obj.data),
        )


class ResourceSuccess(BaseModel):
    resource: str
    id: UUID | str
    verb: str

    @model_serializer
    def serialize(self):
        return {"result": "ok", "id": self.id, "message": f"{self.resource} {self.verb}"}
