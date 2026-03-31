from movici_data_core.domain_model import Workspace


def test_created_workspace_has_id(a_workspace: Workspace):
    assert a_workspace.id is not None


async def test_create_and_delete_workspace_gets_a_uuid(repository):
    workspace = await repository.workspaces.create(
        Workspace(name="some_workspace", display_name="Some Workspace")
    )
    assert workspace.id > 0
