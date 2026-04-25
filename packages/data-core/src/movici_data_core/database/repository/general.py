from __future__ import annotations

import typing as t
from uuid import UUID

from sqlalchemy import insert, select, update

from movici_data_core.database import model as db
from movici_data_core.domain_model import (
    AttributeDataType,
    AttributeType,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    ResourceDoesNotExist,
)

from .common import GenericResourceRepository


class DatasetTypeRepository(GenericResourceRepository[DatasetType]):
    __resource__ = db.DatasetType

    async def create(self, obj: DatasetType) -> UUID:
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.DatasetType)
                .values(name=obj.name, format=obj.format, mimetype=obj.mimetype)
                .returning(db.DatasetType.id)
            ),
        )

    async def update(self, id: UUID, obj: DatasetType):
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("dataset_type", id=id)
        if current.format != obj.format:
            raise InvalidAction("Cannot update dataset type format")

        mimetype = obj.mimetype if obj.format == DatasetFormat.BINARY else None

        await self.session.execute(
            update(db.DatasetType)
            .where(db.DatasetType.id == id)
            .values(name=obj.name, mimetype=mimetype)
        )

    async def ensure_dataset_type(self, dataset_type: DatasetType) -> DatasetType:
        existing = await self.get_by_name(dataset_type.name)
        if not existing:
            if self.options.STRICT_DATASET_TYPES:
                raise ResourceDoesNotExist("dataset_type", name=dataset_type.name)
            dataset_type_id = await self.create(dataset_type)
            existing = await self.get_by_id(dataset_type_id)

        if existing != dataset_type:
            raise InvalidResource(
                "dataset_type",
                name=dataset_type.name,
                message="incompatible dataset_type already exists",
            )
        return t.cast(DatasetType, existing)


class EntityTypeRepository(GenericResourceRepository[EntityType]):
    __resource__ = db.EntityType

    async def create(self, obj: EntityType) -> UUID:
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.EntityType).values(name=obj.name).returning(db.EntityType.id)
            ),
        )

    async def update(self, id: UUID, obj: EntityType):
        await self.session.execute(
            update(db.EntityType).where(db.EntityType.id == id).values(name=obj.name)
        )

    async def ensure_entity_type(self, entity_type: EntityType) -> EntityType:
        existing = await self.get_by_name(entity_type.name)
        if not existing:
            if self.options.STRICT_ENTITY_TYPES:
                raise ResourceDoesNotExist("entity_type", name=entity_type.name)

            entity_type_id = await self.create(entity_type)
            existing = await self.get_by_id(entity_type_id)

        return t.cast(EntityType, existing)


class AttributeTypeRepository(GenericResourceRepository[AttributeType]):
    __resource__ = db.AttributeType

    async def create(self, obj: AttributeType) -> UUID:
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.AttributeType)
                .values(
                    name=obj.name,
                    has_rowptr=obj.data_type.csr,
                    unit_type=self.db_unit_type(obj.data_type.py_type),
                    unit_shape=obj.data_type.unit_shape,
                    unit=obj.unit,
                    description=obj.description,
                    enum_name=obj.enum_name,
                )
                .returning(db.AttributeType.id)
            ),
        )

    def db_unit_type(self, py_type: AttributeDataType):
        return {
            bool: db.AttributeDataType.BOOL,
            int: db.AttributeDataType.INT,
            float: db.AttributeDataType.FLOAT,
            str: db.AttributeDataType.STR,
        }[py_type]

    async def update(self, id: UUID, obj: AttributeType):
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("attribute_type", id=id)
        in_use = await self.session.scalar(
            select(db.Attribute.id).where(db.Attribute.attribute_type_id == id).limit(1)
        )

        if in_use and not current.data_type == obj.data_type:
            raise InvalidAction("cannot change attribute data type when it is in use")

        await self.session.execute(
            update(db.AttributeType)
            .where(db.AttributeType.id == id)
            .values(
                name=obj.name,
                has_rowptr=obj.data_type.csr,
                unit_type=self.db_unit_type(obj.data_type.py_type),
                unit_shape=obj.data_type.unit_shape,
                unit=obj.unit,
                description=obj.description,
            )
        )

    async def ensure_attribute_type(self, attribute_type: AttributeType) -> AttributeType:
        existing = await self.get_by_name(attribute_type.name)
        if not existing:
            if self.options.STRICT_ATTRIBUTES:
                raise ResourceDoesNotExist("attribute_type", name=attribute_type.name)
            attribute_type_id = await self.create(attribute_type)
            existing = t.cast(AttributeType, await self.get_by_id(attribute_type_id))

        if not existing.data_type == attribute_type.data_type:
            raise InvalidResource(
                "attribute_type",
                name=attribute_type.name,
                message="incompatible attribute_type already exists",
            )
        return existing


class ModelTypeRepository(GenericResourceRepository[ModelType]):
    __resource__ = db.ModelType

    async def create(self, obj: ModelType) -> UUID:
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.ModelType)
                .values(name=obj.name, jsonschema=obj.jsonschema)
                .returning(db.ModelType.id)
            ),
        )

    async def update(self, id: UUID, obj: ModelType):
        await self.session.execute(
            update(db.ModelType)
            .where(db.ModelType.id == id)
            .values(name=obj.name, jsonschema=obj.jsonschema)
        )

    async def ensure_model_types(self, model_types: t.Sequence[str]) -> list[ModelType]:
        existing_model_types = {
            tp.name: t.cast(db.ModelType, tp)
            for tp in await self.session.scalars(
                select(db.ModelType).where(
                    db.ModelType.name.in_(model_types),
                )
            )
        }
        to_create = []
        for model_type in model_types:
            if model_type not in existing_model_types:
                if self.options.STRICT_MODEL_TYPES:
                    raise ResourceDoesNotExist("model_type", name=model_type)
                to_create.append(model_type)
                continue

        if to_create:
            created = await self.session.scalars(
                insert(db.ModelType).returning(db.ModelType),
                [{"name": tp, "jsonschema": self.default_jsonschema(tp)} for tp in to_create],
            )

            existing_model_types.update((tp.name, tp) for tp in created)

        return [existing_model_types[tp].to_domain() for tp in model_types]

    @staticmethod
    def default_jsonschema(name: str):
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"/{name}/1.0.0",
            "type": "object",
            "additionalProperties": True,
        }
