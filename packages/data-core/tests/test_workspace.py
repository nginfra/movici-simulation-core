from movici_data_core.model import Workspace


def test_created_workspace_has_id(default_workspace: Workspace):
    assert default_workspace.id is not None
