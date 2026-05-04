from __future__ import annotations

import contextlib
import dataclasses
import io
import pathlib
import typing as t
from uuid import UUID

import numpy as np
import orjson
from sqlalchemy import Insert, Select, delete, exists, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from movici_data_core.database import model as db
from movici_data_core.database.model import NamedResource, Options, to_domain_or_none
from movici_data_core.domain_model import AttributeType, DatasetData, EntityType
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_simulation_core.core import DataType, get_rowptr, infer_data_type_from_array
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.types import DatasetData as NumpyDatasetData
from movici_simulation_core.types import NumpyAttributeData

if t.TYPE_CHECKING:
    from . import SQLAlchemyRepository
T_dom = t.TypeVar("T_dom")


@dataclasses.dataclass
class SQLResourceRepository:
    """Base class for the various resource repositories"""

    session: AsyncSession
    options: Options
    all_data: SQLAlchemyRepository

    async def _exists(self, *where) -> bool:
        return bool(await self.session.scalar(select(exists().where(*where))))


class GenericResourceRepository(SQLResourceRepository, t.Generic[T_dom]):
    """A GenericResourceRepository is the simplest CRUD repository. Resources are globally unique
    by name and do not have a parent (such as a Workspace). Resources that are managed through
    a GenericResourceRepository are:

    * Workspaces
    * DatasetTypes
    * EntityTypes
    * AttributeTypes
    * ModelTypes
    """

    __resource__: type[NamedResource[T_dom]]

    async def list(self) -> list[T_dom]:
        result = await self.session.scalars(select(self.__resource__))
        return [obj.to_domain() for obj in result]

    async def exists(self, name: str) -> bool:
        return await self._exists(self.__resource__.name == name)

    async def get_by_name(self, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(
                select(self.__resource__).where(self.__resource__.name == name).limit(1)
            )
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        return to_domain_or_none(await self.session.get(self.__resource__, id))

    async def delete(self, id: UUID):
        await self.session.execute(delete(self.__resource__).where(self.__resource__.id == id))

    async def create(self, obj: T_dom) -> UUID:
        raise NotImplementedError

    async def update(self, id: UUID, obj: T_dom):
        raise NotImplementedError


class EntityDataSelector(t.Protocol):
    """EntityDataSelector is a Protocol that EntityDataProcessor uses to retrieve SQLAlchemy
    queries for the resource it is operating on, ie Dataset or Update.
    """

    def select_linked_attribute(self, id: UUID) -> Select[tuple[db.Attribute]]: ...
    def insert_linked_attribute(self, id: UUID, attribute_id: UUID) -> Insert: ...


class EntityDataProcessor:
    """Logic for storing and retrieving entity data from the database. This can be used for both
    Dataset data and Update data"""

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

                data_array: np.ndarray = attr_data["data"]
                rowptr = get_rowptr(t.cast(dict, attr_data))

                attribute_id = await self.session.scalar(
                    insert(db.Attribute)
                    .values(
                        entity_type_id=entity_type.id,
                        attribute_type_id=attribute_type.id,
                        length=len(data_array) if rowptr is None else len(rowptr) - 1,
                    )
                    .returning(db.Attribute.id)
                )
                assert attribute_id is not None

                await self._store_data_array(data_array, attribute_id, data_type=data_type)

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


class RawDataProcessor:
    """Logic for storing dataset data as raw bytes in the database. Used for ``BINARY`` and
    ``UNSTRUCTURED`` datasets
    """

    RAW_DATA_CHUNK_SIZE = 100_000_000  # 100 MB

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(
        self, id: UUID | None = None, raw_data: db.RawData | None = None
    ) -> tuple[str | None, bytearray]:
        result = bytearray()
        encoding, gen = await self.stream_bytes(id, raw_data)
        async for chunk in gen:
            result += chunk
        return encoding, result

    async def stream_bytes(
        self, id: UUID | None = None, raw_data: db.RawData | None = None, yield_per=1
    ) -> tuple[str | None, t.AsyncGenerator[bytes]]:
        """
        :returns: a tuple (encoding, bytestreamer). The bytestreamer can be used as an async
            generator
        """
        if not ((id is None) ^ (raw_data is None)):
            raise ValueError("Supply one of id and raw_data, but not both")

        raw_data = raw_data or await self._ensure_raw_data(t.cast(UUID, id))

        async def _bytestreamer():
            async for chunk in await self.session.stream_scalars(
                select(db.RawDataChunk.bytes)
                .execution_options(yield_per=yield_per)
                .where(db.RawDataChunk.raw_data_id == raw_data.id)
                .order_by(db.RawDataChunk.sequence.asc())
            ):
                yield chunk

        return raw_data.encoding, _bytestreamer()

    async def get_dict(self, id: UUID) -> dict:
        raw_data = await self._ensure_raw_data(id)
        if raw_data.encoding != "json":
            raise ValueError(f"Expected dataset encoding 'json', got {raw_data.encoding}")
        _, raw_bytes = await self.get(raw_data=raw_data)
        return t.cast(dict, orjson.loads(raw_bytes))

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

    async def _ensure_raw_data(self, id: UUID) -> db.RawData:
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
