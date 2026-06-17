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

from .common import GenericResourceRepository, ensure_valid_id


class DatasetTypeRepository(GenericResourceRepository[DatasetType]):
    __resource__ = db.DatasetType
    __resource_type_name__ = "dataset_type"

    async def create(self, obj: DatasetType) -> UUID:
        """Store a :class:``DatasetType`` in the database. When storing a ``DatasetType``, its
        ``format`` field may not be set to ``None``.

        :param obj: the ``DatasetType`` object
        :return: the UUID of the stored ``DatasetType``
        """
        if obj.format is None:
            raise InvalidAction("Must specify DatasetFormat when creating a DatasetType")
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.DatasetType)
                .values(name=obj.name, format=obj.format, mimetype=obj.mimetype)
                .returning(db.DatasetType.id)
            ),
        )

    async def update(self, id: UUID, obj: DatasetType):
        """Update a :class:``DatasetType`` in the database

        Valid fields to update are: ``name``, ``mimetype``

        :param id: the UUID of the stored ``DatasetType``
        :param obj: the ``DatasetType`` object
        """
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
        """Ensure that a dataset type exists in the database or raise an error. If the dataset type
        does not exist and the database option ``STRICT_DATASET_TYPES`` is unset, the dataset
        type will be created. If the ``STRICT_DATASET_TYPES`` options is set, an error is raised
        instead. An error will also be raised if an attempt is made to create a DatasetType with
        its ``format`` field set to ``None``

        :param dataset_type: the ``DatasetType`` object to ensure.
        :return: the ``DatasetType`` object as it exists in the database
        """
        existing = await self.get_by_name(dataset_type.name)
        if not existing:
            if self.options.STRICT_DATASET_TYPES:
                raise ResourceDoesNotExist("dataset_type", name=dataset_type.name)
            dataset_type_id = await self.create(dataset_type)
            existing = await self.get_by_id(dataset_type_id)

        assert existing is not None
        if not existing.is_equivalent(dataset_type):
            raise InvalidResource(
                "dataset_type",
                name=dataset_type.name,
                message="incompatible dataset_type already exists",
            )
        return t.cast(DatasetType, existing)


class EntityTypeRepository(GenericResourceRepository[EntityType]):
    __resource__ = db.EntityType
    __resource_type_name__ = "entity_type"

    async def create(self, obj: EntityType) -> UUID:
        """Store a :class:``EntityType`` in the database

        :param obj: the ``EntityType`` object
        :return: the UUID of the stored ``EntityType``
        """
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.EntityType).values(name=obj.name).returning(db.EntityType.id)
            ),
        )

    @ensure_valid_id
    async def update(self, id: UUID, obj: EntityType):
        """Update a :class:``EntityType`` in the database

        Valid fields to update are: ``name``

        :param id: the UUID of the stored ``EntityType``
        :param obj: the ``EntityType`` object with the changes
        """
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
    __resource_type_name__ = "attribute_type"

    async def create(self, obj: AttributeType) -> UUID:
        """Store a :class:``AttributeType`` in the database

        :param obj: the ``AttributeType`` object
        :return: the UUID of the stored ``AttributeType``
        """
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.AttributeType)
                .values(
                    name=obj.name,
                    has_rowptr=obj.data_type.csr,
                    unit_type=self._db_unit_type(obj.data_type.py_type),
                    unit_shape=obj.data_type.unit_shape,
                    unit=obj.unit,
                    description=obj.description,
                    enum_name=obj.enum_name,
                )
                .returning(db.AttributeType.id)
            ),
        )

    def _db_unit_type(self, py_type: AttributeDataType):
        return {
            bool: db.AttributeDataType.BOOL,
            int: db.AttributeDataType.INT,
            float: db.AttributeDataType.FLOAT,
            str: db.AttributeDataType.STR,
        }[py_type]

    async def update(self, id: UUID, obj: AttributeType):
        """Update a :class:``AttributeType`` in the database

        Valid fields to update are: ``name``, ``data_type``, ``unit``, ``description``,
        ``enum_name``

        :param id: the UUID of the stored ``EntityType``
        :param obj: the ``EntityType`` object with the changes
        """
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
                unit_type=self._db_unit_type(obj.data_type.py_type),
                unit_shape=obj.data_type.unit_shape,
                unit=obj.unit,
                description=obj.description,
                enum_name=obj.enum_name,
            )
        )

    async def ensure_attribute_type(self, attribute_type: AttributeType) -> AttributeType:
        """Ensure that an attribute type exists in the database or raise an error. If the attribute
        type does not exist and the database option ``STRICT_ATTRIBUTE_TYPES`` is unset, the
        attribute type will be created. If the ``STRICT_ATTRIBUTE_TYPES`` options is set, an error
        is raised instead. An error will also be raised if an ``AttributeType`` with a different
        data_type already exists.

        :param attribute_type: the ``AttributeType`` object to ensure.
        :return: the ``AttributeType`` object as it exists in the database
        """
        existing = await self.get_by_name(attribute_type.name)
        if not existing:
            if self.options.STRICT_ATTRIBUTE_TYPES:
                raise ResourceDoesNotExist("attribute_type", name=attribute_type.name)
            attribute_type_id = await self.create(attribute_type)
            existing = t.cast(AttributeType, await self.get_by_id(attribute_type_id))

        if existing.data_type != attribute_type.data_type:
            raise InvalidResource(
                "attribute_type",
                name=attribute_type.name,
                message="incompatible attribute_type already exists",
            )
        return existing


class ModelTypeRepository(GenericResourceRepository[ModelType]):
    __resource__ = db.ModelType
    __resource_type_name__ = "model_type"

    async def create(self, obj: ModelType) -> UUID:
        """Store a :class:``ModelType`` in the database

        :param obj: the ``ModelType`` object
        :return: the UUID of the stored ``ModelType``
        """
        if obj.jsonschema is None:
            raise InvalidAction("Cannot create ModelType without a jsonschema")
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.ModelType)
                .values(name=obj.name, jsonschema=obj.jsonschema)
                .returning(db.ModelType.id)
            ),
        )

    @ensure_valid_id
    async def update(self, id: UUID, obj: ModelType):
        """Update a :class:``ModelType`` in the database

        Valid fields to update are: ``name``, ``jsonschema``

        :param id: the UUID of the stored ``ModelType``
        :param obj: the ``ModelType`` object with the changes
        """
        if obj.jsonschema is None:
            raise InvalidAction("Cannot set ModelType.jsonschema to None")
        await self.session.execute(
            update(db.ModelType)
            .where(db.ModelType.id == id)
            .values(name=obj.name, jsonschema=obj.jsonschema)
        )

    async def ensure_model_types(self, model_types: t.Sequence[ModelType]) -> list[ModelType]:
        """Ensure that a sequence of model types exist in the database or raise an error. If one or
        more of the model types does not exist and the database option ``STRICT_MODEL_TYPES`` is
        unset, the non-existing model types will be created. If the ``STRICT_MODEL_TYPES`` options
        is set, an error is raised instead.
        :param model_types: The model types to ensure, as a sequence of model type names
        :return: the ``ModelType`` objects as they exist in the database, in the same order as the
            input sequence
        """
        existing_model_types = {
            tp.name: t.cast(db.ModelType, tp)
            for tp in await self.session.scalars(
                select(db.ModelType).where(
                    db.ModelType.name.in_(tp.name for tp in model_types),
                )
            )
        }
        to_create: list[ModelType] = []
        for model_type in model_types:
            if model_type.name not in existing_model_types:
                if self.options.STRICT_MODEL_TYPES:
                    raise ResourceDoesNotExist("model_type", name=model_type.name)
                to_create.append(model_type)
                continue

        if to_create:
            created = await self.session.scalars(
                insert(db.ModelType).returning(db.ModelType),
                [
                    {
                        "name": tp.name,
                        "jsonschema": tp.jsonschema or self._default_jsonschema(tp.name),
                    }
                    for tp in to_create
                ],
            )

            existing_model_types.update((tp.name, tp) for tp in created)

        return [existing_model_types[tp.name].to_domain() for tp in model_types]

    @staticmethod
    def _default_jsonschema(name: str):
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"/{name}/1.0.0",
            "type": "object",
            "additionalProperties": True,
        }
