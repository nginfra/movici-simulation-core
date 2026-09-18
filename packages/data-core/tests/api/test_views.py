import pytest

from movici_data_core.database.model import DatabaseMode


@pytest.fixture(params=[DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE])
def database_mode(request):
    return request.param


@pytest.fixture
def get_json(get_json, a_scenario, database_mode):
    params = (
        {"scenario": str(a_scenario.id)} if database_mode != DatabaseMode.SINGLE_SCENARIO else {}
    )

    def _get_json(*args, **kwargs):
        return get_json(*args, params=params, **kwargs)

    return _get_json


@pytest.fixture
def view_created_result(get_json):
    return get_json(
        "/views",
        method="post",
        json={"name": "new_view", "config": {"a": "config"}},
    )


@pytest.fixture
def view_id(view_created_result):
    return view_created_result["id"]


def test_create_view(view_created_result):
    view_id = view_created_result.pop("id")
    assert view_id is not None
    assert view_created_result == {
        "result": "ok",
        "message": "view created",
    }


def test_get_view(get_json, view_id):
    view = get_json(f"/views/{view_id}")
    assert view == {
        "name": "new_view",
        "id": view_id,
        "config": {"a": "config"},
    }


def test_update_view(get_json, view_id):
    result = get_json(
        f"/views/{view_id}",
        method="PUT",
        json={"name": "updated_view", "config": {"new": "config"}},
    )
    assert result == {
        "result": "ok",
        "id": view_id,
        "message": "view updated",
    }
    view = get_json(f"/views/{view_id}")
    assert view == {
        "name": "updated_view",
        "id": view_id,
        "config": {"new": "config"},
    }


def test_delete_view(get_json, view_id):
    result = get_json(
        f"/views/{view_id}",
        method="DELETE",
    )
    assert result == {
        "result": "ok",
        "id": view_id,
        "message": "view deleted",
    }

    result = get_json(f"/views/{view_id}", expected_status=404)
    assert result == {
        "result": "error",
        "type": "not_found",
        "resource": "view",
        "message": "Resource not found",
        "id": view_id,
        "name": None,
    }
