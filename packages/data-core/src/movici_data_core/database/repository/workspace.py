from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import func, insert, select, update

from movici_data_core.database import model as db
from movici_data_core.domain_model import Workspace

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

    async def create(self, obj: Workspace) -> UUID:

        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Workspace)
                .values(name=obj.name, display_name=obj.display_name)
                .returning(db.Workspace.id)
            ),
        )

    @ensure_valid_id
    async def update(self, id: UUID, obj: Workspace):
        await self.session.execute(
            update(db.Workspace)
            .where(db.Workspace.id == id)
            .values(name=obj.name, display_name=obj.display_name)
        )
