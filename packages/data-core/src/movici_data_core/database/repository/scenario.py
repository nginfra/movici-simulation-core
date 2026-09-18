from __future__ import annotations

import copy
import dataclasses
import itertools
import typing as t
from uuid import UUID

from sqlalchemy import ColumnElement, delete, exists, insert, select, update
from sqlalchemy.orm import joinedload, selectinload

from movici_data_core import bounding_box
from movici_data_core.database import model as db
from movici_data_core.domain_model import (
    AttributeSummary,
    BoundingBox,
    DatasetSummary,
    EntityGroupSummary,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
)
from movici_data_core.exceptions import (
    ForeignKeyConstraintFailed,
    InvalidAction,
    MoviciValidationError,
    ResourceAlreadyExists,
    ResourceDoesNotExist,
    UniqueConstraintFailed,
    map_errors,
)
from movici_data_core.validators import ModelConfigValidator

from .common import SQLResourceRepository, validated_payload_dict


@dataclasses.dataclass
class ScenarioRepository(SQLResourceRepository):
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None

    def for_id(self, scenario_id: UUID):
        """Bind the ScenarioRepository to a specific scenario"""
        if scenario_id == self.scenario_id:
            return self
        self._ensure_not_single_scenario_mode()
        return dataclasses.replace(self, scenario_id=scenario_id)

    def _ensure_workspace_id(self) -> UUID:
        if self.workspace_id is None:
            raise ValueError("ScenarioRepository.workspace_id is required")
        return self.workspace_id

    def _ensure_scenario_id(self):
        if self.scenario_id is None:
            raise ValueError("ScenarioRepository.scenario_id is required")
        return self.scenario_id

    def _ensure_not_single_scenario_mode(self):
        if self.options.mode == db.DatabaseMode.SINGLE_SCENARIO:
            raise InvalidAction("Unsupported operation for this mode")

    async def list(self) -> list[Scenario]:
        """List all scenarios in the active workspace"""
        workspace_id = self._ensure_workspace_id()
        result = await self.session.execute(
            select(
                db.Scenario,
                exists().where(db.Update.scenario_id == db.Scenario.id),
            )
            .options(joinedload(db.Scenario.workspace))
            .where(db.Scenario.workspace_id == workspace_id)
        )
        return [obj.to_domain(has_updates) for (obj, has_updates) in result]

    @property
    def selector(self):
        return select(
            db.Scenario,
            exists().where(db.Update.scenario_id == db.Scenario.id),
        ).options(
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

    async def exists(self):
        id = self._ensure_scenario_id()
        return await self._exists(db.Scenario.id == id)

    async def _get_one_full_scenario(self, where_clause: ColumnElement[bool]):
        result = (await self.session.execute(self.selector.where(where_clause).limit(1))).first()

        if result is None:
            return None

        scenario, has_updates = result
        bounding_box = await self._get_bounding_box(scenario.id)
        return dataclasses.replace(
            scenario.to_domain(has_updates),
            bounding_box=bounding_box,
            datasets=[
                ds.to_domain() for ds in sorted(scenario.datasets, key=lambda ds: ds.sequence)
            ],
            models=[
                model.to_domain()
                for model in sorted(scenario.models, key=lambda model: model.sequence)
            ],
        )

    async def get_by_name(self, name: str) -> Scenario | None:
        """Get a scenario by name, in the active workspace"""
        workspace_id = self._ensure_workspace_id()

        return await self._get_one_full_scenario(
            (db.Scenario.name == name) & (db.Scenario.workspace_id == workspace_id)
        )

    async def get(self) -> Scenario | None:
        """Get the active scenario from the database

        :return: The Scenario, or None if it does not exist
        """
        id = self._ensure_scenario_id()
        return await self._get_one_full_scenario(db.Scenario.id == id)

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

    @map_errors(
        (ForeignKeyConstraintFailed, lambda: InvalidAction("Cannot delete default scenario"))
    )
    async def delete(self):
        """Delete de active scenario, if it exists"""
        id = self._ensure_scenario_id()
        await self.session.execute(
            delete(db.Attribute).where(
                db.Attribute.id.in_(
                    select(db.UpdateAttribute.attribute_id)
                    .join(db.Update)
                    .where(db.Update.scenario_id == id)
                )
            )
        )
        await self.session.execute(delete(db.Scenario).where(db.Scenario.id == id))

    @map_errors(
        (
            UniqueConstraintFailed,
            lambda self, obj, validator: ResourceAlreadyExists("scenario", name=obj.name),
        ),
        (
            ForeignKeyConstraintFailed,
            lambda self, obj, validator: ResourceDoesNotExist(
                "workspace", id=self._ensure_workspace_id()
            ),
        ),
        with_self=True,
    )
    async def create(self, obj: Scenario, validator: ModelConfigValidator) -> UUID:
        """Store a new Scenario in the database. This method can only be invoked if there is no
        currently active Scenario, to prevent creating scenarios when in a ``SINGLE_SCENARIO`` mode

        :param obj: The scenario to create
        :param validator: A ModelConfigValidator that is instantiated with all available models in
            the dataset
        :return: the newly created Scenario UUID
        """

        self._ensure_not_single_scenario_mode()
        workspace_id = self._ensure_workspace_id()
        payload = validated_payload_dict(
            db.Scenario,
            name=obj.name,
            display_name=obj.display_name,
            description=obj.description,
            status=obj.status,
            simulation_info=dataclasses.asdict(obj.simulation_info),
            epsg_code=obj.epsg_code,
        )
        scenario_id = await self.session.scalar(
            insert(db.Scenario)
            .values(workspace_id=workspace_id, **payload)
            .returning(db.Scenario.id)
        )
        assert scenario_id is not None
        await self._store_scenario_details(workspace_id, scenario_id, obj, validator)
        return scenario_id

    @map_errors(
        (
            UniqueConstraintFailed,
            lambda obj, validator: ResourceAlreadyExists("scenario", name=obj.name),
        )
    )
    async def update(self, obj: Scenario, validator: ModelConfigValidator):
        """Update a scenario in the database. The scenario to update must be the active scenario

        :param obj: The scenario payload
        :param validator: A ModelConfigValidator that is instantiated with all available models in
            the dataset
        """
        id = self._ensure_scenario_id()
        current = await self.get()
        if current is None:
            raise ResourceDoesNotExist("scenario", id=id)
        assert current.workspace is not None
        assert current.workspace.id is not None

        payload = validated_payload_dict(
            db.Scenario,
            name=obj.name,
            display_name=obj.display_name,
            description=obj.description,
            simulation_info=dataclasses.asdict(obj.simulation_info),
            epsg_code=obj.epsg_code,
        )
        await self.session.execute(
            update(db.Scenario).where(db.Scenario.id == id).values(**payload)
        )
        await self.session.execute(
            delete(db.ScenarioDataset).where(db.ScenarioDataset.scenario_id == id)
        )
        await self.session.execute(
            delete(db.ScenarioModel).where(db.ScenarioModel.scenario_id == id)
        )

        await self._store_scenario_details(current.workspace.id, id, obj, validator)

    async def ensure_valid_scenario_dataset(self, dataset_name_or_id: str) -> ScenarioDataset:
        """Verify that a dataset, by name or id, is a valid dataset in the active scenario and
        return the ScenarioDataset. This method requires that the ScenarioRepository has a
        ``scenario_id`` set
        :param dataset_name_or_id: a ``str`` with either a dataset name or a uuid. The uuid is cast
        to a ``UUID`` before comparing against the database
        """
        scenario_id = self._ensure_scenario_id()
        try:
            dataset_id = UUID(dataset_name_or_id)
            where_clause = db.ScenarioDataset.dataset_id == dataset_id
            not_found_payload = dict(id=dataset_id)
        except ValueError:
            # could not cast to UUID, dataset_name_or_id is a name instead
            where_clause = db.Dataset.name == dataset_name_or_id
            not_found_payload = dict(name=dataset_name_or_id)

        result = await self.session.scalar(
            select(db.ScenarioDataset)
            .join(db.Dataset)
            .where(where_clause)
            .where(db.ScenarioDataset.scenario_id == scenario_id)
            .options(
                joinedload(db.ScenarioDataset.dataset).joinedload(db.Dataset.dataset_type),
            )
        )
        if result is None:
            raise ResourceDoesNotExist(
                "scenario_dataset",
                message="dataset does not exist for this scenario",
                **t.cast(dict, not_found_payload),
            )
        return result.to_domain()

    async def get_summary(self, dataset_id: UUID):
        """Request a DatasetSummary for the dataset id in the active scenario. This method
        requires that the ScenarioRepository has a ``scenario_id`` set

        :param dataset_id: the dataset id
        :return: A ``DatasetSummary``
        """
        scenario_id = self._ensure_scenario_id()
        if not await self._exists(db.Scenario.id == scenario_id):
            raise ResourceDoesNotExist("scenario", id=scenario_id)
        dataset = await self.session.scalar(
            select(db.Dataset)
            .join(db.ScenarioDataset)
            .where(db.ScenarioDataset.dataset_id == dataset_id)
            .where(db.ScenarioDataset.scenario_id == scenario_id)
        )
        if dataset is None:
            raise ResourceDoesNotExist(
                "scenario_dataset",
                id=dataset_id,
                message="dataset does not exist for this scenario",
            )

        attributes_from_dataset = await self.session.execute(
            select(db.Attribute, db.DataArray.min_val, db.DataArray.max_val)
            .join(db.DataArray, db.DataArray.attribute_id == db.Attribute.id)
            .join(db.DatasetAttribute)
            .options(
                joinedload(db.Attribute.attribute_type),
                joinedload(db.Attribute.entity_type),
            )
            .where(db.DatasetAttribute.dataset_id == dataset_id)
        )
        attributes_from_updates = await self.session.execute(
            select(db.Attribute, db.DataArray.min_val, db.DataArray.max_val)
            .join(db.DataArray, db.DataArray.attribute_id == db.Attribute.id)
            .join(db.UpdateAttribute)
            .join(db.Update)
            .options(
                joinedload(db.Attribute.attribute_type),
                joinedload(db.Attribute.entity_type),
            )
            .where(db.Update.scenario_id == scenario_id)
            .where(db.Update.dataset_id == dataset_id)
        )
        attribute_summaries: dict[str, dict[str, AttributeSummary]] = {}
        entity_counts: dict[str, int] = {}

        for (attribute, min_val, max_val), is_dataset in itertools.chain(
            zip(attributes_from_dataset, itertools.repeat(True)),
            zip(attributes_from_updates, itertools.repeat(False)),
        ):
            attribute_type = attribute.attribute_type
            attribute_name = attribute_type.name
            entity_group_name = attribute.entity_type.name

            if attribute.attribute_type.name == "id" and is_dataset:
                # we currently do not support creating new entities through updates, so all
                # entities must exist in the dataset. We therefore only need to check the length
                # of the entity array in the dataset.
                entity_counts[entity_group_name] = attribute.length

            entity_summary = attribute_summaries.setdefault(entity_group_name, {})
            if (attribute_summary := entity_summary.get(attribute_name)) is not None:
                if attribute_summary.min_val is None:
                    attribute_summary.min_val = min_val
                elif min_val is not None:
                    attribute_summary.min_val = min(attribute_summary.min_val, min_val)

                if attribute_summary.max_val is None:
                    attribute_summary.max_val = max_val
                elif max_val is not None:
                    attribute_summary.max_val = max(attribute_summary.max_val, max_val)
            else:
                entity_summary[attribute_name] = AttributeSummary(
                    name=attribute_type.name,
                    data_type=attribute_type.data_type,
                    description=attribute_type.description,
                    unit=attribute_type.unit,
                    enum_name=attribute_type.enum_name,
                    min_val=min_val,
                    max_val=max_val,
                )

        return DatasetSummary(
            general=dataset.general or {},
            epsg_code=dataset.epsg_code,
            # taking only the bounding box from the dataset assumes that the entities do
            # not move during a simulation. This is ok for now since we do not support moving
            # entities in the visualization yet either
            bounding_box=BoundingBox.from_tuple_or_none(dataset.bounding_box),
            entity_groups=sorted(
                (
                    EntityGroupSummary(
                        name=name,
                        count=entity_counts.get(name, 0),
                        attributes=sorted(attributes.values(), key=lambda attr: attr.name),
                    )
                    for name, attributes in attribute_summaries.items()
                ),
                key=lambda eg: eg.name,
            ),
            count=sum(count for count in entity_counts.values()),
        )

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
            self._check_duplicate_datasets(obj.datasets)
            try:
                scenario_datasets = await repository.datasets.ensure_scenario_datasets(
                    obj.datasets
                )
            except MoviciValidationError as e:
                raise MoviciValidationError.from_errors(e, path="datasets") from e
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
            [model.type for model in obj.models]
        )

        validator = validator.for_scenario(scenario_datasets, model_types)
        try:
            scenario_models = validator.process_model_configs(obj.models)
        except MoviciValidationError as e:
            raise MoviciValidationError.from_errors(e, path="models") from e

        # both self.all_data.model_types.ensure_model_types and validator.process_model_configs
        # return a list the length of obj.models. Let's assert that to be absolutely sure
        assert len(scenario_models) == len(model_types) == len(obj.models)

        self._check_duplicate_models(scenario_models)
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

    @staticmethod
    def _check_duplicate_datasets(datasets: t.Sequence[ScenarioDataset]):
        found = set()
        for idx, ds in enumerate(datasets):
            if ds.name in found:
                raise MoviciValidationError("duplicate dataset in scenario", f"datasets.{idx}")
            found.add(ds.name)

    @staticmethod
    def _check_duplicate_models(datasets: t.Sequence[ScenarioModel]):
        found = set()
        for idx, ds in enumerate(datasets):
            if ds.name in found:
                raise MoviciValidationError("duplicate model name in scenario", f"models.{idx}")
            found.add(ds.name)

    @staticmethod
    def _stripped_config(scenario_model: ScenarioModel):
        result = copy.deepcopy(scenario_model.config)
        result.pop("name", None)
        result.pop("type", None)
        for ref in scenario_model.references:
            ref.unset_value(result)
        return result
