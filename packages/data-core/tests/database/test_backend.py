from uuid import UUID

import pytest
from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyBackendFactory
from movici_data_core.database.model import DatabaseMode
from movici_data_core.domain_model import Scenario
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the initialized_db fixture in conftest
    "database_mode, single_scenario_mode, single_workspace_mode",
    [
        (DatabaseMode.SINGLE_SCENARIO, True, True),
        (DatabaseMode.SINGLE_WORKSPACE, False, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, False, False),
    ],
)
async def test_correct_backend(
    database_mode, single_scenario_mode, single_workspace_mode, session_factory, initialized_db
):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        assert backend.single_scenario_mode == single_scenario_mode
        assert backend.single_workspace_mode == single_workspace_mode


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the initialized_db fixture in conftest
    "database_mode, flags",
    [
        (
            DatabaseMode.SINGLE_SCENARIO,
            {
                "STRICT_ATTRIBUTES": False,
                "STRICT_DATASET_TYPES": False,
                "STRICT_ENTITY_TYPES": False,
                "STRICT_MODEL_TYPES": False,
            },
        ),
        (
            DatabaseMode.SINGLE_WORKSPACE,
            {
                "STRICT_ATTRIBUTES": False,
                "STRICT_DATASET_TYPES": False,
                "STRICT_ENTITY_TYPES": False,
                "STRICT_MODEL_TYPES": False,
            },
        ),
        (
            DatabaseMode.MULTIPLE_WORKSPACES,
            {
                "STRICT_ATTRIBUTES": True,
                "STRICT_DATASET_TYPES": True,
                "STRICT_ENTITY_TYPES": True,
                "STRICT_MODEL_TYPES": True,
            },
        ),
    ],
)
async def test_default_flags(database_mode, flags, session_factory, initialized_db):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        for k, v in flags.items():
            assert getattr(backend.options, k) == v


class _TestBackend:
    @pytest.fixture
    async def backend(self, session_factory, initialized_db):
        factory = SQLAlchemyBackendFactory(session_factory)
        async with factory.get_backend() as backend:
            yield backend


class TestSingleScenarioBackend(_TestBackend):
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_SCENARIO

    def test_scenario_and_workspace_are_set(self, backend: SQLAlchemyBackend):
        assert backend.workspace_id is not None
        assert backend.scenario_id is not None

    @pytest.mark.parametrize(
        "flag",
        [
            "STRICT_ATTRIBUTES",
            "STRICT_DATASET_TYPES",
            "STRICT_ENTITY_TYPES",
            "STRICT_MODEL_TYPES",
        ],
    )
    async def test_can_set_flag(self, flag: str, backend: SQLAlchemyBackend):
        assert not getattr(backend.options, flag)
        backend.set_options(**{flag.lower(): True})
        assert getattr(backend.options, flag)

    async def test_cannot_list_workspaces(self, backend: SQLAlchemyBackend):
        with pytest.raises(InvalidAction):
            await backend.workspaces.list()

    async def test_cannot_delete_scenario(self, backend: SQLAlchemyBackend):
        with pytest.raises(InvalidAction):
            await backend.scenarios.delete()


class TestSingleWorkspaceBackend(_TestBackend):
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_WORKSPACE

    def test_workspace_is_set_but_scenario_is_unset(self, backend: SQLAlchemyBackend):
        assert backend.workspace_id is not None
        assert backend.scenario_id is None

    async def test_cannot_list_workspaces(self, backend: SQLAlchemyBackend):
        with pytest.raises(InvalidAction):
            await backend.workspaces.list()

    async def test_can_create_and_delete_scenario(
        self, backend: SQLAlchemyBackend, model_config_validator
    ):
        scenario = await backend.scenarios.create(
            Scenario(
                name="a_scenario",
                display_name="a scenario",
                description="",
                epsg_code=0,
            ),
            validator=model_config_validator,
        )
        assert len(await backend.scenarios.list()) == 1
        await backend.for_scenario(scenario).scenarios.delete()
        assert len(await backend.scenarios.list()) == 0

    async def test_scenario_must_exist_to_delete(self, backend: SQLAlchemyBackend):
        with pytest.raises(ResourceDoesNotExist):
            await backend.for_scenario(UUID(int=0)).scenarios.delete()


class TestMultipleWorkspaceBackend(_TestBackend):
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.MULTIPLE_WORKSPACES

    def test_scenario_and_workspace_are_unset(self, backend: SQLAlchemyBackend):
        assert backend.workspace_id is None
        assert backend.scenario_id is None

    def test_can_set_workspace_id_in_repository(self, backend: SQLAlchemyBackend):
        workspace_id = UUID(int=24)
        assert backend.for_workspace(workspace_id).repository.workspace_id == workspace_id

    def test_can_set_scenario_id_in_repository(self, backend: SQLAlchemyBackend):
        scenario_id = UUID(int=24)
        assert backend.for_scenario(scenario_id).repository.scenario_id == scenario_id

    async def test_can_list_workspaces(self, backend: SQLAlchemyBackend):
        assert isinstance(await backend.workspaces.list(), list)

    async def test_can_create_and_delete_scenario(
        self, backend: SQLAlchemyBackend, model_config_validator, a_workspace
    ):
        backend = backend.for_workspace(a_workspace.id)
        scenario = await backend.scenarios.create(
            Scenario(
                name="a_scenario",
                display_name="a scenario",
                description="",
                epsg_code=0,
            ),
            validator=model_config_validator,
        )
        assert len(await backend.scenarios.list()) == 1
        await backend.for_scenario(scenario).scenarios.delete()
        assert len(await backend.scenarios.list()) == 0
