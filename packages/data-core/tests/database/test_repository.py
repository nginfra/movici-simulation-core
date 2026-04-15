import dataclasses
import uuid
from io import BytesIO
from unittest.mock import patch

import numpy as np
import pytest
from movici_data_core.database import model as db
from movici_data_core.database.repository import DatasetDataRepository, SQLAlchemyRepository
from movici_data_core.domain_model import (
    AttributeType,
    Dataset,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    Update,
    Workspace,
)
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from sqlalchemy import func, select

from movici_simulation_core.core import DataType
from movici_simulation_core.testing import assert_dataset_dicts_equal


class TestWorkspaceRepository:
    async def test_get_workspace_by_id(self, repository: SQLAlchemyRepository, a_workspace):
        assert a_workspace.id is not None
        found = await repository.workspaces.get_by_id(a_workspace.id)
        assert a_workspace == found

    async def test_get_workspace_by_name(self, repository: SQLAlchemyRepository, a_workspace):
        found = await repository.workspaces.get_by_name(a_workspace.name)
        assert a_workspace == found

    async def test_get_non_existing_workspace_by_name(self, repository: SQLAlchemyRepository):
        assert (await repository.workspaces.get_by_name("invalid")) is None

    async def test_get_non_existing_workspace_by_id(self, repository: SQLAlchemyRepository):
        assert (await repository.workspaces.get_by_id(uuid.uuid4())) is None

    async def test_created_workspace_gets_a_uuid(self, repository: SQLAlchemyRepository):
        workspace_id = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert int(workspace_id) > 0

    async def test_create_and_delete_a_workspace(self, repository: SQLAlchemyRepository):
        existing = len(await repository.workspaces.list())
        workspace_id = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert len(await repository.workspaces.list()) == existing + 1

        await repository.workspaces.delete(workspace_id)

        assert len(await repository.workspaces.list()) == existing

    async def test_update_workspace(
        self, repository: SQLAlchemyRepository, a_workspace: Workspace
    ):
        assert a_workspace.id is not None
        assert a_workspace.display_name != "New Name"

        await repository.workspaces.update(
            a_workspace.id, dataclasses.replace(a_workspace, display_name="New Name")
        )
        updated = await repository.workspaces.get_by_id(a_workspace.id)
        assert updated is not None
        assert updated.display_name == "New Name"


class TestDatasetTypeRepository:
    async def test_create_and_delete_a_dataset_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.dataset_types.list())
        dataset_type_id = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )

        assert dataset_type_id is not None
        assert len(await repository.dataset_types.list()) == existing + 1

        await repository.dataset_types.delete(dataset_type_id)

        assert len(await repository.dataset_types.list()) == existing

    async def test_update_dataset_type(self, repository: SQLAlchemyRepository):

        dataset_type = DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)

        dataset_type_id = await repository.dataset_types.create(dataset_type)

        await repository.dataset_types.update(
            dataset_type_id, dataclasses.replace(dataset_type, name="new_name")
        )
        updated = await repository.dataset_types.get_by_id(dataset_type_id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_change_format(self, repository: SQLAlchemyRepository):
        dataset_type = DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        dataset_type_id = await repository.dataset_types.create(dataset_type)

        dataset_type.format = DatasetFormat.UNSTRUCTURED
        with pytest.raises(InvalidAction):
            await repository.dataset_types.update(
                dataset_type_id, dataclasses.replace(dataset_type, name="new_name")
            )

    async def test_returns_existing_dataset_type_when_compatible(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True
        found = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
        )
        assert found == a_dataset_type

    async def test_raises_on_non_existing_dataset_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_DATASET_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.dataset_types.ensure_dataset_type(
                DatasetType(name="non-existing", format=DatasetFormat.ENTITY_BASED)
            )

    async def test_automatically_creates_dataset_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_DATASET_TYPES = False

        dataset_type = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
        )

        assert dataset_type is not None
        assert dataset_type.name == "transport_network"
        assert dataset_type.id is not None

    async def test_raises_on_incompatible_existing_dataset_type(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = False

        with pytest.raises(InvalidResource):
            await repository.dataset_types.ensure_dataset_type(
                DatasetType(name="transport_network", format=DatasetFormat.BINARY)
            )


class TestEntityTypeRepository:
    async def test_create_and_delete_an_entity_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.entity_types.list())
        entity_type_id = await repository.entity_types.create(EntityType(name="some_entity_type"))
        assert len(await repository.entity_types.list()) == existing + 1

        await repository.entity_types.delete(entity_type_id)

        assert len(await repository.entity_types.list()) == existing

    async def test_update_entity_type(
        self, repository: SQLAlchemyRepository, an_entity_type: EntityType
    ):
        assert an_entity_type.id is not None

        await repository.entity_types.update(
            an_entity_type.id, dataclasses.replace(an_entity_type, name="new_name")
        )
        updated = await repository.entity_types.get_by_id(an_entity_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_returns_existing_entity_type_when_compatible(
        self, repository: SQLAlchemyRepository, an_entity_type
    ):
        repository.options.STRICT_ENTITY_TYPES = True
        found = await repository.entity_types.ensure_entity_type(EntityType(an_entity_type.name))
        assert found is not None
        assert found.id == an_entity_type.id

    async def test_raises_on_non_existing_entity_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ENTITY_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.entity_types.ensure_entity_type(EntityType("new_type"))

    async def test_automatically_creates_entity_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ENTITY_TYPES = False

        entity_type = await repository.entity_types.ensure_entity_type(EntityType("new_type"))

        assert entity_type is not None
        assert entity_type.name == "new_type"
        assert entity_type.id is not None


class TestAttributeTypeRepository:
    async def test_created_attribute_type_has_data_type(self, repository: SQLAlchemyRepository):
        data_type = DataType(int, (2,), csr=True)
        await repository.attribute_types.create(
            AttributeType("attribute_type", data_type=data_type)
        )
        attribute_type = await repository.attribute_types.get_by_name("attribute_type")
        assert attribute_type is not None
        assert attribute_type.data_type == data_type

    async def test_create_and_delete_an_attribute_type(self, repository: SQLAlchemyRepository):
        existing = len(await repository.attribute_types.list())
        attribute_type_id = await repository.attribute_types.create(
            AttributeType(name="some_attribute_type", data_type=DataType(float))
        )
        assert len(await repository.attribute_types.list()) == existing + 1

        await repository.attribute_types.delete(attribute_type_id)

        assert len(await repository.attribute_types.list()) == existing

    async def test_update_attribute_type(
        self, repository: SQLAlchemyRepository, an_attribute_type: AttributeType
    ):
        assert an_attribute_type.id is not None

        await repository.attribute_types.update(
            an_attribute_type.id, dataclasses.replace(an_attribute_type, name="new_name")
        )
        updated = await repository.attribute_types.get_by_id(an_attribute_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_update_data_type_if_in_use(
        self,
        repository: SQLAlchemyRepository,
        an_attribute_type: AttributeType,
        a_dataset,
        an_entity_type,
    ):
        assert an_attribute_type.id is not None

        await repository.dataset_data.create(
            a_dataset.id,
            {
                an_entity_type.name: {
                    an_attribute_type.name: {
                        "data": np.array([1.0, 2.0]),
                    },
                }
            },
            format=DatasetFormat.ENTITY_BASED,
        )
        with pytest.raises(InvalidAction):
            await repository.attribute_types.update(
                an_attribute_type.id,
                dataclasses.replace(an_attribute_type, data_type=DataType(int)),
            )

    async def test_returns_existing_attribute_type_when_compatible(
        self, repository: SQLAlchemyRepository, an_attribute_type
    ):
        repository.options.STRICT_ATTRIBUTES = True
        found = await repository.attribute_types.ensure_attribute_type(
            AttributeType("some.attribute", data_type=DataType(float))
        )
        assert found is not None
        assert found.id == an_attribute_type.id

    async def test_raises_on_non_existing_attribute_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ATTRIBUTES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.attribute_types.ensure_attribute_type(
                AttributeType("some.attribute", data_type=DataType(float))
            )

    async def test_automatically_creates_attribute_type_when_not_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_ATTRIBUTES = False

        attribute_type = await repository.attribute_types.ensure_attribute_type(
            AttributeType("some.attribute", data_type=DataType(float))
        )

        assert attribute_type is not None
        assert attribute_type.name == "some.attribute"
        assert attribute_type.id is not None

    async def test_raises_on_incompatible_existing_attribute_type(
        self, repository: SQLAlchemyRepository, an_attribute_type
    ):
        repository.options.STRICT_ATTRIBUTES = False

        with pytest.raises(InvalidResource):
            await repository.attribute_types.ensure_attribute_type(
                AttributeType("some.attribute", data_type=DataType(int))
            )


class TestModelTypeRepository:
    @pytest.fixture
    async def a_model_type(self, repository: SQLAlchemyRepository):
        model_type_id = await repository.model_types.create(
            ModelType(name="some_model", jsonschema={"some": "schema"})
        )
        return await repository.model_types.get_by_id(model_type_id)

    async def test_created_model_type_has_schema(self, a_model_type):
        assert a_model_type.jsonschema == {"some": "schema"}

    async def test_update_model_type(
        self, a_model_type: ModelType, repository: SQLAlchemyRepository
    ):
        assert a_model_type.id is not None

        await repository.model_types.update(
            a_model_type.id, ModelType("another_name", {"some": "othershema"})
        )

        updated = await repository.model_types.get_by_name("another_name")
        assert updated is not None
        assert updated.jsonschema == {"some": "othershema"}

    async def test_returns_existing_model_type(
        self, repository: SQLAlchemyRepository, a_model_type
    ):
        repository.options.STRICT_MODEL_TYPES = True
        found = await repository.model_types.ensure_model_types(["some_model"])
        assert found == [a_model_type]

    async def test_raises_on_non_existing_model_type_when_strict(
        self, repository: SQLAlchemyRepository
    ):
        repository.options.STRICT_MODEL_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.model_types.ensure_model_types(["non-existing"])

    async def test_automatically_creates_model_type_with_passall_schema_when_not_strict(
        self, repository: SQLAlchemyRepository, a_model_type
    ):
        repository.options.STRICT_MODEL_TYPES = False

        created, existing = await repository.model_types.ensure_model_types(
            ["new", a_model_type.name]
        )
        assert existing == a_model_type
        assert created is not None
        assert created.name == "new"
        assert created.jsonschema == {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": "/new/1.0.0",
            "type": "object",
            "additionalProperties": True,
        }


class TestDatasetRepository:
    async def test_get_dataset_with_workspace_and_dataset_type(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        dataset = await repository.datasets.get_by_id(a_dataset.id)
        assert dataset is not None
        assert isinstance(dataset.workspace, Workspace)
        assert isinstance(dataset.dataset_type, DatasetType)

    async def test_create_dataset(
        self, repository: SQLAlchemyRepository, a_workspace, a_dataset_type
    ):
        dataset_id = await repository.for_workspace(a_workspace.id).datasets.create(
            Dataset("another_dataset", "Another Dataset", dataset_type=a_dataset_type)
        )
        assert int(dataset_id) > 0

    async def test_update_dataset(self, repository: SQLAlchemyRepository, a_dataset):
        await repository.datasets.update(
            a_dataset.id, dataclasses.replace(a_dataset, name="new_name")
        )
        updated = await repository.datasets.get_by_id(a_dataset.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_raises_on_invalid_dataset_type_when_strict(
        self, repository: SQLAlchemyRepository, a_workspace, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True

        with pytest.raises(InvalidResource):
            await repository.for_workspace(a_workspace.id).datasets.create(
                Dataset(
                    "some_dataset",
                    "some dataset",
                    dataset_type=DatasetType(a_dataset_type.name, format=DatasetFormat.BINARY),
                ),
            )

    async def test_delete_dataset_deletes_data(self, repository: SQLAlchemyRepository, a_dataset):
        with patch.object(DatasetDataRepository, "delete") as mock:
            await repository.datasets.delete(a_dataset.id)
            mock.assert_awaited_once_with(a_dataset.id)

    async def test_returns_existing_datasets(self, repository: SQLAlchemyRepository, a_dataset):
        repository.options.STRICT_SCENARIO_DATASETS = True
        another_dataset_id = await repository.datasets.create(
            Dataset(
                "another_dataset",
                "another_dataset",
                DatasetType("tabular", format=DatasetFormat.UNSTRUCTURED),
            ),
        )
        another_dataset = await repository.datasets.get_by_id(another_dataset_id)
        assert another_dataset is not None

        found = await repository.datasets.ensure_scenario_datasets(
            [
                ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
                ScenarioDataset(another_dataset.name, another_dataset.dataset_type.name),
            ],
        )
        assert [ds.id for ds in found] == [a_dataset.id, another_dataset.id]

    async def test_raises_on_missing_dataset_when_strict(self, repository: SQLAlchemyRepository):
        repository.options.STRICT_SCENARIO_DATASETS = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset("non-existing", type="transport_network")],
            )

    async def test_automatically_creates_dataset_stubs_when_not_strict(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        repository.options.STRICT_SCENARIO_DATASETS = False

        scenario_datasets = await repository.datasets.ensure_scenario_datasets(
            [
                ScenarioDataset("new", "transport_network"),
                ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
                ScenarioDataset("new_tapefile", "tabular"),
            ],
        )
        assert [ds.name for ds in scenario_datasets] == ["new", a_dataset.name, "new_tapefile"]
        assert [ds.type for ds in scenario_datasets] == [
            "transport_network",
            a_dataset.dataset_type.name,
            "tabular",
        ]
        assert None not in [ds.id for ds in scenario_datasets]

    async def test_raises_on_missing_dataset_type(self, repository: SQLAlchemyRepository):
        repository.options.STRICT_SCENARIO_DATASETS = False

        with pytest.raises(ResourceDoesNotExist):
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset("new", "unknown_type")]
            )

    async def test_raises_on_existing_dataset_with_incorrect_type(
        self, repository: SQLAlchemyRepository, a_dataset
    ):

        repository.options.STRICT_SCENARIO_DATASETS = False

        with pytest.raises(InvalidResource):
            await repository.datasets.ensure_scenario_datasets(
                [ScenarioDataset(name=a_dataset.name, type="tabular")]
            )


class TestDatasetDataRepository:
    @pytest.mark.parametrize("method", ["path", "bytes", "bytesio"])
    async def test_store_and_retrieve_raw_data_bytes(
        self, repository: SQLAlchemyRepository, a_dataset, method, tmp_path
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        raw_bytes = b"somethingbinarydata"
        data = None
        if method == "path":
            data = tmp_path / "data.bin"
            data.write_bytes(raw_bytes)
        elif method == "bytes":
            data = raw_bytes
        elif method == "bytesio":
            data = BytesIO(raw_bytes)
        assert data is not None

        await repository.dataset_data.create(
            a_dataset.id, data, format=DatasetFormat.BINARY, chunk_size=2
        )
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = b""
        n_chunks = 0
        async for chunk in repository.dataset_data.stream_binary_data(a_dataset.id):
            result += chunk
            n_chunks += 1
        assert n_chunks == len(raw_bytes) // 2 + 1
        assert result == raw_bytes

    async def test_store_and_retrieve_unstructured_data(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        data = {"some": "data"}
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.UNSTRUCTURED)
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = await repository.dataset_data.get_unstructured_data(a_dataset.id)
        assert result == data

    async def test_store_and_retrieve_entity_data(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        assert not await repository.dataset_data.exists_for(a_dataset.id)
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                },
                a_csr_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                    "indptr": np.array([0, 2, 2]),
                },
            }
        }
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        assert await repository.dataset_data.exists_for(a_dataset.id)
        result = await repository.dataset_data.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    async def test_store_multiple_entity_data_retrieve_one(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        another_dataset = Dataset("another_dataset", "Another Dataset", a_dataset.dataset_type)

        another_dataset_id = await repository.datasets.create(another_dataset)
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                }
            }
        }
        await repository.dataset_data.create(
            another_dataset_id,
            {
                an_entity_type.name: {
                    a_csr_attribute_type.name: {
                        "data": np.array([1.0, 2.0]),
                        "indptr": np.array([0, 2, 2]),
                    },
                }
            },
            format=DatasetFormat.ENTITY_BASED,
        )
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        result = await repository.dataset_data.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    async def test_deletes_entity_data(
        self, repository: SQLAlchemyRepository, a_dataset, an_entity_type, an_attribute_type
    ):
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                }
            }
        }
        await repository.dataset_data.create(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        attribute_count = await repository.session.scalar(select(func.count(db.Attribute.id)))
        assert attribute_count != 0

        await repository.dataset_data.delete(a_dataset.id)

        attribute_count = await repository.session.scalar(select(func.count(db.Attribute.id)))
        assert attribute_count == 0

    async def test_deletes_raw_data(self, repository: SQLAlchemyRepository, a_dataset):
        raw_bytes = b"somethingbinarydata"

        await repository.dataset_data.create(a_dataset.id, raw_bytes, format=DatasetFormat.BINARY)
        data_count = await repository.session.scalar(select(func.count(db.RawData.id)))
        assert data_count != 0

        await repository.dataset_data.delete(a_dataset.id)

        data_count = await repository.session.scalar(select(func.count(db.RawData.id)))
        assert data_count == 0


class TestScenarioRepository:
    async def test_scenario_round_trip(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        default_model_types,
        get_model_config_validator,
    ):
        validator = await get_model_config_validator()
        scenario = Scenario(
            name="some_scenario",
            workspace=a_dataset.workspace,
            display_name="Some Scenario",
            description="Scenario for testing",
            epsg_code=28992,
            simulation_info={"some": "info"},
            datasets=[
                {
                    "name": a_dataset.name,
                    "type": a_dataset.dataset_type.name,
                }
            ],
            models=[
                {
                    "name": "model1",
                    "type": default_model_types[0].name,
                    "dataset": a_dataset.name,
                    "entity_group": "transport_nodes",
                    "attribute": "id",
                },
                {
                    "name": "model2",
                    "type": default_model_types[1].name,
                    "field": "value",
                },
            ],
        )
        scenario_id = await repository.scenarios.create(scenario, validator)
        result = await repository.scenarios.get_by_id(scenario_id)
        assert result is not None

        assert result.id is not None
        assert result.created_at is not None
        assert result.updated_at is not None
        assert result.datasets[0].pop("id") == a_dataset.id
        assert dataclasses.replace(result, id=None, created_at=None, updated_at=None) == scenario

    async def test_get_scenario_by_name(self, repository: SQLAlchemyRepository, a_scenario):
        result = await repository.scenarios.get_by_name(a_scenario.name)
        assert result is not None

    async def test_update_scenario(
        self, repository: SQLAlchemyRepository, a_scenario: Scenario, get_model_config_validator
    ):

        validator = await get_model_config_validator()

        assert a_scenario is not None
        assert a_scenario.id is not None

        a_scenario.name = "new_name"
        a_scenario.models = list(reversed(a_scenario.models))
        await repository.scenarios.update(a_scenario.id, a_scenario, validator)

        result = await repository.scenarios.get_by_id(a_scenario.id)

        assert result is not None
        assert result.name == a_scenario.name
        assert result.models == a_scenario.models

    async def test_delete_scenario_deletes_scenario_datasets(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        query = (
            select(func.count())
            .select_from(db.ScenarioDataset)
            .where(db.ScenarioDataset.scenario_id == a_scenario.id)
        )
        assert (await repository.session.scalar(query)) != 0
        await repository.scenarios.delete(a_scenario.id)
        assert len(await repository.scenarios.list()) == 0
        assert (await repository.session.scalar(query)) == 0

    async def test_delete_scenario_deletes_scenario_models(
        self, repository: SQLAlchemyRepository, a_scenario
    ):
        query = (
            select(func.count())
            .select_from(db.ScenarioModel)
            .where(db.ScenarioModel.scenario_id == a_scenario.id)
        )
        assert (await repository.session.scalar(query)) != 0
        await repository.scenarios.delete(a_scenario.id)
        await repository.session.commit()
        assert len(await repository.scenarios.list()) == 0
        assert (await repository.session.scalar(query)) == 0


class TestUpdateRepository:
    @pytest.fixture
    def repository_for_scenario(self, repository: SQLAlchemyRepository, a_scenario):
        return repository.for_scenario(a_scenario.id)

    @pytest.fixture
    async def create_update(
        self,
        repository: SQLAlchemyRepository,
        a_scenario,
        a_dataset,
        an_attribute_type,
        an_entity_type,
    ):
        async def _create_update(timestamp, iteration, ids, array, scenario_id=None):
            scenario_id = scenario_id or a_scenario.id
            update = Update(
                dataset=ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
                timestamp=timestamp,
                iteration=iteration,
                model_name=a_scenario.models[0]["name"],
                model_type=a_scenario.models[0]["type"],
                data={
                    an_entity_type.name: {
                        "id": {"data": np.asarray(ids)},
                        an_attribute_type.name: {"data": np.asarray(array)},
                    }
                },
            )

            return await repository.for_scenario(scenario_id).updates.create(update)

        return _create_update

    async def test_update_round_trip(
        self,
        a_scenario,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        repository_for_scenario: SQLAlchemyRepository,
    ):
        update = Update(
            dataset=ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
            timestamp=12,
            iteration=2,
            model_name=a_scenario.models[0]["name"],
            model_type=a_scenario.models[0]["type"],
            data={
                an_entity_type.name: {
                    "id": {"data": np.asarray([0, 1])},
                    an_attribute_type.name: {"data": np.asarray([1.0, 2.0])},
                }
            },
        )

        update_id = await repository_for_scenario.updates.create(update)

        result = await repository_for_scenario.updates.get_by_id(update_id)
        assert result is not None
        assert dataclasses.replace(update, data=None, id=update_id) == dataclasses.replace(
            result, data=None
        )
        assert_dataset_dicts_equal(update.data, result.data)

    async def test_gets_all_updates_in_order(
        self, create_update, repository_for_scenario: SQLAlchemyRepository
    ):
        update1 = await create_update(timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0])
        update4 = await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        update2 = await create_update(timestamp=2, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        update3 = await create_update(timestamp=2, iteration=2, ids=[0, 1], array=[2.0, 3.0])
        all_updates = await repository_for_scenario.updates.list()
        assert [upd.id for upd in all_updates] == [update1, update2, update3, update4]

    async def test_deletes_all_updates_for_scenario_but_not_others(
        self,
        a_scenario,
        create_update,
        repository_for_scenario: SQLAlchemyRepository,
        create_scenario,
    ):
        another_scenario_id = await create_scenario(
            dataclasses.replace(a_scenario, name="another_scenario")
        )
        await create_update(timestamp=6, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=1, ids=[0, 1], array=[2.0, 3.0])
        await create_update(timestamp=2, iteration=2, ids=[0, 1], array=[2.0, 3.0])
        await create_update(
            scenario_id=another_scenario_id, timestamp=1, iteration=0, ids=[0, 1], array=[1.0, 2.0]
        )

        assert len(await repository_for_scenario.updates.list()) == 3
        assert (
            len(await repository_for_scenario.for_scenario(another_scenario_id).updates.list())
            == 1
        )

        await repository_for_scenario.updates.delete_all()

        assert len(await repository_for_scenario.updates.list()) == 0
        assert (
            len(await repository_for_scenario.for_scenario(another_scenario_id).updates.list())
            == 1
        )
