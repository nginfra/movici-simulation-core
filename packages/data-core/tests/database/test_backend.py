import typing as t
from uuid import UUID

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.database.model import DatabaseMode
from movici_data_core.domain_model import Scenario, Workspace
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the db fixture in conftest
    "database_mode, single_scenario_mode, single_workspace_mode",
    [
        (DatabaseMode.SINGLE_SCENARIO, True, True),
        (DatabaseMode.SINGLE_WORKSPACE, False, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, False, False),
    ],
)
async def test_correct_backend(
    backend, database_mode, single_scenario_mode, single_workspace_mode
):
    assert backend.single_scenario_mode == single_scenario_mode
    assert backend.single_workspace_mode == single_workspace_mode


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the db fixture in conftest
    "database_mode, flags",
    [
        (
            DatabaseMode.SINGLE_SCENARIO,
            {
                "STRICT_ATTRIBUTE_TYPES": False,
                "STRICT_DATASET_TYPES": False,
                "STRICT_ENTITY_TYPES": False,
                "STRICT_MODEL_TYPES": False,
            },
        ),
        (
            DatabaseMode.SINGLE_WORKSPACE,
            {
                "STRICT_ATTRIBUTE_TYPES": False,
                "STRICT_DATASET_TYPES": False,
                "STRICT_ENTITY_TYPES": False,
                "STRICT_MODEL_TYPES": False,
            },
        ),
        (
            DatabaseMode.MULTIPLE_WORKSPACES,
            {
                "STRICT_ATTRIBUTE_TYPES": True,
                "STRICT_DATASET_TYPES": True,
                "STRICT_ENTITY_TYPES": True,
                "STRICT_MODEL_TYPES": True,
            },
        ),
    ],
)
async def test_default_flags(backend, database_mode, flags):
    for k, v in flags.items():
        assert getattr(backend.options, k) == v


@pytest.mark.parametrize(
    "database_mode, new_mode, workspace_count, scenario_count, can_change",
    [
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_SCENARIO, 1, 1, True),
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE, 1, 1, True),
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.MULTIPLE_WORKSPACES, 1, 1, True),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_SCENARIO, 1, 1, True),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_WORKSPACE, 1, 1, True),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.MULTIPLE_WORKSPACES, 1, 1, True),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_SCENARIO, 1, 2, False),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_WORKSPACE, 1, 2, True),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.MULTIPLE_WORKSPACES, 1, 2, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_SCENARIO, 1, 1, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_WORKSPACE, 1, 1, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.MULTIPLE_WORKSPACES, 1, 1, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_SCENARIO, 1, 2, False),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_WORKSPACE, 1, 2, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.MULTIPLE_WORKSPACES, 1, 2, True),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_SCENARIO, 2, 1, False),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_WORKSPACE, 2, 1, False),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.MULTIPLE_WORKSPACES, 2, 1, True),
    ],
)
async def test_change_mode(
    backend: SQLAlchemyBackend,
    database_mode,
    new_mode,
    workspace_count,
    scenario_count,
    can_change,
):
    if database_mode == DatabaseMode.MULTIPLE_WORKSPACES:
        for num in range(workspace_count):
            await backend.workspaces.create(Workspace(f"workspace_{num}", f"Workspace {num}"))
    workspace_id: UUID = t.cast(
        UUID, backend.options.default_workspace_id or (await backend.workspaces.list())[0].id
    )

    if database_mode != DatabaseMode.SINGLE_SCENARIO:
        for num in range(scenario_count):
            await backend.for_workspace(workspace_id).scenarios.create(
                Scenario(f"scenario_{num}", f"scenario_{num}", description="", epsg_code=1),
                validator=ModelConfigValidator(),
            )
    if can_change:
        await backend.set_database_mode(new_mode)
        assert backend.options.mode == new_mode
        if new_mode == DatabaseMode.SINGLE_SCENARIO:
            assert backend.single_scenario_mode
            assert backend.scenario_id is not None
        if new_mode in (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE):
            assert backend.single_workspace_mode
            assert backend.workspace_id is not None
        if new_mode == (DatabaseMode.MULTIPLE_WORKSPACES):
            assert not backend.single_workspace_mode
            assert not backend.single_scenario_mode
    else:
        with pytest.raises(InvalidAction):
            await backend.set_database_mode(new_mode)


@pytest.mark.parametrize(
    "database_mode, new_mode",
    [
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_SCENARIO),
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE),
        (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.MULTIPLE_WORKSPACES),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_SCENARIO),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.SINGLE_WORKSPACE),
        (DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.MULTIPLE_WORKSPACES),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_SCENARIO),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.SINGLE_WORKSPACE),
        (DatabaseMode.MULTIPLE_WORKSPACES, DatabaseMode.MULTIPLE_WORKSPACES),
    ],
)
async def test_mode_persists_after_change(db, database_mode, new_mode):
    async with db.get_backend() as backend:
        assert backend.options.mode == database_mode
        await backend.set_database_mode(new_mode)

    async with db.get_backend() as backend:
        assert backend.options.mode == new_mode


class TestSingleScenarioBackend:
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_SCENARIO

    def test_scenario_and_workspace_are_set(self, backend: SQLAlchemyBackend):
        assert backend.workspace_id is not None
        assert backend.scenario_id is not None

    @pytest.mark.parametrize(
        "flag",
        [
            "STRICT_ATTRIBUTE_TYPES",
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


class TestSingleWorkspaceBackend:
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


class TestMultipleWorkspaceBackend:
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
        assert len(await backend.scenarios.list()) == 0
        scenario = await backend.scenarios.create(
            Scenario(
                name="some_scenario",
                display_name="a scenario",
                description="",
                epsg_code=0,
            ),
            validator=model_config_validator,
        )
        assert len(await backend.scenarios.list()) == 1
        await backend.for_scenario(scenario).scenarios.delete()
        assert len(await backend.scenarios.list()) == 0
