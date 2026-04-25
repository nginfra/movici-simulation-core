from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import joinedload

from movici_data_core.database import model as db
from movici_data_core.domain_model import Update
from movici_data_core.exceptions import (
    InvalidAction,
    MoviciValidationError,
    ResourceDoesNotExist,
)

from .common import EntityDataProcessor, EntityDataSelector, SQLResourceRepository


@dataclasses.dataclass
class UpdateRepository(SQLResourceRepository):
    scenario_id: UUID

    @property
    def selector(self):
        return select(db.Update).options(
            joinedload(db.Update.dataset).joinedload(db.Dataset.dataset_type),
            joinedload(db.Update.model_type),
        )

    async def list(self) -> list[Update]:
        result = await self.session.scalars(
            self.selector.where(db.Update.scenario_id == self.scenario_id).order_by(
                db.Update.timestamp, db.Update.iteration
            )
        )
        return [update.to_domain() for update in result]

    async def exists(self):
        return await self._exists(db.Update.scenario_id == self.scenario_id)

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
            data=await EntityDataProcessor(
                self.session, all_data=self.all_data, selector=UpdateDataSelector()
            ).get(id),
        )

    async def create(self, obj: Update) -> UUID:
        """
        :param parent: A Scenario id
        """
        if not isinstance(obj.data, dict):
            raise InvalidAction("update data must be a numpy dataset dict")
        model_type_id = await self.session.scalar(
            select(db.ModelType.id)
            .join(db.ScenarioModel)
            .where(db.ScenarioModel.scenario_id == self.scenario_id)
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
            .where(db.ScenarioDataset.scenario_id == self.scenario_id)
            .where(db.Dataset.name == obj.dataset.name)
        )
        if dataset is None:
            raise ResourceDoesNotExist("dataset", name=obj.dataset.name)

        update_id = t.cast(
            UUID,
            await self.session.scalar(
                insert(db.Update)
                .values(
                    scenario_id=self.scenario_id,
                    timestamp=obj.timestamp,
                    iteration=obj.iteration,
                    model_type_id=model_type_id,
                    model_name=obj.model_name,
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
        await self.session.execute(
            delete(db.Update).where(db.Update.scenario_id == self.scenario_id)
        )


class UpdateDataSelector(EntityDataSelector):
    def select_linked_attribute(self, id: UUID):
        return (
            select(db.Attribute).join(db.UpdateAttribute).where(db.UpdateAttribute.update_id == id)
        )

    def insert_linked_attribute(self, id: UUID, attribute_id: UUID):
        return insert(db.UpdateAttribute).values(update_id=id, attribute_id=attribute_id)
