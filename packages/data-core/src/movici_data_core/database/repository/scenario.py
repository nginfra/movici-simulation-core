from __future__ import annotations

import copy
import dataclasses
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import joinedload, selectinload

from movici_data_core import bounding_box
from movici_data_core.database import model as db
from movici_data_core.domain_model import (
    BoundingBox,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
)
from movici_data_core.exceptions import InvalidAction, MoviciValidationError, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.validate import MoviciDataRefInfo

from .common import SQLResourceRepository


@dataclasses.dataclass
class ScenarioRepository(SQLResourceRepository):
    """A"""

    workspace_id: UUID | None = None
    scenario_id: UUID | None = None

    def for_id(self, scenario_id: UUID):
        """Bind the ScenarioRepository to a specific scenario"""
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
        """List all scenarios in the active workspace"""
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
        """checks whether a scenario with a specific name exists in the active workspace
        :return: bool
        """
        workspace_id = self._ensure_workspace_id()
        return await self._exists(
            db.Scenario.workspace_id == workspace_id, db.Scenario.name == name
        )

    async def get_by_name(self, name: str) -> Scenario | None:
        """Get a scenario by name, in the active workspace"""
        workspace_id = self._ensure_workspace_id()
        record = await self.session.scalar(
            self.selector.where(db.Scenario.name == name, db.Scenario.workspace_id == workspace_id)
        )
        if record is None:
            return None
        bounding_box = await self._get_bounding_box(record.id)
        return self._load_full_scenario(record, bounding_box=bounding_box)

    async def get(self) -> Scenario | None:
        """Get the active scenario from the database

        :return: The Scenario, or None if it does not exist
        """
        id = self._ensure_scenario_id()
        record = await self.session.scalar(self.selector.where(db.Scenario.id == id))
        if record is None:
            return None
        bounding_box = await self._get_bounding_box(record.id)
        return self._load_full_scenario(record, bounding_box=bounding_box)

    async def _get_bounding_box(self, scenario_id: UUID):
        bboxs_from_datasets = await self.session.scalars(
            select(db.Dataset.bounding_box)
            .join(db.ScenarioDataset)
            .where(db.ScenarioDataset.scenario_id == scenario_id)
        )
        bboxs_from_updates = await self.session.scalars(
            select(db.Update.bounding_box)
            .where(db.Update.scenario_id == scenario_id)
            .where(db.Update.bounding_box.isnot(None))
        )
        return bounding_box.calculate_new_bounding_box(
            *(BoundingBox.from_tuple_or_none(bb) for bb in bboxs_from_datasets),
            *(BoundingBox.from_tuple_or_none(bb) for bb in bboxs_from_updates),
        )

    async def delete(self):
        """Delete de active scenario, if it exists"""
        id = self._ensure_scenario_id()
        await self.session.execute(delete(db.Scenario).where(db.Scenario.id == id))

    async def create(self, obj: Scenario, validator: ModelConfigValidator) -> UUID:
        """Store a new Scenario in the database. This method can only be invoked if there is no
        currently active Scenario, to prevent creating scenarios when in a ``SINGLE_SCENARIO`` mode

        :param obj: The scenario to create
        :param validator: A ModelConfigValidator that is instantiated with all available models in
            the dataset
        :return: the newly created Scenario UUID
        """

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
                simulation_info=dataclasses.asdict(obj.simulation_info),
                epsg_code=obj.epsg_code,
            )
            .returning(db.Scenario.id)
        )
        assert scenario_id is not None
        await self._store_scenario_details(workspace_id, scenario_id, obj, validator)
        return scenario_id

    async def update(self, obj: Scenario, validator: ModelConfigValidator):
        """Update a scenario in the database. The scenario to update must be the active scenario

        :param obj: The sc
        :param validator: A ModelConfigValidator that is instantiated with all available models in
            the dataset
        """
        id = self._ensure_scenario_id()
        current = await self.get()
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
                simulation_info=dataclasses.asdict(obj.simulation_info),
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

    # TODO: test this, and perhaps rethink how to deal with scenariostatus (see TODO for
    # ScenarioStatus)
    async def set_status(self, status: ScenarioStatus):
        """Set the ScenarioStatus for the active scenario"""
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
            [model["type"] for model in obj.models if "type" in model]
        )

        validator = validator.for_scenario(scenario_datasets, model_types)
        try:
            scenario_models = validator.process_model_configs(obj.models)
        except MoviciValidationError as e:
            raise MoviciValidationError.from_errors(e, path="models") from e

        # In the previous step where we create the model_type list, there is the possibility of
        # a model config that does not specify a type, and we potentially end up with a list of
        # model_types that is shorter that the number of scenario_models. However, validation must
        # have caught this and raise an error if a model does not have a "type" field. So we
        # can assert that we always have the correct length of lists here
        assert len(scenario_models) == len(model_types)
        scenario_model_records = await self.session.scalars(
            insert(db.ScenarioModel).returning(db.ScenarioModel),
            [
                {
                    "name": model.name,
                    "scenario_id": scenario_id,
                    "model_type_id": model_type.id,
                    "sequence": idx,
                    "config": self._stripped_config(model),
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
                    id=record.id, scenario_model=scenario_model
                )
            )

        if refs_to_add:
            await self.session.execute(insert(db.ScenarioModelReference), refs_to_add)

    @classmethod
    def _load_full_scenario(cls, scenario: db.Scenario, bounding_box: BoundingBox) -> Scenario:
        return dataclasses.replace(
            scenario.to_domain(),
            bounding_box=bounding_box,
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
    def _stripped_config(scenario_model: ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        result.pop("name", None)
        result.pop("type", None)
        for ref in scenario_model.references:
            ref.unset_value(result)
        return result
