import pytest

from movici_data_core.database.model import DatabaseMode


class TestSingleScenarioMode:
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_SCENARIO

    def test_get_scenario_without_specifying_workspace(self, get_json):
        result = get_json("/scenarios/")
        assert {scenario["name"] for scenario in result["scenarios"]} == {"default_scenario"}

    def test_cannot_create_scenario(self, get_json):
        result = get_json("/scenarios/", method="post", json={}, expected_status=400)
        assert result == {
            "result": "error",
            "type": "invalid_action",
            "message": "create scenario is not allowed in this mode",
        }

    def test_cannot_get_workspaces(self, get_json):
        result = get_json("/workspaces/", expected_status=400)
        assert result["type"] == "invalid_action"
        assert "not allowed in this mode" in result["message"]


class TestSingleWorkspaceMode:
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_WORKSPACE

    def test_can_get_scenarios_without_specifying_workspace(self, get_json, a_scenario):
        result = get_json("/scenarios/")
        assert {scenario["name"] for scenario in result["scenarios"]} == {a_scenario.name}

    def test_can_create_scenario(self, get_json, create_scenario_json):
        result = get_json(
            "/scenarios/", method="post", json=create_scenario_json(), expected_status=200
        )
        assert result["id"] is not None

    def test_cannot_get_workspaces(self, get_json):
        result = get_json("/workspaces/", expected_status=400)
        assert result["type"] == "invalid_action"
        assert "not allowed in this mode" in result["message"]


class TestMultipleWorkspaceMode:
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.MULTIPLE_WORKSPACES

    def test_cannot_get_scenarios_without_specifying_workspace(self, get_json, a_scenario):
        result = get_json("/scenarios/", expected_status=400)

        assert result == {
            "result": "error",
            "type": "invalid_action",
            "message": "supply a workspace name or id",
        }
