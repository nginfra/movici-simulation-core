import dataclasses
import uuid
from io import BytesIO

import numpy as np
import pytest
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import (
    AttributeType,
    Dataset,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    Workspace,
)
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist

from movici_simulation_core.core import DataType
from movici_simulation_core.testing import assert_dataset_dicts_equal


class TestSQLAlchemyRepository:
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

    async def test_created_workspace_gets_a_uuid(self, repository):
        workspace = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert int(workspace.id) > 0

    async def test_create_and_delete_a_workspace(self, repository: SQLAlchemyRepository):
        assert len(await repository.workspaces.list()) == 0
        workspace = await repository.workspaces.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert workspace.id is not None
        assert len(await repository.workspaces.list()) == 1

        await repository.workspaces.delete(workspace.id)

        assert len(await repository.workspaces.list()) == 0

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
        dataset_type = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id is not None
        assert len(await repository.dataset_types.list()) == existing + 1

        await repository.dataset_types.delete(dataset_type.id)

        assert len(await repository.dataset_types.list()) == existing

    async def test_update_dataset_type(self, repository: SQLAlchemyRepository):
        dataset_type = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id is not None

        await repository.dataset_types.update(
            dataset_type.id, dataclasses.replace(dataset_type, name="new_name")
        )
        updated = await repository.dataset_types.get_by_id(dataset_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_change_format(self, repository: SQLAlchemyRepository):
        dataset_type = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id

        dataset_type.format = DatasetFormat.UNSTRUCTURED
        with pytest.raises(InvalidAction):
            await repository.dataset_types.update(
                dataset_type.id, dataclasses.replace(dataset_type, name="new_name")
            )

    async def test_returns_existing_dataset_type_when_compatible(
        self, repository: SQLAlchemyRepository, a_dataset_type
    ):
        repository.options.STRICT_DATASET_TYPES = True
        found = await repository.dataset_types.ensure_dataset_type(
            DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
        )
        assert found is not None
        assert found.id == a_dataset_type.id

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
        entity_type = await repository.entity_types.create(EntityType(name="some_entity_type"))
        assert entity_type.id is not None
        assert len(await repository.entity_types.list()) == existing + 1

        await repository.entity_types.delete(entity_type.id)

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
        attribute_type = await repository.attribute_types.create(
            AttributeType(name="some_attribute_type", data_type=DataType(float))
        )
        assert attribute_type.id is not None
        assert len(await repository.attribute_types.list()) == existing + 1

        await repository.attribute_types.delete(attribute_type.id)

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

        await repository.datasets.store_data(
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
        return await repository.model_types.create(
            ModelType(name="some_model", jsonschema={"some": "schema"})
        )

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
        dataset = await repository.datasets.create(
            a_workspace.id,
            Dataset("another_dataset", "Another Dataset", dataset_type=a_dataset_type),
        )
        assert dataset is not None and dataset.id is not None
        assert int(dataset.id) > 0

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
            await repository.datasets.create(
                a_workspace.id,
                Dataset(
                    "some_dataset",
                    "some dataset",
                    dataset_type=DatasetType(a_dataset_type.name, format=DatasetFormat.BINARY),
                ),
            )

    @pytest.mark.parametrize("method", ["path", "bytes", "bytesio"])
    async def test_store_and_retrieve_raw_data_bytes(
        self, repository: SQLAlchemyRepository, a_dataset, method, tmp_path
    ):
        assert not await repository.datasets.has_data(a_dataset.id)
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

        await repository.datasets.store_data(
            a_dataset.id, data, format=DatasetFormat.BINARY, chunk_size=2
        )
        assert await repository.datasets.has_data(a_dataset.id)
        result = b""
        n_chunks = 0
        async for chunk in repository.datasets.stream_binary_data(a_dataset.id):
            result += chunk
            n_chunks += 1
        assert n_chunks == len(raw_bytes) // 2 + 1
        assert result == raw_bytes

    async def test_store_and_retrieve_unstructured_data(
        self, repository: SQLAlchemyRepository, a_dataset
    ):
        assert not await repository.datasets.has_data(a_dataset.id)
        data = {"some": "data"}
        await repository.datasets.store_data(a_dataset.id, data, format=DatasetFormat.UNSTRUCTURED)
        assert await repository.datasets.has_data(a_dataset.id)
        result = await repository.datasets.get_unstructured_data(a_dataset.id)
        assert result == data

    async def test_store_and_retrieve_entity_data(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        assert not await repository.datasets.has_data(a_dataset.id)
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
        await repository.datasets.store_data(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        assert await repository.datasets.has_data(a_dataset.id)
        result = await repository.datasets.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    async def test_store_multiple_entity_data_retrieve_one(
        self,
        repository: SQLAlchemyRepository,
        a_dataset,
        an_entity_type,
        an_attribute_type,
        a_csr_attribute_type,
    ):
        another_dataset = await repository.datasets.create(
            a_dataset.workspace.id,
            Dataset("another_dataset", "Another Dataset", a_dataset.dataset_type),
        )
        assert another_dataset.id is not None
        data = {
            an_entity_type.name: {
                an_attribute_type.name: {
                    "data": np.array([1.0, 2.0]),
                }
            }
        }
        await repository.datasets.store_data(
            another_dataset.id,
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
        await repository.datasets.store_data(a_dataset.id, data, format=DatasetFormat.ENTITY_BASED)
        result = await repository.datasets.get_entity_data(a_dataset.id)
        assert_dataset_dicts_equal(data, result)

    async def test_returns_existing_datasets(self, repository: SQLAlchemyRepository, a_dataset):
        repository.options.STRICT_SCENARIO_DATASETS = True
        another_dataset = await repository.datasets.create(
            a_dataset.workspace.id,
            Dataset(
                "another_dataset",
                "another_dataset",
                DatasetType("tabular", format=DatasetFormat.UNSTRUCTURED),
            ),
        )
        assert another_dataset.id is not None

        found = await repository.datasets.ensure_scenario_datasets(
            a_dataset.workspace.id,
            [
                ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
                ScenarioDataset(another_dataset.name, another_dataset.dataset_type.name),
            ],
        )
        assert [ds.id for ds in found] == [a_dataset.id, another_dataset.id]

    async def test_raises_on_missing_dataset_when_strict(
        self, repository: SQLAlchemyRepository, a_workspace
    ):
        repository.options.STRICT_SCENARIO_DATASETS = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.datasets.ensure_scenario_datasets(
                a_workspace.id,
                [ScenarioDataset("non-existing", type="transport_network")],
            )

    async def test_automatically_creates_dataset_stubs_when_not_strict(
        self, repository: SQLAlchemyRepository, a_workspace, a_dataset
    ):
        repository.options.STRICT_SCENARIO_DATASETS = False

        scenario_datasets = await repository.datasets.ensure_scenario_datasets(
            a_workspace.id,
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

    async def test_raises_on_missing_dataset_type(
        self, repository: SQLAlchemyRepository, a_workspace
    ):
        repository.options.STRICT_SCENARIO_DATASETS = False

        with pytest.raises(ResourceDoesNotExist):
            await repository.datasets.ensure_scenario_datasets(
                a_workspace.id, [ScenarioDataset("new", "unknown_type")]
            )

    async def test_raises_on_existing_dataset_with_incorrect_type(
        self, repository: SQLAlchemyRepository, a_dataset
    ):

        repository.options.STRICT_SCENARIO_DATASETS = False

        with pytest.raises(InvalidResource):
            await repository.datasets.ensure_scenario_datasets(
                a_dataset.workspace.id, [ScenarioDataset(name=a_dataset.name, type="tabular")]
            )


class TestScenarioRepository:
    @pytest.fixture
    def scenario(self, default_model_types, a_dataset):
        return Scenario(
            name="a_scenario",
            display_name="A Scenario",
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

    async def test_scenario_round_trip(
        self,
        repository: SQLAlchemyRepository,
        scenario: Scenario,
        get_scenario_model_validator,
        a_workspace,
    ):
        validator = await get_scenario_model_validator()
        await repository.scenarios.create(a_workspace.id, scenario, validator)
        result = await repository.scenarios.get_by_name(a_workspace.id, scenario.name)

        assert result is not None
        assert result.name == scenario.name
        assert result.models == scenario.models

        for ds in result.datasets:
            ds.pop("id")
        assert result.datasets == scenario.datasets

    async def test_update_scenario(
        self,
        repository: SQLAlchemyRepository,
        scenario: Scenario,
        get_scenario_model_validator,
        a_workspace,
    ):

        validator = await get_scenario_model_validator()
        scenario = await repository.scenarios.create(a_workspace.id, scenario, validator)

        assert scenario is not None
        assert scenario.id is not None

        scenario.name = "new_name"
        scenario.models = list(reversed(scenario.models))
        await repository.scenarios.update(scenario.id, scenario, validator)

        result = await repository.scenarios.get_by_id(scenario.id)

        assert result is not None
        assert result.name == scenario.name
        assert result.models == scenario.models
