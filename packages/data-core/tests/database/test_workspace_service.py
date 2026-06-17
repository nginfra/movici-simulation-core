import uuid

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.exceptions import ResourceDoesNotExist


async def test_ensure_valid_workspace_by_name(a_workspace, backend: SQLAlchemyBackend):
    workspace_name = a_workspace.name
    assert await backend.workspaces.ensure_valid_workspace(workspace_name)


async def test_ensure_valid_workspace_by_id(a_workspace, backend: SQLAlchemyBackend):
    workspace_id_str = str(a_workspace.id)
    assert await backend.workspaces.ensure_valid_workspace(workspace_id_str)


async def test_ensure_invalid_workspace_by_name(backend: SQLAlchemyBackend):
    with pytest.raises(ResourceDoesNotExist):
        await backend.workspaces.ensure_valid_workspace("invalid")


async def test_ensure_invalid_workspace_by_id(backend: SQLAlchemyBackend):
    with pytest.raises(ResourceDoesNotExist):
        await backend.workspaces.ensure_valid_workspace(str(uuid.uuid4()))


async def test_get_workspace_with_counts(
    backend: SQLAlchemyBackend, a_workspace, a_scenario, a_dataset
):
    workspace = await backend.workspaces.get(id=a_workspace.id)
    assert workspace is not None
    assert workspace.scenario_count is None
    assert workspace.dataset_count is None

    workspace = await backend.workspaces.get_with_counts(id=a_workspace.id)
    assert workspace is not None
    assert workspace.scenario_count == 1
    assert workspace.dataset_count == 1
