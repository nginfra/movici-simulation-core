import pytest
from movici_data_core.database.backend import (
    MultipleWorkspacesBackend,
    SingleScenarioBackend,
    SingleWorkspaceBackend,
    SQLAlchemyBackendFactory,
)
from movici_data_core.database.general import get_options
from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import InvalidAction


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the initialized_db fixture in conftest
    "database_mode, backend_cls",
    [
        (DatabaseMode.SINGLE_SCENARIO, SingleScenarioBackend),
        (DatabaseMode.SINGLE_WORKSPACE, SingleWorkspaceBackend),
        (DatabaseMode.MULTIPLE_WORKSPACES, MultipleWorkspacesBackend),
    ],
)
async def test_correct_backend(database_mode, backend_cls, session_factory, initialized_db):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        assert isinstance(backend, backend_cls)


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
                "STRICT_MODELS": False,
                "STRICT_MODEL_CONFIGS": False,
            },
        ),
        (
            DatabaseMode.SINGLE_WORKSPACE,
            {
                "STRICT_ATTRIBUTES": False,
                "STRICT_DATASET_TYPES": False,
                "STRICT_ENTITY_TYPES": False,
                "STRICT_MODELS": False,
                "STRICT_MODEL_CONFIGS": False,
            },
        ),
        (
            DatabaseMode.MULTIPLE_WORKSPACES,
            {
                "STRICT_ATTRIBUTES": True,
                "STRICT_DATASET_TYPES": True,
                "STRICT_ENTITY_TYPES": True,
                "STRICT_MODELS": True,
                "STRICT_MODEL_CONFIGS": True,
            },
        ),
    ],
)
async def test_default_flags(database_mode, flags, session_factory, initialized_db):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        for k, v in flags.items():
            assert getattr(backend.options, k) == v


class TestSetFlags:
    @pytest.fixture
    def database_mode(self):
        return DatabaseMode.SINGLE_SCENARIO

    @pytest.fixture
    async def backend(self, session_factory, initialized_db):
        factory = SQLAlchemyBackendFactory(session_factory)
        async with factory.get_backend() as backend:
            yield backend

    @pytest.mark.parametrize(
        "flag",
        [
            "STRICT_ATTRIBUTES",
            "STRICT_DATASET_TYPES",
            "STRICT_ENTITY_TYPES",
        ],
    )
    async def test_can_set_flag(self, flag: str, backend: SingleScenarioBackend):
        assert not getattr(backend.options, flag)
        backend.set_options(**{flag.lower(): True})
        assert getattr(backend.options, flag)

    async def test_can_set_strict_models_and_config(self, backend: SingleScenarioBackend):
        backend.set_options(strict_model_configs=True, strict_models=True)
        assert backend.options.STRICT_MODELS
        assert backend.options.STRICT_MODEL_CONFIGS

    async def test_unsetting_strict_models_unsets_strict_model_configs(
        self, backend: SingleScenarioBackend
    ):
        backend.set_options(strict_model_configs=True, strict_models=True)
        backend.set_options(strict_models=False)

        assert not backend.options.STRICT_MODELS
        assert not backend.options.STRICT_MODEL_CONFIGS

    async def test_cannot_set_strict_model_configs_when_not_strict_models(
        self, backend: SingleScenarioBackend
    ):
        with pytest.raises(InvalidAction):
            backend.set_options(strict_model_configs=True)


async def test_can_get_backend_for_workspace(session, a_workspace, initialized_db):
    options = await get_options(session)
    assert options.mode == DatabaseMode.MULTIPLE_WORKSPACES
    backend = MultipleWorkspacesBackend(session, options)
    workspace_backend = backend.for_workspace(a_workspace)
    assert isinstance(workspace_backend, SingleWorkspaceBackend)
