import uuid

import pytest

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.services.common import ensure_valid_workspace


async def test_ensure_valid_workspace_by_name(a_workspace, repository: SQLAlchemyRepository):
    workspace_name = a_workspace.name
    assert await ensure_valid_workspace(workspace_name, repository)


async def test_ensure_valid_workspace_by_id(a_workspace, repository: SQLAlchemyRepository):
    workspace_id_str = str(a_workspace.id)
    assert await ensure_valid_workspace(workspace_id_str, repository)


async def test_ensure_invalid_workspace_by_name(repository: SQLAlchemyRepository):
    with pytest.raises(ResourceDoesNotExist):
        await ensure_valid_workspace("invalid", repository)


async def test_ensure_invalid_workspace_by_id(repository: SQLAlchemyRepository):
    with pytest.raises(ResourceDoesNotExist):
        await ensure_valid_workspace(str(uuid.uuid4()), repository)
