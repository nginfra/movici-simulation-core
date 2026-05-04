from __future__ import annotations

import copy
import dataclasses
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import joinedload, selectinload

from movici_data_core.database import model as db
from movici_data_core.domain_model import (
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
)
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.validate import MoviciDataRefInfo

from .common import SQLResourceRepository


@dataclasses.dataclass
class ScenarioRepository(SQLResourceRepository):
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None

    def for_id(self, scenario_id: UUID):
        self._ensure_no_scenario_id()
        return dataclasses.replace(self, scenario_id=scenario_id)

    def _ensure_workspace_id(self) -> UUID:
        if self.workspace_id is None:
            raise ValueError("ScenarioRepository.workspace_id is required")
        return self.workspace_id

    def _ensure_scenario_id(self):
        if self.scenario_id is None:
            raise ValueError("ScenarioRepository.scenario_id is required")
        return self.scenario_id

    def _ensure_no_scenario_id(self):
        if self.scenario_id is not None:
            raise InvalidAction("Unsupported operation for this mode")

    async def list(self) -> list[Scenario]:
        workspace_id = self._ensure_workspace_id()
        result = await self.session.scalars(
            select(db.Scenario)
            .options(joinedload(db.Scenario.workspace))
            .where(db.Scenario.workspace_id == workspace_id)
        )
        return [obj.to_domain() for obj in result]

    @property
    def selector(self):
        return select(db.Scenario).options(
            joinedload(db.Scenario.workspace),
            selectinload(db.Scenario.datasets)
            .joinedload(db.ScenarioDataset.dataset)
            .joinedload(db.Dataset.dataset_type),
            selectinload(db.Scenario.models).options(
                joinedload(db.ScenarioModel.model_type),
                selectinload(db.ScenarioModel.references).options(
                    joinedload(db.ScenarioModelReference.dataset),
                    joinedload(db.ScenarioModelReference.entity_type),
                    joinedload(db.ScenarioModelReference.attribute_type),
                ),
            ),
        )

    async def exists_by_name(self, name: str):
        workspace_id = self._ensure_workspace_id()
        return await self._exists(
            db.Scenario.workspace_id == workspace_id, db.Scenario.name == name
        )

    async def exists(self):
        id = self._ensure_scenario_id()
        return await self._exists(db.Scenario.id == id)

    async def get_by_name(self, name: str) -> Scenario | None:
        workspace_id = self._ensure_workspace_id()
        record = await self.session.scalar(
            self.selector.where(db.Scenario.name == name, db.Scenario.workspace_id == workspace_id)
        )
        if record is None:
            return None
        return self.load_full_scenario(record)

    async def get_by_id(self) -> Scenario | None:
        id = self._ensure_scenario_id()
        record = await self.session.scalar(self.selector.where(db.Scenario.id == id))
        if record is None:
            return None
        return self.load_full_scenario(record)

    async def delete(self):
        id = self._ensure_scenario_id()
        await self.session.execute(delete(db.Scenario).where(db.Scenario.id == id))

    async def create(self, obj: Scenario, validator: ModelConfigValidator) -> UUID:
        self._ensure_no_scenario_id()
        workspace_id = self._ensure_workspace_id()
        scenario_id = await self.session.scalar(
            insert(db.Scenario)
            .values(
                workspace_id=workspace_id,
                name=obj.name,
                display_name=obj.display_name,
                description=obj.description,
                status=obj.status,
                simulation_info=obj.simulation_info,
                epsg_code=obj.epsg_code,
            )
            .returning(db.Scenario.id)
        )
        assert scenario_id is not None
        await self._store_scenario_details(workspace_id, scenario_id, obj, validator)
        return scenario_id

    async def update(self, obj: Scenario, validator: ModelConfigValidator):
        id = self._ensure_scenario_id()
        current = await self.get_by_id()
        if current is None:
            raise ResourceDoesNotExist("scenario", id=id)
        assert current.workspace is not None
        assert current.workspace.id is not None

        await self.session.execute(
            update(db.Scenario)
            .where(db.Scenario.id == id)
            .values(
                name=obj.name,
                display_name=obj.display_name,
                description=obj.description,
                simulation_info=obj.simulation_info,
                epsg_code=obj.epsg_code,
            )
        )
        await self.session.execute(
            delete(db.ScenarioDataset).where(db.ScenarioDataset.scenario_id == id)
        )
        await self.session.execute(
            delete(db.ScenarioModel).where(db.ScenarioModel.scenario_id == id)
        )

        await self._store_scenario_details(current.workspace.id, id, obj, validator)

    async def set_status(self, status: ScenarioStatus):
        id = self._ensure_scenario_id()
        await self.session.execute(
            update(db.Scenario).where(db.Scenario.id == id).values(status=status)
        )

    async def _store_scenario_details(
        self,
        workspace_id: UUID,
        scenario_id: UUID,
        obj: Scenario,
        validator: ModelConfigValidator,
    ):
        repository = self.all_data.for_workspace(workspace_id)
        scenario_datasets = []
        if obj.datasets:
            scenario_datasets = await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset(ds["name"], ds["type"]) for ds in obj.datasets]
            )
            await self.session.execute(
                insert(db.ScenarioDataset),
                [
                    {"scenario_id": scenario_id, "dataset_id": ds.id, "sequence": idx}
                    for idx, ds in enumerate(scenario_datasets)
                ],
            )
        if not obj.models:
            return

        model_types = await self.all_data.model_types.ensure_model_types(
            [model["type"] for model in obj.models if "name" in model]
        )

        validator = validator.for_scenario(scenario_datasets, model_types)
        scenario_models = validator.process_model_configs(obj.models)
        scenario_model_records = await self.session.scalars(
            insert(db.ScenarioModel).returning(db.ScenarioModel),
            [
                {
                    "name": model.name,
                    "scenario_id": scenario_id,
                    "model_type_id": model_type.id,
                    "sequence": idx,
                    "config": self.stripped_config(model),
                }
                for idx, (model, model_type) in enumerate(zip(scenario_models, model_types))
            ],
        )
        refs_to_add: list[dict] = []
        for scenario_model, record in zip(
            scenario_models, sorted(scenario_model_records, key=lambda r: r.sequence)
        ):
            refs_to_add.extend(
                validator.iter_scenario_model_references(
                    dataclasses.replace(scenario_model, id=record.id)
                )
            )

        if refs_to_add:
            await self.session.execute(insert(db.ScenarioModelReference), refs_to_add)

    @classmethod
    def load_full_scenario(cls, scenario: db.Scenario) -> Scenario:
        return dataclasses.replace(
            scenario.to_domain(),
            datasets=[
                cls._load_scenario_dataset(ds)
                for ds in sorted(scenario.datasets, key=lambda ds: ds.sequence)
            ],
            models=[
                cls._load_scenario_model(model)
                for model in sorted(scenario.models, key=lambda model: model.sequence)
            ],
        )

    @staticmethod
    def _load_scenario_dataset(scenario_dataset: db.ScenarioDataset):
        return {
            "id": scenario_dataset.dataset_id,
            "name": scenario_dataset.dataset.name,
            "type": scenario_dataset.dataset.dataset_type.name,
        }

    @classmethod
    def _load_scenario_model(cls, scenario_model: db.ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        for data_ref in scenario_model.references:
            value = None
            if data_ref.dataset is not None:
                value = data_ref.dataset.name
            elif data_ref.entity_type is not None:
                value = data_ref.entity_type.name
            elif data_ref.attribute_type is not None:
                value = data_ref.attribute_type.name
            MoviciDataRefInfo.from_path_string(data_ref.path, value).set_value(result)

        result["name"] = scenario_model.name
        result["type"] = scenario_model.model_type.name
        return result

    @staticmethod
    def stripped_config(scenario_model: ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        result.pop("name", None)
        result.pop("type", None)
        for ref in scenario_model.references:
            ref.unset_value(result)
        return result
