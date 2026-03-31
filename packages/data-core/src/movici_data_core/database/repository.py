from __future__ import annotations

import typing as t
from uuid import UUID

from movici_data_core.database import model as db
from movici_data_core.database.model import NamedResource, to_domain_or_none
from movici_data_core.domain_model import Workspace
from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import Options

T_dom = t.TypeVar("T_dom")


class SQLAlchemyRepository:
    def __init__(self, session: AsyncSession, options: Options):
        self.session = session
        self.options = options

    # define these fields as properties to prevent cyclic references and simplify GC
    @property
    def workspaces(self):
        return WorkspaceRepository(self.session, self)


class GenericResourceRepository(t.Generic[T_dom]):
    __resource__: type[NamedResource[T_dom]]

    def __init__(self, session: AsyncSession, all_data: SQLAlchemyRepository):
        self.session = session
        self.all_data = all_data

    async def list(self) -> t.Sequence[T_dom]:
        result = await self.session.scalars(select(self.__resource__))
        return [obj.to_domain() for obj in result]

    async def get_by_name(self, name: str) -> T_dom | None:
        return to_domain_or_none(
            await self.session.scalar(
                select(self.__resource__).where(self.__resource__.name == name).limit(1)
            )
        )

    async def get_by_id(self, id: UUID) -> T_dom | None:
        return to_domain_or_none(await self.session.get(self.__resource__, id))

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
