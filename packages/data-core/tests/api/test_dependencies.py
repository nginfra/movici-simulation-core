from uuid import UUID

import pytest

from movici_data_core.api.dependencies import get_scenario_backend
from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist

A_SCENARIO_NAME = "<default_scenario_name>"
A_SCENARIO_ID = "<default_scenario_id>"
A_WORKSPACE_NAME = "<default_workspace_name>"
A_WORKSPACE_ID = "<default_workspace_id>"


@pytest.mark.parametrize(
    "database_mode, scenario_q, workspace_q",
    [
        (DatabaseMode.SINGLE_SCENARIO, A_SCENARIO_NAME, "whatever"),
        (DatabaseMode.SINGLE_SCENARIO, A_SCENARIO_ID, "whatever"),
        (DatabaseMode.SINGLE_SCENARIO, A_SCENARIO_ID, None),
        (DatabaseMode.SINGLE_SCENARIO, "whatever", "whatever"),
        (DatabaseMode.SINGLE_SCENARIO, None, None),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_NAME, A_WORKSPACE_NAME),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_ID, A_WORKSPACE_NAME),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_NAME, A_WORKSPACE_ID),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_ID, A_WORKSPACE_ID),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_ID, None),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_ID, "whatever"),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_NAME, None),
        (DatabaseMode.SINGLE_WORKSPACE, A_SCENARIO_NAME, "whatever"),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_NAME, A_WORKSPACE_NAME),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_ID, A_WORKSPACE_NAME),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_NAME, A_WORKSPACE_ID),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_ID, A_WORKSPACE_ID),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_ID, None),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_ID, "whatever"),
    ],
)
async def test_get_scenario_backend(
    database_mode,
    scenario_q,
    workspace_q,
    a_workspace,
    a_scenario,
    backend,
):
    if scenario_q == A_SCENARIO_NAME:
        scenario_q = a_scenario.name
    if scenario_q == A_SCENARIO_ID:
        scenario_q = str(a_scenario.id)
    if workspace_q == A_WORKSPACE_NAME:
        workspace_q = a_workspace.name
    if workspace_q == A_WORKSPACE_ID:
        workspace_q = str(a_workspace.id)

    backend = await get_scenario_backend(backend, scenario_q, workspace_q)
    assert backend.scenario_id == a_scenario.id


@pytest.mark.parametrize(
    "database_mode, scenario_q, workspace_q, error",
    [
        (DatabaseMode.MULTIPLE_WORKSPACES, None, None, InvalidAction),
        (DatabaseMode.SINGLE_WORKSPACE, None, A_WORKSPACE_NAME, InvalidAction),
        (DatabaseMode.MULTIPLE_WORKSPACES, None, A_WORKSPACE_ID, InvalidAction),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_NAME, None, InvalidAction),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_NAME, "asdf", ResourceDoesNotExist),
        (DatabaseMode.MULTIPLE_WORKSPACES, "asdf", A_WORKSPACE_NAME, ResourceDoesNotExist),
        (DatabaseMode.MULTIPLE_WORKSPACES, UUID(int=0), A_WORKSPACE_ID, ResourceDoesNotExist),
        (DatabaseMode.MULTIPLE_WORKSPACES, A_SCENARIO_NAME, UUID(int=0), ResourceDoesNotExist),
    ],
)
async def test_raises_when_cannot_get_scenario_backend(
    database_mode, scenario_q, workspace_q, error, a_workspace, a_scenario, backend
):
    if scenario_q == A_SCENARIO_NAME:
        scenario_q = a_scenario.name
    if scenario_q == A_SCENARIO_ID:
        scenario_q = a_scenario.id
    if workspace_q == A_WORKSPACE_NAME:
        workspace_q = a_workspace.name
    if workspace_q == A_WORKSPACE_ID:
        workspace_q = a_workspace.id

    with pytest.raises(error):
        await get_scenario_backend(
            backend,
            str(scenario_q) if scenario_q is not None else None,
            str(workspace_q) if workspace_q is not None else None,
        )
