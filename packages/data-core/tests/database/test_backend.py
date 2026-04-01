import pytest
from movici_data_core.database.backend import (
    MultipleWorkspacesBackend,
    SingleScenarioBackend,
    SingleWorkspaceBackend,
    SQLAlchemyBackendFactory,
)
from movici_data_core.database.general import get_options
from movici_data_core.database.model import DatabaseMode


@pytest.mark.parametrize(
    # database_mode fixture is pickecd up in the initialized_db fixture in conftest
    "database_mode, backend_cls",
    [
        (DatabaseMode.SINGLE_SCENARIO, SingleScenarioBackend),
        (DatabaseMode.SINGLE_WORKSPACE, SingleWorkspaceBackend),
        (DatabaseMode.MULTIPLE_WORKSPACES, MultipleWorkspacesBackend),
    ],
)
async def test_correct_backend(database_mode, backend_cls, session_factory, initialized_db):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        assert isinstance(backend, backend_cls)


async def test_can_get_backend_for_workspace(session, a_workspace, initialized_db):
    options = await get_options(session)
    assert options.mode == DatabaseMode.MULTIPLE_WORKSPACES
    backend = MultipleWorkspacesBackend(session, options)
    workspace_backend = backend.for_workspace(a_workspace)
    assert isinstance(workspace_backend, SingleWorkspaceBackend)
