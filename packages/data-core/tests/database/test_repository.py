import dataclasses
import uuid

import pytest
from movici_data_core.database.repository import (
    SQLAlchemyRepository,
)
from movici_data_core.domain_model import Dataset, DatasetFormat, DatasetType, Workspace
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist


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
        assert len(await repository.dataset_types.list()) == 0
        dataset_type = await repository.dataset_types.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id is not None
        assert len(await repository.dataset_types.list()) == 1

        await repository.dataset_types.delete(dataset_type.id)

        assert len(await repository.dataset_types.list()) == 0

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

    async def test_raises_on_non_existing_dataset_type_when_strict(
        self, repository: SQLAlchemyRepository, a_workspace
    ):
        repository.options.STRICT_DATASET_TYPES = True

        with pytest.raises(ResourceDoesNotExist):
            await repository.datasets.create(
                a_workspace.id,
                Dataset(
                    "some_dataset",
                    "some dataset",
                    dataset_type=DatasetType("new", format=DatasetFormat.ENTITY_BASED),
                ),
            )

    async def test_automatically_creates_dataset_type_when_not_strict(
        self, repository: SQLAlchemyRepository, a_workspace
    ):
        repository.options.STRICT_DATASET_TYPES = False

        dataset = await repository.datasets.create(
            a_workspace.id,
            Dataset(
                "some_dataset",
                "some dataset",
                dataset_type=DatasetType("new", format=DatasetFormat.ENTITY_BASED),
            ),
        )
        assert dataset is not None
        assert dataset.dataset_type.name == "new"
        assert dataset.dataset_type.id is not None
