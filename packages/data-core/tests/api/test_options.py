import pytest


def test_get_options(get_json):
    assert get_json("/options") == {
        "mode": "multiple_workspaces",
        "strict_dataset_types": True,
        "strict_attribute_types": True,
        "strict_entity_types": True,
        "strict_model_types": True,
        "strict_scenario_datasets": True,
        "immutable_workspace_names": False,
    }


def test_update_options(get_json):
    result = get_json("/options", method="PATCH", json={"mode": "single_scenario"})
    assert result == {"result": "ok", "message": "options updated"}


def test_get_and_update_database_mode(get_json):
    current_options = get_json("/options")
    assert current_options["mode"] != "single_scenario"
    get_json("/options", method="PATCH", json={"mode": "single_scenario"})

    result = get_json("/options")
    assert result == {**current_options, "mode": "single_scenario"}


@pytest.mark.parametrize(
    "option, value",
    [
        ("strict_dataset_types", False),
        ("strict_attribute_types", False),
        ("strict_entity_types", False),
        ("strict_model_types", False),
        ("strict_scenario_datasets", False),
        ("immutable_workspace_names", True),
    ],
)
def test_get_and_update_options(get_json, option, value):
    current_options = get_json("/options")
    assert current_options[option] != value
    get_json("/options", method="PATCH", json={option: value})

    result = get_json("/options")
    assert result == {**current_options, option: value}
