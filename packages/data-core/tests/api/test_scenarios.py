import pytest


@pytest.fixture
def create_scenario_through_api(get_json, a_workspace):
    def _create_scenario(**kwargs):
        defaults = {
            "name": "new_scenario",
            "display_name": "New Scenario",
            "simulation_info": {
                "mode": "time_oriented",
                "reference": 1,
                "start_time": 0,
                "duration": 12,
                "time_scale": 1.4,
            },
            "models": [],
            "datasets": [],
        }
        return get_json(
            "/scenarios",
            params={"workspace": a_workspace.id},
            method="post",
            json={**defaults, **kwargs},
        )

    return _create_scenario


@pytest.fixture
def scenario_id(create_scenario_through_api):
    result = create_scenario_through_api()
    return result["id"]


def test_create_scenario(create_scenario_through_api):
    result = create_scenario_through_api()
    scenario_id = result.pop("id")
    assert scenario_id is not None
    assert result == {
        "result": "ok",
        "message": "scenario created",
    }


def test_list_scenarios(get_json, a_scenario, scenario_id):
    result = get_json("/scenarios", params={"workspace": a_scenario.workspace.id})
    scenario_ids = {scenario["id"] for scenario in result["scenarios"]}
    assert scenario_ids == {str(a_scenario.id), scenario_id}


def test_get_scenario(get_json, scenario_id):
    scenario = get_json(f"/scenarios/{scenario_id}")
    assert scenario.pop("created_at") is not None
    assert scenario.pop("updated_at") is not None
    assert scenario == {
        "id": scenario_id,
        "name": "new_scenario",
        "display_name": "New Scenario",
        "description": "",
        "epsg_code": None,
        "status": "ready",
        "simulation_info": {
            "mode": "time_oriented",
            "reference": 1,
            "start_time": 0,
            "duration": 12,
            "time_scale": 1.4,
        },
        "models": [],
        "datasets": [],
        "has_updates": False,
    }


def test_update_scenario(get_json, scenario_id):
    result = get_json(
        f"/scenarios/{scenario_id}",
        method="PUT",
        json={
            "id": scenario_id,
            "name": "new_name",
            "display_name": "New Name",
            "description": "",
            "simulation_info": {
                "mode": "time_oriented",
                "reference": 1,
                "start_time": 0,
                "duration": 12,
                "time_scale": 1.4,
            },
            "models": [],
            "datasets": [],
        },
    )
    assert result == {
        "result": "ok",
        "id": scenario_id,
        "message": "scenario updated",
    }
    scenario = get_json(f"/scenarios/{scenario_id}")
    assert scenario["name"] == "new_name"
    assert scenario["display_name"] == "New Name"


def test_delete_scenario(get_json, scenario_id):
    result = get_json(
        f"/scenarios/{scenario_id}",
        method="DELETE",
    )
    assert result == {
        "result": "ok",
        "id": scenario_id,
        "message": "scenario deleted",
    }

    result = get_json(f"/scenarios/{scenario_id}", expected_status=404)
    assert result == {
        "result": "error",
        "type": "not_found",
        "resource": "scenario",
        "message": "Resource not found",
        "id": scenario_id,
        "name": None,
    }
