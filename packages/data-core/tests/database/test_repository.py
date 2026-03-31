import dataclasses
import uuid

import pytest
from movici_data_core.database.repository import (
    DatasetTypeRepository,
    SQLAlchemyRepository,
    WorkspaceRepository,
)
from movici_data_core.domain_model import DatasetFormat, DatasetType, Workspace
from movici_data_core.exceptions import InvalidAction


class TestWorkspaceRepository:
    @pytest.fixture
    def repository(self, repository: SQLAlchemyRepository):
        return repository.workspaces

    async def test_get_workspace_by_id(self, repository: WorkspaceRepository, a_workspace):
        assert a_workspace.id is not None
        found = await repository.get_by_id(a_workspace.id)
        assert a_workspace == found

    async def test_get_workspace_by_name(self, repository: WorkspaceRepository, a_workspace):
        found = await repository.get_by_name(a_workspace.name)
        assert a_workspace == found

    async def test_get_non_existing_workspace_by_name(self, repository: WorkspaceRepository):
        assert (await repository.get_by_name("invalid")) is None

    async def test_get_non_existing_workspace_by_id(self, repository: WorkspaceRepository):
        assert (await repository.get_by_id(uuid.uuid4())) is None

    async def test_created_workspace_gets_a_uuid(self, repository):
        workspace = await repository.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert int(workspace.id) > 0

    async def test_create_and_delete_a_workspace(self, repository: WorkspaceRepository):
        assert len(await repository.list()) == 0
        workspace = await repository.create(
            Workspace(name="some_workspace", display_name="Some Workspace")
        )
        assert workspace.id is not None
        assert len(await repository.list()) == 1

        await repository.delete(workspace.id)

        assert len(await repository.list()) == 0

    async def test_update_workspace(self, repository: WorkspaceRepository, a_workspace: Workspace):
        assert a_workspace.id is not None
        assert a_workspace.display_name != "New Name"

        await repository.update(
            a_workspace.id, dataclasses.replace(a_workspace, display_name="New Name")
        )
        updated = await repository.get_by_id(a_workspace.id)
        assert updated is not None
        assert updated.display_name == "New Name"


class TestDatasetTypeRepository:
    @pytest.fixture
    def repository(self, repository: SQLAlchemyRepository):
        return repository.dataset_types

    async def test_create_and_delete_a_dataset_type(self, repository: DatasetTypeRepository):
        assert len(await repository.list()) == 0
        dataset_type = await repository.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id is not None
        assert len(await repository.list()) == 1

        await repository.delete(dataset_type.id)

        assert len(await repository.list()) == 0

    async def test_update_dataset_type(self, repository: DatasetTypeRepository):
        dataset_type = await repository.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id is not None

        await repository.update(
            dataset_type.id, dataclasses.replace(dataset_type, name="new_name")
        )
        updated = await repository.get_by_id(dataset_type.id)
        assert updated is not None
        assert updated.name == "new_name"

    async def test_cannot_change_format(self, repository: DatasetTypeRepository):
        dataset_type = await repository.create(
            DatasetType(name="a_dataset_type", format=DatasetFormat.ENTITY_BASED)
        )
        assert dataset_type.id

        dataset_type.format = DatasetFormat.UNSTRUCTURED
        with pytest.raises(InvalidAction):
            await repository.update(
                dataset_type.id, dataclasses.replace(dataset_type, name="new_name")
            )


class TestDatasetRepository:
    @pytest.fixture
    def repository(self, repository: SQLAlchemyRepository):
        return repository.datasets
