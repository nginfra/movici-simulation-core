import pytest


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


def test_conflict_on_create_existing_scenario(create_scenario_through_api):
    create_scenario_through_api()
    result = create_scenario_through_api()
    assert result["type"] == "duplicate_error"


def test_conflict_on_update_exisiting_scenario(
    create_scenario_through_api, create_scenario_json, get_json
):
    create_scenario_through_api(name="new_scenario")
    scenario_id = create_scenario_through_api(name="another_scenario")["id"]

    result = get_json(
        f"/scenarios/{scenario_id}",
        method="put",
        json=create_scenario_json(name="new_scenario"),
        expected_status=409,
    )
    assert result["type"] == "duplicate_error"


def test_conflict_on_duplicate_scenario_model(create_scenario_through_api, default_model_types):
    result = create_scenario_through_api(
        models=[
            {"name": "model", "type": default_model_types[0].name},
            {"name": "model", "type": default_model_types[0].name},
        ]
    )
    assert result == {
        "result": "error",
        "message": "duplicate model name",
        "type": "duplicate_error",
        "resource": "scenario_model",
        "id": None,
        "name": "model",
    }


def test_validation_error_on_too_long_new_models_and_datasets(create_scenario_through_api):
    result = create_scenario_through_api(
        models=[
            {"name": "model", "type": "a" * 51},
        ],
        datasets=[
            {"name": "b" * 51, "type": "b" * 51},
        ],
    )
    locs = [".".join(str(f) for f in e["loc"]) for e in result["detail"]]
    assert "models.0.type" in locs[0]
    assert "models.0.type" in locs[1]  # a second message at this paht for the union type
    assert "datasets.0.name" in locs[2]
    assert "datasets.0.type" in locs[3]
    assert "datasets.0.type" in locs[4]  # a second message at this paht for the union type
