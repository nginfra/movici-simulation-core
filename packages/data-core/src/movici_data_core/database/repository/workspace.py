from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import func, insert, select, update

from movici_data_core.database import model as db
from movici_data_core.domain_model import Workspace

from .common import GenericResourceRepository


class WorkspaceRepository(GenericResourceRepository[Workspace]):
    __resource__ = db.Workspace

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

    async def get_by_name(self, name: str) -> Workspace | None:
        result = await super().get_by_name(name)
        return await self._with_counts(result)

    async def get_by_id(self, id: UUID) -> Workspace | None:
        result = await super().get_by_id(id)
        return await self._with_counts(result)

    async def _with_counts(self, workspace: Workspace | None) -> Workspace | None:
        if workspace is None:
            return workspace
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
        await self.session.execute(
            update(db.Workspace)
            .where(db.Workspace.id == id)
            .values(name=obj.name, display_name=obj.display_name)
        )
