from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update

from movici_data_core.database import model as db
from movici_data_core.domain_model import Workspace
from movici_data_core.exceptions import (
    ForeignKeyConstraintFailed,
    InvalidAction,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
    UniqueConstraintFailed,
    map_errors,
)

from .common import GenericResourceRepository, ensure_valid_id


class WorkspaceRepository(GenericResourceRepository[Workspace]):
    __resource__ = db.Workspace
    __resource_type_name__ = "workspace"

    async def list(self) -> list[Workspace]:
        result = await super().list()

        dataset_counts: dict[UUID, int] = {
            k: v
            for k, v in await self.session.execute(
                select(db.Workspace.id, func.count(db.Dataset.id))
                .join(db.Dataset)
                .group_by(db.Workspace.id)
            )
        }
        scenario_counts: dict[UUID, int] = {
            k: v
            for k, v in await self.session.execute(
                select(db.Workspace.id, func.count(db.Scenario.id))
                .join(db.Scenario)
                .group_by(db.Workspace.id)
            )
        }
        return [
            dataclasses.replace(
                ws,
                dataset_count=dataset_counts.get(t.cast(UUID, ws.id), 0),
                scenario_count=scenario_counts.get(t.cast(UUID, ws.id), 0),
            )
            for ws in result
        ]

    async def with_counts(self, workspace: Workspace) -> Workspace:
        """add :attr:`Workspace.dataset_count` and :attr:`Workspace.scenario_count` to the
        workspace. The workspace must have been previously loaded from the database
        """
        assert workspace.id is not None
        return dataclasses.replace(
            workspace,
            dataset_count=t.cast(
                int,
                await self.session.scalar(
                    select(func.count(1)).where(db.Dataset.workspace_id == workspace.id)
                ),
            ),
            scenario_count=t.cast(
                int,
                await self.session.scalar(
                    select(func.count(1)).where(db.Scenario.workspace_id == workspace.id)
                ),
            ),
        )

    @map_errors(
        (UniqueConstraintFailed, lambda obj: ResourceAlreadyExists("workspace", name=obj.name))
    )
    async def create(self, obj: Workspace) -> UUID:
        """Store a :class:``Workspace`` in the database

        :param obj: the ``Workspace`` object
        :return: the UUID of the stored ``ModelType``
        """
        payload = self._validated_payload(obj, ("name", "display_name"))
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Workspace).values(**payload).returning(db.Workspace.id)
            ),
        )

    @map_errors(
        (UniqueConstraintFailed, lambda id, obj: ResourceAlreadyExists("workspace", name=obj.name))
    )
    async def update(self, id: UUID, obj: Workspace):
        """Update a :class:``Workspace`` in the database

        Valid fields to update are: ``name``, ``display_name``

        :param id: the UUID of the stored ``Workspace``
        :param obj: the ``Workspace`` object with the changes
        """
        if (current := await self.get_by_id(id)) is None:
            raise ResourceDoesNotExist(self.__resource_type_name__, id=id)

        if self.options.IMMUTABLE_WORKSPACE_NAMES and current.name != obj.name:
            raise InvalidAction("cannot update workspace name, it is immutable")

        payload = self._validated_payload(obj, ("name", "display_name"))
        await self.session.execute(
            update(db.Workspace).where(db.Workspace.id == id).values(**payload)
        )

    @ensure_valid_id
    @map_errors(
        (
            ForeignKeyConstraintFailed,
            lambda id: InvalidAction("Cannot delete default workspace"),
        )
    )
    async def delete(self, id: UUID):
        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.DatasetAttribute.attribute_id)
                    .join(db.Dataset)
                    .where(db.Dataset.workspace_id == id)
                )
            )
        )

        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.UpdateAttribute.attribute_id)
                    .join(db.Update)
                    .join(db.Scenario)
                    .where(db.Scenario.workspace_id == id)
                )
            )
        )
        await self.session.execute(delete(self.__resource__).where(self.__resource__.id == id))
