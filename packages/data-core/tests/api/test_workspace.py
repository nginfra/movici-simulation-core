import pytest


@pytest.fixture
def workspace_created_result(get_json):
    return get_json(
        "/workspaces", method="post", json={"name": "new_project", "display_name": "New Project"}
    )


@pytest.fixture
def workspace_id(workspace_created_result):
    return workspace_created_result["id"]


def test_create_workspace(workspace_created_result):
    workspace_id = workspace_created_result.pop("id")
    assert workspace_id is not None
    assert workspace_created_result == {
        "result": "ok",
        "message": "workspace created",
    }


def test_get_workspace(get_json, workspace_id):
    workspace = get_json(f"/workspaces/{workspace_id}")
    assert workspace == {
        "name": "new_project",
        "display_name": "New Project",
        "id": workspace_id,
        "dataset_count": 0,
        "scenario_count": 0,
    }


def test_update_workspace(get_json, workspace_id):
    result = get_json(
        f"/workspaces/{workspace_id}",
        method="PUT",
        json={"name": "new_project", "display_name": "Updated Name"},
    )
    assert result == {
        "result": "ok",
        "id": workspace_id,
        "message": "workspace updated",
    }
    workspace = get_json(f"/workspaces/{workspace_id}")
    assert workspace == {
        "name": "new_project",
        "display_name": "Updated Name",
        "id": workspace_id,
        "dataset_count": 0,
        "scenario_count": 0,
    }


def test_delete_workspace(get_json, workspace_id):
    result = get_json(
        f"/workspaces/{workspace_id}",
        method="DELETE",
    )
    assert result == {
        "result": "ok",
        "id": workspace_id,
        "message": "workspace deleted",
    }

    result = get_json(f"/workspaces/{workspace_id}", expected_status=404)
    assert result == {
        "result": "error",
        "type": "not_found",
        "resource": "workspace",
        "message": "Resource not found",
        "id": workspace_id,
        "name": None,
    }


def test_conflict_on_create_existing_workspace(get_json):
    payload = {"name": "new_project", "display_name": "New Project"}
    get_json("/workspaces", method="post", json=payload)
    result = get_json("/workspaces", method="post", json=payload, expected_status=409)
    assert result["type"] == "duplicate_error"


def test_conflict_on_update_exisiting_workspace(get_json):
    payload = {"name": "new_project", "display_name": "New Project"}
    get_json("/workspaces", method="post", json=payload)
    workspace_id = get_json(
        "/workspaces", method="post", json={"name": "another", "display_name": "Another"}
    )["id"]
    result = get_json(
        f"/workspaces/{workspace_id}", method="PUT", json=payload, expected_status=409
    )
    assert result["type"] == "duplicate_error"
