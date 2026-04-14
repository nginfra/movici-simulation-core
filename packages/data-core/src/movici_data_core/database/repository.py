from __future__ import annotations

import contextlib
import copy
import dataclasses
import io
import pathlib
import typing as t
from uuid import UUID

import numpy as np
import orjson
from movici_data_core.database import model as db
from movici_data_core.database.model import (
    NamedResource,
    Options,
    to_domain_or_none,
)
from movici_data_core.domain_model import (
    AttributeDataType,
    AttributeType,
    Dataset,
    DatasetData,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
    Update,
    Workspace,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    MoviciValidationError,
    ResourceDoesNotExist,
)
from movici_data_core.validators import ModelConfigValidator
from sqlalchemy import Insert, Select, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, joinedload, selectinload

from movici_simulation_core.core import DataType, get_rowptr, infer_data_type_from_array
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.types import DatasetData as NumpyDatasetData
from movici_simulation_core.types import FileType, NumpyAttributeData
from movici_simulation_core.validate import MoviciDataRefInfo

T_dom = t.TypeVar("T_dom")


class SQLAlchemyRepository:
    def __init__(self, session: AsyncSession, options: Options):
        self.session = session
        self.options = options

    # define these fields as properties to prevent cyclic references and simplify GC
    @property
    def workspaces(self):
        return WorkspaceRepository(self.session, self.options, self)

    @property
    def dataset_types(self):
        return DatasetTypeRepository(self.session, self.options, self)

    @property
    def entity_types(self):
        return EntityTypeRepository(self.session, self.options, self)

    @property
    def attribute_types(self):
        return AttributeTypeRepository(self.session, self.options, self)

    @property
    def model_types(self):
        return ModelTypeRepository(self.session, self.options, self)

    @property
    def datasets(self):
        return DatasetRepository(self.session, self.options, self)

    @property
    def dataset_data(self):
        return DatasetDataRepository(self.session, self.options, self)

    @property
    def scenarios(self):
        return ScenarioRepository(self.session, self.options, self)

    @property
    def updates(self):
        return UpdateRepository(self.session, self.options, self)


class ResourceSelector(t.Generic[T_dom]):
    __resource__: type[NamedResource[T_dom]]
    __joined_load__: tuple[InstrumentedAttribute, ...] = ()

    @property
    def selector(self):
        selector = select(self.__resource__)
        if self.__joined_load__:
            selector = selector.options(*self._joinedload())
        return selector

    def _joinedload(self):
        yield from (joinedload(col) for col in self.__joined_load__)


class Repository:
    def __init__(self, session: AsyncSession, options: Options, all_data: SQLAlchemyRepository):
        self.session = session
        self.options = options
        self.all_data = all_data


class GenericResourceRepository(Repository, ResourceSelector[T_dom]):
    __resource__: type[NamedResource[T_dom]]

    async def list(self) -> list[T_dom]:
        result = await self.session.scalars(self.selector)
        return [obj.to_domain() for obj in result]

    async def get_by_name(self, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(self.selector.where(self.__resource__.name == name).limit(1))
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        get_kwargs: dict[str, t.Any] = (
            dict(options=list(self._joinedload())) if self.__joined_load__ else {}
        )
        return to_domain_or_none(await self.session.get(self.__resource__, id, **get_kwargs))

    async def delete(self, id: UUID):
        return await self.session.execute(
            delete(self.__resource__).where(self.__resource__.id == id)
        )

    async def create(self, obj: T_dom) -> UUID:
        raise NotImplementedError

    async def update(self, id: UUID, obj: T_dom):
        raise NotImplementedError


class ScopedResourceRepository(Repository, ResourceSelector[T_dom]):
    __parent_ref__: InstrumentedAttribute[UUID]

    async def list(self, parent: UUID) -> list[T_dom]:
        result = await self.session.scalars(
            self.selector.where(type(self).__parent_ref__ == parent)
        )
        return [obj.to_domain() for obj in result]

    async def get_by_name(self, parent: UUID, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(
                select(self.__resource__)
                .where(self.__resource__.name == name, type(self).__parent_ref__ == parent)
                .options(*self._joinedload())
                .limit(1)
            )
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        return to_domain_or_none(
            await self.session.get(self.__resource__, id, options=list(self._joinedload()))
        )

    async def delete(self, id: UUID):
        return await self.session.execute(
            delete(self.__resource__).where(self.__resource__.id == id)
        )

    async def create(self, parent: UUID, obj: T_dom) -> UUID:
        raise NotImplementedError

    async def update(self, id: UUID, obj: T_dom):
        raise NotImplementedError


class WorkspaceRepository(GenericResourceRepository[Workspace]):
    __resource__ = db.Workspace

    async def create(self, obj: Workspace) -> UUID:

        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Workspace)
                .values(name=obj.name, display_name=obj.display_name)
                .returning(db.Workspace.id)
            ),
        )

    async def update(self, id: UUID, obj: Workspace):
        # We do not allow updating the workspace name
        await self.session.execute(
            update(db.Workspace).where(db.Workspace.id == id).values(display_name=obj.display_name)
        )


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

        # We do not allow updating the workspace name
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
                self.selector.where(
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


class DatasetRepository(ScopedResourceRepository[Dataset]):
    __resource__ = db.Dataset
    __parent_ref__ = db.Dataset.workspace_id
    __joined_load__ = (db.Dataset.workspace, db.Dataset.dataset_type)

    async def create(self, parent: UUID, obj: Dataset) -> UUID:
        dataset_type = await self.all_data.dataset_types.ensure_dataset_type(obj.dataset_type)
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Dataset)
                .values(
                    workspace_id=parent,
                    name=obj.name,
                    display_name=obj.display_name,
                    dataset_type_id=t.cast(UUID, dataset_type.id),
                )
                .returning(db.Dataset.id)
            ),
        )

    async def update(self, id: UUID, obj: Dataset):
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("dataset", id=id)
        await self.session.execute(
            update(db.Dataset)
            .where(db.Dataset.id == id)
            .values(name=obj.name, display_name=obj.display_name)
        )

    async def delete(self, id: UUID):
        await self.all_data.dataset_data.delete(id)
        return await super().delete(id)

    async def ensure_scenario_datasets(
        self, parent: UUID, datasets: t.Sequence[ScenarioDataset]
    ) -> list[ScenarioDataset]:
        existing_datasets = {
            ds.name: t.cast(db.Dataset, ds)
            for ds in await self.session.scalars(
                self.selector.where(
                    db.Dataset.workspace_id == parent,
                    db.Dataset.name.in_(ds.name for ds in datasets),
                )
            )
        }
        to_create = []
        for scenario_dataset in datasets:
            name = scenario_dataset.name
            if name not in existing_datasets:
                if self.options.STRICT_SCENARIO_DATASETS:
                    raise ResourceDoesNotExist("dataset", name=name)
                to_create.append(scenario_dataset)
                continue
            if scenario_dataset.type != existing_datasets[name].dataset_type.name:
                raise InvalidResource(
                    "dataset",
                    name=name,
                    message="incompatible dataset already exists",
                )
        if to_create:
            existing_types = {tp.name: tp for tp in await self.all_data.dataset_types.list()}
            for scenario_dataset in to_create:
                if scenario_dataset.type not in existing_types:
                    raise ResourceDoesNotExist("dataset_type", name=scenario_dataset.type)

            created = await self.session.scalars(
                insert(db.Dataset).returning(db.Dataset),
                [
                    {
                        "name": ds.name,
                        "display_name": ds.name,
                        "dataset_type_id": existing_types[ds.type].id,
                        "workspace_id": parent,
                    }
                    for ds in to_create
                ],
            )

            existing_datasets.update((ds.name, ds) for ds in created)

        return [
            ScenarioDataset(name=ds.name, type=ds.type, id=existing_datasets[ds.name].id)
            for ds in datasets
        ]


class DatasetDataRepository(Repository):
    async def exists_for(self, id: UUID):
        raw_data = await self.session.scalar(
            select(func.count(db.RawData.id)).where(db.RawData.dataset_id == id)
        )
        entity_data = await self.session.scalar(
            select(func.count(db.DatasetAttribute.id)).where(db.DatasetAttribute.dataset_id == id)
        )
        return bool(raw_data) or bool(entity_data)

    def stream_binary_data(self, id: UUID, yield_per=1) -> t.AsyncGenerator[bytes]:
        return _RawDataHandler(self.session).stream_bytes(id, yield_per=yield_per)

    def get_unstructured_data(self, id: UUID):
        return _RawDataHandler(self.session).get_dict(id)

    def get_entity_data(self, id: UUID):
        return _EntityDataHandler(
            self.session, all_data=self.all_data, selector=DatasetDataSelector()
        ).get(id)

    async def create(self, id: UUID, data: DatasetData, format: DatasetFormat, chunk_size=0):
        """Store dataset data for a dataset. The dataset must currently not contain any data

        :param id: A dataset id
        :param data: The dataset data as dict, bytes, BytesIO or pathlib.Path
        :param format: The dataset's ``DatasetFormat``
        :param chunk_size: The maximum chunk size in bytes to store data. By default set to the
            value of DatasetRepository.RAW_DATA_CHUNK_SIZE. This parameter is ignore when the
            dataset format is DatasetFormat.ENTITY_BASED
        """

        if await self.exists_for(id):
            raise InvalidResource("dataset", id=id, message="Dataset already has data")

        if format == DatasetFormat.ENTITY_BASED:
            if not isinstance(data, dict):
                raise ValueError("Entity based data must be provided as a dictionary")
            await _EntityDataHandler(
                self.session, self.all_data, selector=DatasetDataSelector()
            ).store(id, data)

        if format == DatasetFormat.UNSTRUCTURED:
            await _RawDataHandler(self.session).store(id, data, chunk_size=chunk_size)

        if format == DatasetFormat.BINARY:
            await _RawDataHandler(self.session).store(id, data, chunk_size=chunk_size)

    async def delete(self, id: UUID):
        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.DatasetAttribute.attribute_id).where(
                        db.DatasetAttribute.dataset_id == id
                    )
                )
            )
        )
        await self.session.execute(delete(db.RawData).where(db.RawData.dataset_id == id))
        await self.session.execute(
            update(db.Dataset)
            .where(db.Dataset.id == id)
            .values(general=None, epsg_code=None, bounding_box=None)
        )


class UpdateRepository(Repository):
    @property
    def selector(self):
        return select(db.Update).options(
            joinedload(db.Update.dataset).joinedload(db.Dataset.dataset_type),
            joinedload(db.Update.model_type),
        )

    async def list(self, parent: UUID) -> list[Update]:
        result = await self.session.scalars(
            self.selector.where(db.Update.scenario_id == parent).order_by(
                db.Update.timestamp, db.Update.iteration
            )
        )
        return [update.to_domain() for update in result]

    async def get_by_id(self, id: UUID) -> Update | None:
        record = await self.session.scalar(
            select(db.Update)
            .options(
                joinedload(db.Update.dataset).joinedload(db.Dataset.dataset_type),
                joinedload(db.Update.model_type),
            )
            .where(db.Update.id == id)
        )
        if record is None:
            return None
        return dataclasses.replace(
            record.to_domain(),
            data=await _EntityDataHandler(
                self.session, all_data=self.all_data, selector=UpdateDataSelector()
            ).get(id),
        )

    async def create(self, parent: UUID, obj: Update) -> UUID:
        """
        :param parent: A Scenario id
        """
        if not isinstance(obj.data, dict):
            raise InvalidAction("update data must be a numpy dataset dict")
        model_type_id = await self.session.scalar(
            select(db.ModelType.id)
            .join(db.ScenarioModel)
            .where(db.ScenarioModel.scenario_id == parent)
            .where(db.ScenarioModel.name == obj.model_name)
        )
        if model_type_id is None:
            raise MoviciValidationError(
                f"{obj.model_name} is not a valid model for this scenario", "model_name"
            )
        dataset = await self.session.scalar(
            select(db.Dataset)
            .options(joinedload(db.Dataset.dataset_type))
            .join(db.ScenarioDataset)
            .where(db.ScenarioDataset.scenario_id == parent)
            .where(db.Dataset.name == obj.dataset.name)
        )
        if dataset is None:
            raise ResourceDoesNotExist("dataset", name=obj.dataset.name)

        update_id = t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Update)
                .values(
                    scenario_id=parent,
                    timestamp=obj.timestamp,
                    iteration=obj.iteration,
                    model_type_id=model_type_id,
                    model_name=obj.model_name,
                    dataset_id=dataset.id,
                )
                .returning(db.Update.id)
            ),
        )
        await _EntityDataHandler(self.session, self.all_data, UpdateDataSelector()).store(
            update_id, obj.data
        )
        return update_id

    async def delete_for_scenario(self, parent: UUID):
        await self.session.execute(delete(db.Update).where(db.Update.scenario_id == parent))


class EntityDataSelector(t.Protocol):
    def select_linked_attribute(self, id: UUID) -> Select[tuple[db.Attribute]]: ...
    def insert_linked_attribute(self, id: UUID, attribute_id: UUID) -> Insert: ...


class DatasetDataSelector:
    def select_linked_attribute(self, id: UUID) -> Select[tuple[db.Attribute]]:
        return (
            select(db.Attribute)
            .join(db.DatasetAttribute)
            .where(db.DatasetAttribute.dataset_id == id)
        )

    def insert_linked_attribute(self, id: UUID, attribute_id: UUID) -> Insert:
        return insert(db.DatasetAttribute).values(dataset_id=id, attribute_id=attribute_id)


class UpdateDataSelector:
    def select_linked_attribute(self, id: UUID):
        return (
            select(db.Attribute).join(db.UpdateAttribute).where(db.UpdateAttribute.update_id == id)
        )

    def insert_linked_attribute(self, id: UUID, attribute_id: UUID):
        return insert(db.UpdateAttribute).values(update_id=id, attribute_id=attribute_id)


class _EntityDataHandler:
    def __init__(
        self, session: AsyncSession, all_data: SQLAlchemyRepository, selector: EntityDataSelector
    ):
        self.session = session
        self.all_data = all_data
        self.selector = selector

    async def get(self, id: UUID) -> NumpyDatasetData:
        result: NumpyDatasetData = {}
        for attribute in (
            await self.session.scalars(
                self.selector.select_linked_attribute(id).options(
                    joinedload(db.Attribute.rowptr),
                    joinedload(db.Attribute.data),
                    joinedload(db.Attribute.entity_type),
                    joinedload(db.Attribute.attribute_type),
                )
            )
        ).all():
            entity_group = result.setdefault(attribute.entity_type.name, {})
            attr_data: NumpyAttributeData = {"data": attribute.data.to_numpy()}
            if attribute.rowptr is not None:
                attr_data[DEFAULT_ROWPTR_KEY] = attribute.rowptr.to_numpy()
            entity_group[attribute.attribute_type.name] = attr_data
        return result

    async def store(self, id: UUID, data: NumpyDatasetData):
        """
        :param id: dataset UUID
        :param data: dataset data section in numpy format
        """
        for entity_group, attributes in data.items():
            entity_type = await self.all_data.entity_types.ensure_entity_type(
                EntityType(entity_group)
            )
            for attr_name, attr_data in attributes.items():
                data_type = infer_data_type_from_array(t.cast(dict, attr_data))
                attribute_type = await self.all_data.attribute_types.ensure_attribute_type(
                    AttributeType(attr_name, data_type=data_type)
                )

                attribute_id = await self.session.scalar(
                    insert(db.Attribute)
                    .values(
                        entity_type_id=entity_type.id,
                        attribute_type_id=attribute_type.id,
                    )
                    .returning(db.Attribute.id)
                )
                assert attribute_id is not None

                data_array: np.ndarray = attr_data["data"]  # type: ignore
                await self._store_data_array(data_array, attribute_id, data_type=data_type)

                rowptr = get_rowptr(t.cast(dict, attr_data))
                if rowptr is not None:
                    await self._store_rowptr_array(rowptr, attribute_id)

                await self.session.execute(
                    self.selector.insert_linked_attribute(id=id, attribute_id=attribute_id)
                )

    async def _store_data_array(self, arr: np.ndarray, attribute_id: UUID, data_type: DataType):
        min_val, max_val = data_type.get_min_max(arr)
        await self.session.execute(
            insert(db.DataArray).values(
                attribute_id=attribute_id,
                dtype=arr.dtype.str,
                shape=arr.shape,
                data=arr.tobytes(),
                min_val=min_val,
                max_val=max_val,
            )
        )

    async def _store_rowptr_array(self, arr: np.ndarray, attribute_id: UUID):
        await self.session.execute(
            insert(db.RowptrArray).values(data=arr.tobytes(), attribute_id=attribute_id)
        )

    # TODO: We already expect to have numpy data here, so we need to move this function somewhere
    # else. The backend maybe?
    def _data_as_numpy_dict(self, data: dict, filetype: FileType, data_is_numpy=False):
        ""
        finalizer = None  # noqa: F841

        if isinstance(data, dict):
            if data_is_numpy:
                return data
            if "data" not in data.keys():
                data = {"data": data}
            return EntityInitDataFormat(self.schema).load_json(data)["data"]

        if isinstance(data, pathlib.Path):
            data = data.read_bytes()
        if isinstance(data, t.BinaryIO):
            data = data.read()

        return self.serializer.loads(data, type=filetype)["data"]


class _RawDataHandler:
    RAW_DATA_CHUNK_SIZE = 100_000_000  # 100 MB

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: UUID | None = None, raw_data: db.RawData | None = None) -> bytearray:
        result = bytearray()

        async for chunk in self.stream_bytes(id, raw_data):
            result += chunk
        return result

    async def stream_bytes(
        self, id: UUID | None = None, raw_data: db.RawData | None = None, yield_per=1
    ) -> t.AsyncGenerator[bytes]:
        if not ((id is None) ^ (raw_data is None)):
            raise ValueError("Supply one of id and raw_data, but not both")

        raw_data = raw_data or await self._ensure_raw_data(t.cast(UUID, id))

        async for chunk in await self.session.stream_scalars(
            select(db.RawDataChunk.bytes)
            .execution_options(yield_per=yield_per)
            .where(db.RawDataChunk.raw_data_id == raw_data.id)
            .order_by(db.RawDataChunk.sequence.asc())
        ):
            yield chunk

    async def get_dict(self, id: UUID) -> dict:
        raw_data = await self._ensure_raw_data(id)
        if raw_data.encoding != "json":
            raise ValueError(f"Expected dataset encoding 'json', got {raw_data.encoding}")
        raw_bytes = await self.get(id)
        return orjson.loads(raw_bytes)

    async def store(self, id: UUID, data: DatasetData, chunk_size=0):
        chunk_size = chunk_size or self.RAW_DATA_CHUNK_SIZE
        with self._data_as_bytesio(data) as (encoding, raw_reader):
            raw_data_id = t.cast(
                UUID,
                await self.session.scalar(
                    insert(db.RawData)
                    .values(
                        dataset_id=id,
                        encoding=encoding,
                    )
                    .returning(db.RawData.id)
                ),
            )
            for seq, chunk in self._raw_data_chunks(raw_reader, chunk_size):
                await self.session.execute(
                    insert(db.RawDataChunk).values(
                        raw_data_id=raw_data_id, sequence=seq, bytes=chunk
                    )
                )

    async def _ensure_raw_data(self, id: UUID):
        raw_data = await self.session.scalar(
            select(db.RawData).where(db.RawData.dataset_id == id).limit(1)
        )
        if raw_data is None:
            raise ResourceDoesNotExist("dataset_data", id=id)
        return raw_data

    @staticmethod
    @contextlib.contextmanager
    def _data_as_bytesio(data: DatasetData):
        encoding = None
        finalizer = None
        if isinstance(data, dict):
            data = orjson.dumps(data)
            encoding = "json"
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        if isinstance(data, pathlib.Path):
            data = open(data, "rb")
            finalizer = data.close

        try:
            yield encoding, data
        finally:
            if finalizer is not None:
                finalizer()

    @staticmethod
    def _raw_data_chunks(file: t.BinaryIO, chunk_size: int):
        if chunk_size <= 0:
            raise ValueError("Chunk size must be greater than 0")
        seq = 0
        while chunk := file.read(chunk_size):
            seq += 1
            yield seq, chunk


class ScenarioRepository:
    def __init__(self, session: AsyncSession, options: Options, all_data: SQLAlchemyRepository):
        self.session = session
        self.all_data = all_data
        self.options = options

    async def list(self, parent: UUID) -> list[Scenario]:
        result = await self.session.scalars(
            select(db.Scenario).where(db.Scenario.workspace_id == parent)
        )
        return [obj.to_domain() for obj in result]

    @property
    def selector(self):
        return select(db.Scenario).options(
            joinedload(db.Scenario.workspace),
            selectinload(db.Scenario.datasets)
            .joinedload(db.ScenarioDataset.dataset)
            .joinedload(db.Dataset.dataset_type),
            selectinload(db.Scenario.models).options(
                joinedload(db.ScenarioModel.model_type),
                selectinload(db.ScenarioModel.references).options(
                    joinedload(db.ScenarioModelReference.dataset),
                    joinedload(db.ScenarioModelReference.entity_type),
                    joinedload(db.ScenarioModelReference.attribute_type),
                ),
            ),
        )

    async def get_by_name(self, parent: UUID, name: str) -> Scenario | None:
        record = await self.session.scalar(
            self.selector.where(db.Scenario.name == name, db.Scenario.workspace_id == parent)
        )
        if record is None:
            return None
        return self.load_full_scenario(record)

    async def get_by_id(self, id: UUID) -> Scenario | None:
        record = await self.session.scalar(self.selector.where(db.Scenario.id == id))
        if record is None:
            return None
        return self.load_full_scenario(record)

    async def delete(self, id: UUID):
        return await self.session.execute(delete(db.Scenario).where(db.Scenario.id == id))

    async def create(self, parent: UUID, obj: Scenario, validator: ModelConfigValidator) -> UUID:
        scenario_id = await self.session.scalar(
            insert(db.Scenario)
            .values(
                workspace_id=parent,
                name=obj.name,
                display_name=obj.display_name,
                description=obj.description,
                status=obj.status,
                simulation_info=obj.simulation_info,
                epsg_code=obj.epsg_code,
            )
            .returning(db.Scenario.id)
        )
        assert scenario_id is not None
        await self._store_scenario_details(parent, scenario_id, obj, validator)
        return scenario_id

    async def update(self, id: UUID, obj: Scenario, validator: ModelConfigValidator):
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("scenario", id=id)
        assert current.workspace is not None
        assert current.workspace.id is not None

        await self.session.execute(
            update(db.Scenario)
            .where(db.Scenario.id == id)
            .values(
                name=obj.name,
                display_name=obj.display_name,
                description=obj.description,
                simulation_info=obj.simulation_info,
                epsg_code=obj.epsg_code,
            )
        )
        await self.session.execute(
            delete(db.ScenarioDataset).where(db.ScenarioDataset.scenario_id == id)
        )
        await self.session.execute(
            delete(db.ScenarioModel).where(db.ScenarioModel.scenario_id == id)
        )

        await self._store_scenario_details(current.workspace.id, id, obj, validator)

    async def set_status(self, id: UUID, status: ScenarioStatus):
        await self.session.execute(
            update(db.Scenario).where(db.Scenario.id == id).values(status=status)
        )

    async def _store_scenario_details(
        self, parent: UUID, scenario_id: UUID, obj: Scenario, validator: ModelConfigValidator
    ):
        scenario_datasets = await self.all_data.datasets.ensure_scenario_datasets(
            parent, [ScenarioDataset(ds["name"], ds["type"]) for ds in obj.datasets]
        )
        await self.session.execute(
            insert(db.ScenarioDataset),
            [
                {"scenario_id": scenario_id, "dataset_id": ds.id, "sequence": idx}
                for idx, ds in enumerate(scenario_datasets)
            ],
        )

        model_types = await self.all_data.model_types.ensure_model_types(
            [model["type"] for model in obj.models if "name" in model]
        )

        validator = validator.for_scenario(scenario_datasets, model_types)
        scenario_models = validator.process_model_configs(obj.models)
        scenario_model_records = await self.session.scalars(
            insert(db.ScenarioModel).returning(db.ScenarioModel),
            [
                {
                    "name": model.name,
                    "scenario_id": scenario_id,
                    "model_type_id": model_type.id,
                    "sequence": idx,
                    "config": self.stripped_config(model),
                }
                for idx, (model, model_type) in enumerate(zip(scenario_models, model_types))
            ],
        )
        refs_to_add = []
        for scenario_model, record in zip(
            scenario_models, sorted(scenario_model_records, key=lambda r: r.sequence)
        ):
            for ref in scenario_model.references:
                ref_data = {
                    "scenario_model_id": record.id,
                    "path": ref.json_path,
                }
                if ref.movici_type == "attribute":
                    ref_data["attribute_type_id"] = validator.attribute_types[ref.value].id
                elif ref.movici_type == "entityGroup":
                    ref_data["entity_type_id"] = validator.entity_types[ref.value].id
                elif ref.movici_type == "dataset":
                    ref_data["dataset_id"] = (
                        validator.datasets[ref.value].id if validator.datasets else None
                    )
                refs_to_add.append(ref_data)

        if refs_to_add:
            await self.session.execute(insert(db.ScenarioModelReference), refs_to_add)

    @classmethod
    def load_full_scenario(cls, scenario: db.Scenario) -> Scenario:
        return dataclasses.replace(
            scenario.to_domain(),
            datasets=[
                cls._load_scenario_dataset(ds)
                for ds in sorted(scenario.datasets, key=lambda ds: ds.sequence)
            ],
            models=[
                cls._load_scenario_model(model)
                for model in sorted(scenario.models, key=lambda model: model.sequence)
            ],
        )

    @staticmethod
    def _load_scenario_dataset(scenario_dataset: db.ScenarioDataset):
        return {
            "id": scenario_dataset.dataset_id,
            "name": scenario_dataset.dataset.name,
            "type": scenario_dataset.dataset.dataset_type.name,
        }

    @classmethod
    def _load_scenario_model(cls, scenario_model: db.ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        for data_ref in scenario_model.references:
            value = None
            if data_ref.dataset is not None:
                value = data_ref.dataset.name
            elif data_ref.entity_type is not None:
                value = data_ref.entity_type.name
            elif data_ref.attribute_type is not None:
                value = data_ref.attribute_type.name
            MoviciDataRefInfo.from_path_string(data_ref.path, value).set_value(result)

        result["name"] = scenario_model.name
        result["type"] = scenario_model.model_type.name
        return result

    @staticmethod
    def stripped_config(scenario_model: ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        result.pop("name", None)
        result.pop("type", None)
        for ref in scenario_model.references:
            ref.unset_value(result)
        return result

    @staticmethod
    def prepare_scenario_model_references(
        id: UUID, scenario_model: ScenarioModel, schema: ModelConfigValidator
    ):
        result = []
        for ref in scenario_model.references:
            ref_data = {
                "scenario_model_id": id,
                "path": ref.json_path,
            }
            if ref.movici_type == "attribute":
                ref_data["attribute_type_id"] = schema.attribute_types[ref.value].id
            elif ref.movici_type == "entityGroup":
                ref_data["entity_type_id"] = schema.entity_types[ref.value].id
            elif ref.movici_type == "dataset":
                ref_data["dataset_id"] = schema.datasets[ref.value].id if schema.datasets else None
            result.append(ref_data)
        return result
