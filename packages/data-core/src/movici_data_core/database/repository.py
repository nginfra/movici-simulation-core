from __future__ import annotations

import contextlib
import io
import pathlib
import typing as t
from uuid import UUID

import numpy as np
import orjson
from movici_data_core.database import model as db
from movici_data_core.database.model import (
    Attribute,
    DatasetAttribute,
    NamedResource,
    NumpyArray,
    Options,
    RawData,
    RawDataChunk,
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
    NumpyDatasetData,
    Workspace,
)
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

from movici_simulation_core.core import (
    get_rowptr,
    infer_data_type_from_array,
)
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.types import (
    FileType,
    NumpyAttributeData,
)

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
    def datasets(self):
        return DatasetRepository(self.session, self.options, self)


class ResourceSelector(t.Generic[T_dom]):
    __resource__: type[NamedResource[T_dom]]
    __select_in_load__: tuple[InstrumentedAttribute, ...] = ()

    @property
    def selector(self):
        selector = select(self.__resource__)
        if self.__select_in_load__:
            selector = selector.options(*self._selectinload())
        return selector

    def _selectinload(self):
        yield from (selectinload(col) for col in self.__select_in_load__)


class ScopedResourceRepository(ResourceSelector[T_dom]):
    __parent_ref__: InstrumentedAttribute[UUID]

    def __init__(self, session: AsyncSession, options: Options, all_data: SQLAlchemyRepository):
        self.session = session
        self.all_data = all_data
        self.options = options

    async def list(self, parent: UUID) -> t.Sequence[T_dom]:
        result = await self.session.scalars(
            self.selector.where(type(self).__parent_ref__ == parent)
        )
        return [obj.to_domain() for obj in result]

    async def get_by_name(self, parent: UUID, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(
                self.selector.where(
                    self.__resource__.name == name, type(self).__parent_ref__ == parent
                ).limit(1)
            )
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        get_kwargs: dict[str, t.Any] = (
            dict(options=list(self._selectinload())) if self.__select_in_load__ else {}
        )
        return to_domain_or_none(await self.session.get(self.__resource__, id, **get_kwargs))

    async def delete(self, id: UUID):
        return await self.session.execute(
            delete(self.__resource__).where(self.__resource__.id == id)
        )

    async def create(self, parent: UUID, obj: T_dom) -> T_dom:
        raise NotImplementedError

    async def update(self, id: UUID, obj: T_dom):
        raise NotImplementedError


class GenericResourceRepository(ResourceSelector[T_dom]):
    __resource__: type[NamedResource[T_dom]]

    def __init__(self, session: AsyncSession, options: Options, all_data: SQLAlchemyRepository):
        self.session = session
        self.options = options
        self.all_data = all_data

    async def list(self) -> t.Sequence[T_dom]:
        result = await self.session.scalars(self.selector)
        return [obj.to_domain() for obj in result]

    async def get_by_name(self, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(self.selector.where(self.__resource__.name == name).limit(1))
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        get_kwargs: dict[str, t.Any] = (
            dict(options=list(self._selectinload())) if self.__select_in_load__ else {}
        )
        return to_domain_or_none(await self.session.get(self.__resource__, id, **get_kwargs))

    async def delete(self, id: UUID):
        return await self.session.execute(
            delete(self.__resource__).where(self.__resource__.id == id)
        )

    async def create(self, obj: T_dom) -> T_dom:
        raise NotImplementedError

    async def update(self, id: UUID, obj: T_dom):
        raise NotImplementedError


class WorkspaceRepository(GenericResourceRepository[Workspace]):
    __resource__ = db.Workspace

    async def create(self, obj: Workspace) -> Workspace:
        return (
            t.cast(
                db.Workspace,
                await self.session.scalar(
                    insert(db.Workspace)
                    .values(name=obj.name, display_name=obj.display_name)
                    .returning(db.Workspace)
                ),
            )
        ).to_domain()

    async def update(self, id: UUID, obj: Workspace):
        # We do not allow updating the workspace name
        await self.session.execute(
            update(db.Workspace).where(db.Workspace.id == id).values(display_name=obj.display_name)
        )


class DatasetTypeRepository(GenericResourceRepository[DatasetType]):
    __resource__ = db.DatasetType

    async def create(self, obj: DatasetType) -> DatasetType:
        return (
            t.cast(
                db.DatasetType,
                await self.session.scalar(
                    insert(db.DatasetType)
                    .values(name=obj.name, format=obj.format, mimetype=obj.mimetype)
                    .returning(db.DatasetType)
                ),
            )
        ).to_domain()

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
            existing = await self.create(dataset_type)
        if existing != dataset_type:
            raise InvalidResource(
                "dataset_type",
                name=dataset_type.name,
                message="incompatible dataset_type already exists",
            )
        return existing


class EntityTypeRepository(GenericResourceRepository[EntityType]):
    __resource__ = db.EntityType

    async def create(self, obj: EntityType) -> EntityType:
        return (
            t.cast(
                db.EntityType,
                await self.session.scalar(
                    insert(db.EntityType).values(name=obj.name).returning(db.EntityType)
                ),
            )
        ).to_domain()

    async def update(self, id: UUID, obj: EntityType):
        await self.session.execute(
            update(db.EntityType).where(db.EntityType.id == id).values(name=obj.name)
        )

    async def ensure_entity_type(self, entity_type: EntityType) -> EntityType:
        existing = await self.get_by_name(entity_type.name)
        if not existing:
            if self.options.STRICT_ENTITY_TYPES:
                raise ResourceDoesNotExist("entity_type", name=entity_type.name)
            existing = await self.create(entity_type)
        return existing


class AttributeTypeRepository(GenericResourceRepository[AttributeType]):
    __resource__ = db.AttributeType

    async def create(self, obj: AttributeType) -> AttributeType:
        return (
            t.cast(
                db.AttributeType,
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
                    .returning(db.AttributeType)
                ),
            )
        ).to_domain()

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
            existing = await self.create(attribute_type)
        if not existing.data_type == attribute_type.data_type:
            raise InvalidResource(
                "attribute_type",
                name=attribute_type.name,
                message="incompatible attribute_type already exists",
            )
        return existing


class DatasetRepository(ScopedResourceRepository[Dataset]):
    __resource__ = db.Dataset
    __parent_ref__ = db.Dataset.workspace_id
    __select_in_load__ = (db.Dataset.workspace, db.Dataset.dataset_type)

    async def get_by_name(self, parent: UUID, name: str) -> Dataset | None:
        return to_domain_or_none(
            await self.session.scalar(
                select(self.__resource__)
                .where(self.__resource__.name == name, type(self).__parent_ref__ == parent)
                .options(*self._selectinload())
                .limit(1)
            )
        )

    async def get_by_id(self, id: UUID) -> Dataset | None:
        return to_domain_or_none(
            await self.session.get(self.__resource__, id, options=list(self._selectinload()))
        )

    async def create(self, parent: UUID, obj: Dataset) -> Dataset:
        dataset_type = await self.all_data.dataset_types.ensure_dataset_type(obj.dataset_type)
        dataset_id = t.cast(
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
        return t.cast(Dataset, await self.get_by_id(dataset_id))

    async def update(self, id: UUID, obj: Dataset):
        current = await self.get_by_id(id)
        if current is None:
            raise ResourceDoesNotExist("dataset_type", id=id)
        await self.session.execute(
            update(db.Dataset)
            .where(db.Dataset.id == id)
            .values(name=obj.name, display_name=obj.display_name)
        )

    async def has_data(self, id: UUID):
        return bool(
            await self.session.scalar(
                select(func.count(RawData.id)).where(RawData.dataset_id == id)
            )
        )  # TODO: add check for entity data

    async def store_data(self, id: UUID, data: DatasetData, format: DatasetFormat, chunk_size=0):
        """Store dataset data for a dataset. The dataset must currently not contain any data

        :param id: A dataset id
        :param data: The dataset data as dict, bytes, BytesIO or pathlib.Path
        :param format: The dataset's ``DatasetFormat``
        :param chunk_size: The maximum chunk size in bytes to store data. By default set to the
            value of DatasetRepository.RAW_DATA_CHUNK_SIZE. This parameter is ignore when the
            dataset format is DatasetFormat.ENTITY_BASED
        """

        if await self.has_data(id):
            raise InvalidResource("dataset", id=id, message="Dataset already has data")

        if format == DatasetFormat.ENTITY_BASED:
            if not isinstance(data, dict):
                raise ValueError("Entity based data must be provided as a dictionary")
            await _EntityDataHandler(self.session, self.all_data).store(id, data)

        if format == DatasetFormat.UNSTRUCTURED:
            await _RawDataHandler(self.session).store(id, data, chunk_size=chunk_size)

        if format == DatasetFormat.BINARY:
            await _RawDataHandler(self.session).store(id, data, chunk_size=chunk_size)

    def stream_binary_data(self, id: UUID, yield_per=1) -> t.AsyncGenerator[bytes]:
        return _RawDataHandler(self.session).stream_bytes(id, yield_per=yield_per)

    def get_unstructured_data(self, id: UUID):
        return _RawDataHandler(self.session).get_dict(id)

    def get_entity_data(self, id: UUID):
        return _EntityDataHandler(self.session, all_data=self.all_data).get(id)


class _EntityDataHandler:
    def __init__(
        self,
        session: AsyncSession,
        all_data: SQLAlchemyRepository,
    ):
        self.session = session
        self.all_data = all_data

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

                data_array: np.ndarray = attr_data["data"]  # type: ignore
                data_id = await self._store_array(data_array)

                rowptr_id = None
                rowptr = get_rowptr(t.cast(dict, attr_data))
                if rowptr is not None:
                    rowptr_id = await self._store_array(rowptr)

                min_val, max_val = data_type.get_min_max(data_array)
                attribute_id = await self.session.scalar(
                    insert(Attribute)
                    .values(
                        entity_type_id=entity_type.id,
                        attribute_type_id=attribute_type.id,
                        data_id=data_id,
                        rowptr_id=rowptr_id,
                        min_val=min_val,
                        max_val=max_val,
                    )
                    .returning(Attribute.id)
                )

                await self.session.execute(
                    insert(DatasetAttribute).values(dataset_id=id, attribute_id=attribute_id)
                )

    async def get(self, id: UUID) -> NumpyDatasetData:
        result: NumpyDatasetData = {}
        for attribute in (
            await self.session.scalars(
                select(Attribute)
                .join(DatasetAttribute)
                .where(DatasetAttribute.dataset_id == id)
                .options(
                    selectinload(Attribute.data),
                    selectinload(Attribute.rowptr),
                    selectinload(Attribute.entity_type),
                    selectinload(Attribute.attribute_type),
                )
            )
        ).all():
            entity_group = result.setdefault(attribute.entity_type.name, {})
            attr_data: NumpyAttributeData = {"data": attribute.data.to_array()}
            if attribute.rowptr is not None:
                attr_data[DEFAULT_ROWPTR_KEY] = attribute.rowptr.to_array()
            entity_group[attribute.attribute_type.name] = attr_data
        return result

    async def _store_array(self, arr: np.ndarray) -> UUID:
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(NumpyArray)
                .values(dtype=arr.dtype.str, shape=arr.shape, data=arr.tobytes())
                .returning(NumpyArray.id)
            ),
        )

    # TODO: We already expect to have numpy data here, so we need to move this function somewhere
    # else. The backend maybe?
    def _data_as_numpy_dict(self, data: dict, filetype: FileType, data_is_numpy=False):
        ""
        finalizer = None

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
            select(RawData).where(RawData.dataset_id == id).limit(1)
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

    async def stream_bytes(
        self, id: UUID | None = None, raw_data: RawData | None = None, yield_per=1
    ) -> t.AsyncGenerator[bytes]:
        if not ((id is None) ^ (raw_data is None)):
            raise ValueError("Supply one of id and raw_data, but not both")

        raw_data = raw_data or await self._ensure_raw_data(t.cast(UUID, id))

        async for chunk in await self.session.stream_scalars(
            select(RawDataChunk.bytes)
            .execution_options(yield_per=yield_per)
            .where(RawDataChunk.raw_data_id == raw_data.id)
            .order_by(RawDataChunk.sequence.asc())
        ):
            yield chunk

    async def get(self, id: UUID | None = None, raw_data: RawData | None = None) -> bytearray:
        result = bytearray()

        async for chunk in self.stream_bytes(id, raw_data):
            result += chunk
        return result

    async def get_dict(self, id: UUID) -> dict:
        raw_data = await self._ensure_raw_data(id)
        if raw_data.encoding != "json":
            raise ValueError(f"Expected dataset encoding 'json', got {raw_data.encoding}")
        raw_bytes = await self.get(id)
        return orjson.loads(raw_bytes)
