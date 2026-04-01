from __future__ import annotations

import typing as t
from uuid import UUID

from movici_data_core.database import model as db
from movici_data_core.database.model import NamedResource, Options, to_domain_or_none
from movici_data_core.domain_model import Dataset, DatasetFormat, DatasetType, Workspace
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, selectinload

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
