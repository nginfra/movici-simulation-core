from movici_data_core.database.backend import SQLAlchemyBackend


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
