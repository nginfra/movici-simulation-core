def test_create_and_get_workspace(get_json):
    result = get_json(
        "/workspaces", method="post", json={"name": "new_project", "display_name": "New Project"}
    )
    workspace_id = result.pop("id")
    assert workspace_id is not None
    assert result == {
        "result": "ok",
        "message": "workspace created",
    }

    workspace = get_json(f"/workspaces/{workspace_id}")
    assert workspace == {
        "name": "new_project",
        "display_name": "New Project",
        "id": workspace_id,
        "dataset_count": 0,
        "scenario_count": 0,
    }
