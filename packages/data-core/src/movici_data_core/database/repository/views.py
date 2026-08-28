from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import delete, insert, select, update

from movici_data_core.database import model as db
from movici_data_core.domain_model import View
from movici_data_core.exceptions import (
    ForeignKeyConstraintFailed,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
    UniqueConstraintFailed,
    map_errors,
)

from .common import SQLResourceRepository, ensure_valid_id, validated_payload


@dataclasses.dataclass
class ViewRepository(SQLResourceRepository):
    """A Repository for managing visualization views.

    :param scenario_id: A Scenario UUID to bind this ViewRepository to. Most methods require the
        repository to be bound, with the exception of :meth:`ViewRepository.get_by_id`. Binding
        generally is performed by the ``SQLAlchemyRepository`` that manages this
        ``ViewRepository``
    """

    scenario_id: UUID | None

    def _ensure_scenario_id(self):
        if self.scenario_id is None:
            raise ValueError("ViewRepository.scenario_id is required")
        return self.scenario_id

    @property
    def selector(self):
        return select(db.VisualizationView)

    async def list(self) -> list[View]:
        """List all views in the active scenario.

        :return: a list of views
        """
        scenario_id = self._ensure_scenario_id()
        result = await self.session.scalars(
            self.selector.where(db.VisualizationView.scenario_id == scenario_id)
        )
        return [view.to_domain() for view in result]

    async def get_by_id(self, id: UUID) -> View | None:
        record = await self.session.scalar(self.selector.where(db.VisualizationView.id == id))
        if record is None:
            return None
        return record.to_domain()

    async def get_by_name(self, name: str) -> View | None:
        scenario_id = self._ensure_scenario_id()
        record = await self.session.scalar(
            self.selector.where(db.VisualizationView.scenario_id == scenario_id).where(
                db.VisualizationView.name == name
            )
        )
        if record is None:
            return None
        return record.to_domain()

    @map_errors(
        (UniqueConstraintFailed, lambda self, obj: ResourceAlreadyExists("view", name=obj.name)),
        (
            ForeignKeyConstraintFailed,
            lambda self, obj: ResourceDoesNotExist("scenario", id=self._ensure_scenario_id()),
        ),
        with_self=True,
    )
    async def create(self, obj: View) -> UUID:
        """Store a :class:``View`` in the database

        :param obj: the ``View`` object
        :return: the UUID of the stored ``View``
        """

        scenario_id = self._ensure_scenario_id()
        payload = validated_payload(db.VisualizationView, obj, ("name", "config"))
        return t.cast(
            UUID,
            await self.session.scalar(
                insert(db.VisualizationView)
                .values(scenario_id=scenario_id, **payload)
                .returning(db.VisualizationView.id)
            ),
        )

    @map_errors(
        (UniqueConstraintFailed, lambda id, obj: ResourceAlreadyExists("view", name=obj.name)),
    )
    @ensure_valid_id
    async def update(self, id: UUID, obj: View):
        """Update a :class:``View`` in the database

        Valid fields to update are: ``name``, ``config``

        :param id: the UUID of the stored ``View``
        :param obj: the ``View`` object with the changes
        """

        payload = validated_payload(db.VisualizationView, obj, ("name", "config"))
        await self.session.execute(
            update(db.VisualizationView).where(db.VisualizationView.id == id).values(**payload)
        )

    @ensure_valid_id
    async def delete(self, id: UUID):
        await self.session.execute(
            delete(db.VisualizationView).where(db.VisualizationView.id == id)
        )
