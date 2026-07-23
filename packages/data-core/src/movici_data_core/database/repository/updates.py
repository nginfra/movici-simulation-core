from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

import sqlalchemy.exc
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import joinedload

from movici_data_core.database import model as db
from movici_data_core.domain_model import Update
from movici_data_core.exceptions import (
    InvalidAction,
    MoviciValidationError,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
    UniqueConstraintFailed,
    map_errors,
)

from .common import EntityDataProcessor, EntityDataSelector, SQLResourceRepository


@dataclasses.dataclass
class UpdateRepository(SQLResourceRepository):
    """A Repository for managing Updates. In contrast to other resources, Updates are immutable and
    can only be created (added to a scenario). The only way to delete an update is by deleting all
    updates for a Scenario, thereby effectively resetting the Scenario

    :param scenario_id: A Scenario UUID to bind this UpdateRepository to. Most methods require the
        repository to be bound, with the exception of :meth:`UpdateRepository.get_by_id`. Binding
        generally is performed by the ``SQLAlchemyRepository`` that manages this
        ``UpdateRepository``
    """

    scenario_id: UUID | None

    def _ensure_scenario_id(self):
        if self.scenario_id is None:
            raise ValueError("UpdateRepository.scenario_id is required")
        return self.scenario_id

    @property
    def selector(self):
        return select(db.Update).options(
            joinedload(db.Update.dataset).joinedload(db.Dataset.dataset_type),
            joinedload(db.Update.model_type),
        )

    async def list(self) -> list[Update]:
        """List all updates in the active scenario.

        :return: a list of Updates, these Updates do not contain any data
        """
        scenario_id = self._ensure_scenario_id()
        result = await self.session.scalars(
            self.selector.where(db.Update.scenario_id == scenario_id).order_by(
                db.Update.timestamp, db.Update.iteration
            )
        )
        return [update.to_domain() for update in result]

    async def exists(self) -> bool:
        """Does the active scenario have any updates?"""
        scenario_id = self._ensure_scenario_id()
        return await self._exists(db.Update.scenario_id == scenario_id)

    async def get_by_id(self, id: UUID, with_data=False) -> Update | None:
        record = await self.session.scalar(self.selector.where(db.Update.id == id))
        if record is None:
            return None
        result = record.to_domain()
        if with_data:
            result = dataclasses.replace(result, data=await self._get_data(id=id))
        return result

    async def _get_data(self, id: UUID) -> dict:
        return await EntityDataProcessor(
            self.session, all_data=self.all_data, selector=UpdateDataSelector()
        ).get(id)

    @map_errors(
        (
            UniqueConstraintFailed,
            lambda obj: ResourceAlreadyExists("update", name=f"t{obj.timestamp}_{obj.iteration}"),
        ),
        (
            sqlalchemy.exc.IntegrityError,
            lambda obj: InvalidAction("Could not create update"),
        ),
    )
    async def create(self, obj: Update) -> UUID:
        """
        Store an Update to the active scenario.

        :param obj: the Update to add, including data
        :return: the newly created Update UUID
        """
        scenario_id = self._ensure_scenario_id()
        if not isinstance(obj.data, dict):
            raise InvalidAction("update data must be a numpy dataset dict")
        model_type_id = await self.session.scalar(
            select(db.ModelType.id)
            .join(db.ScenarioModel)
            .where(db.ScenarioModel.scenario_id == scenario_id)
            .where(db.ScenarioModel.name == obj.model.name)
        )
        if model_type_id is None:
            if not (await self._exists(db.Scenario.id == scenario_id)):
                raise ResourceDoesNotExist("scenario", id=scenario_id)
            raise MoviciValidationError(
                f"{obj.model.name} is not a valid model for this scenario", "model.name"
            )
        dataset = await self.session.scalar(
            select(db.Dataset)
            .options(joinedload(db.Dataset.dataset_type))
            .join(db.ScenarioDataset)
            .where(db.ScenarioDataset.scenario_id == scenario_id)
            .where(db.Dataset.name == obj.dataset.name)
        )
        if dataset is None:
            raise ResourceDoesNotExist("dataset", name=obj.dataset.name)

        update_id = t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Update)
                .values(
                    scenario_id=scenario_id,
                    timestamp=obj.timestamp,
                    iteration=obj.iteration,
                    model_type_id=model_type_id,
                    model_name=obj.model.name,
                    bounding_box=obj.bounding_box.as_tuple_or_none(),
                    dataset_id=dataset.id,
                )
                .returning(db.Update.id)
            ),
        )
        await EntityDataProcessor(self.session, self.all_data, UpdateDataSelector()).store(
            update_id, obj.data
        )
        return update_id

    async def delete_all(self):
        """Delete all updates for the active scenario. Should be combined with a separate call, to
        the Scenario, resetting the ScenarioStatus
        """

        scenario_id = self._ensure_scenario_id()
        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.UpdateAttribute.attribute_id)
                    .join(db.Update)
                    .where(db.Update.scenario_id == scenario_id)
                )
            )
        )
        await self.session.execute(delete(db.Update).where(db.Update.scenario_id == scenario_id))


class UpdateDataSelector(EntityDataSelector):
    """Subclass of EntityDataSelector to be use for Updates"""

    def select_linked_attribute(self, id: UUID):
        return (
            select(db.Attribute).join(db.UpdateAttribute).where(db.UpdateAttribute.update_id == id)
        )

    def insert_linked_attribute(self, id: UUID, attribute_id: UUID):
        return insert(db.UpdateAttribute).values(update_id=id, attribute_id=attribute_id)
