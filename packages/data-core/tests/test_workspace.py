import dataclasses
import uuid

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import Workspace


def test_created_workspace_has_id(a_workspace: Workspace):
    assert a_workspace.id is not None


async def test_get_workspace_by_id(repository: SQLAlchemyRepository, a_workspace):
    assert a_workspace.id is not None
    found = await repository.workspaces.get_by_id(a_workspace.id)
    assert a_workspace == found


async def test_get_workspace_by_name(repository: SQLAlchemyRepository, a_workspace):
    found = await repository.workspaces.get_by_name(a_workspace.name)
    assert a_workspace == found


async def test_get_non_existing_workspace_by_name(repository: SQLAlchemyRepository):
    assert (await repository.workspaces.get_by_name("invalid")) is None


async def test_get_non_existing_workspace_by_id(repository: SQLAlchemyRepository):
    assert (await repository.workspaces.get_by_id(uuid.uuid4())) is None


async def test_created_workspace_gets_a_uuid(repository):
    workspace = await repository.workspaces.create(
        Workspace(name="some_workspace", display_name="Some Workspace")
    )
    assert int(workspace.id) > 0


async def test_create_and_delete_a_workspace(repository: SQLAlchemyRepository):
    assert len(await repository.workspaces.list()) == 0
    workspace = await repository.workspaces.create(
        Workspace(name="some_workspace", display_name="Some Workspace")
    )
    assert workspace.id is not None
    assert len(await repository.workspaces.list()) == 1

    await repository.workspaces.delete(workspace.id)

    assert len(await repository.workspaces.list()) == 0


async def test_update_workspace(repository: SQLAlchemyRepository, a_workspace: Workspace):
    assert a_workspace.id is not None
    assert a_workspace.display_name != "New Name"

    await repository.workspaces.update(
        a_workspace.id, dataclasses.replace(a_workspace, display_name="New Name")
    )
    updated = await repository.workspaces.get_by_id(a_workspace.id)
    assert updated is not None
    assert updated.display_name == "New Name"
