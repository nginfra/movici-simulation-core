import dataclasses
from uuid import UUID

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyBackendFactory
from movici_data_core.database.model import DatabaseMode
from movici_data_core.domain_model import Dataset, Scenario
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from movici_data_core.serialization import dump_dict
from movici_simulation_core.core import EntityInitDataFormat
from movici_simulation_core.types import FileType


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


@pytest.fixture
async def backend(session_factory, initialized_db):
    factory = SQLAlchemyBackendFactory(session_factory)
    async with factory.get_backend() as backend:
        yield backend


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


class TestDatasetService:
    @pytest.fixture
    async def backend(self, backend: SQLAlchemyBackend, a_dataset):
        schema = await backend.attribute_types.as_schema()
        return dataclasses.replace(
            backend, serializer=EntityInitDataFormat(schema=schema)
        ).for_workspace(a_dataset.workspace.id)

    @pytest.fixture
    def dataset_with_data(self, a_dataset: Dataset):
        return {
            "name": a_dataset.name,
            "type": a_dataset.dataset_type.name,
            "display_name": a_dataset.display_name,
            "general": {"some": "data"},
            "data": {
                "transport_nodes": {
                    "id": [1, 2],
                    "geometry.x": [1.0, 2.0],
                    "geometry.y": [2.0, 3.0],
                }
            },
        }

    @pytest.fixture
    def store_dataset(self, tmp_path):
        def _store(dataset_data, name: str | None = None, filetype: FileType = FileType.JSON):
            if isinstance(dataset_data, dict):
                name = dataset_data["name"]
                dataset_data = dump_dict(dataset_data, filetype=filetype)
            else:
                assert name is not None
            file_path = (tmp_path / name).with_suffix(filetype.default_extension)
            file_path.write_bytes(dataset_data)
            return file_path

        return _store

    @pytest.fixture
    def dataset_path(self, dataset_with_data, store_dataset):
        return store_dataset(dataset_with_data)

    async def test_list_dataset_with_data(
        self,
        backend: SQLAlchemyBackend,
        dataset_with_data,
        store_dataset,
        a_dataset_type,
        a_dataset,
    ):
        # fill a_dataset with entity_data
        await backend.datasets.update_from_file(a_dataset.id, store_dataset(dataset_with_data))

        # create a dataset with raw data
        raw_dataset_type = await backend.dataset_types.get(name="flooding_tape")
        assert raw_dataset_type is not None
        dataset_id = await backend.datasets.create(
            Dataset("dataset_with_raw_data", "Raw Dataset", dataset_type=raw_dataset_type)
        )
        await backend.datasets.update_from_file(
            dataset_id,
            store_dataset(b"some_data", name="dataset_with_raw_data", filetype=FileType.NETCDF),
        )

        # create another dataset with no data
        await backend.datasets.create(
            Dataset("another_dataset", "Another Dataset", dataset_type=a_dataset_type)
        )

        result = await backend.datasets.list()
        has_data = {ds.name: ds.has_data for ds in result}
        assert has_data == {
            a_dataset.name: True,
            "dataset_with_raw_data": True,
            "another_dataset": False,
        }

    async def test_can_update_entity_dataset_from_file(
        self, a_dataset, dataset_path, backend: SQLAlchemyBackend
    ):
        await backend.datasets.update_from_file(a_dataset.id, dataset_path)
        dataset_data = await backend.datasets.get_entity_data(a_dataset.id)
        assert dataset_data.get("transport_nodes") is not None

    async def test_update_raw_dataset_from_file(self, backend: SQLAlchemyBackend, store_dataset):
        dataset_type = await backend.dataset_types.get(name="flooding_tape")
        assert dataset_type is not None

        dataset_id = await backend.datasets.create(
            Dataset("some_dataset", "Some Dataset", dataset_type=dataset_type)
        )
        created = await backend.datasets.get(id=dataset_id)
        assert created is not None
        assert not created.has_data

        await backend.datasets.update_from_file(
            dataset_id,
            store_dataset(b"some_data", name="dataset_with_raw_data", filetype=FileType.NETCDF),
        )

        result = await backend.datasets.get(id=dataset_id)
        assert result is not None
        assert result.has_data

    async def test_update_unstructured_dataset_from_file(
        self, backend: SQLAlchemyBackend, store_dataset
    ):
        dataset_type = await backend.dataset_types.get(name="tabular")
        assert dataset_type is not None

        dataset_id = await backend.datasets.create(
            Dataset("some_dataset", "Some Dataset", dataset_type=dataset_type)
        )
        created = await backend.datasets.get(id=dataset_id)
        assert created is not None
        assert not created.has_data

        await backend.datasets.update_from_file(
            dataset_id,
            store_dataset(
                {"name": "some_dataset", "type": "tabular", "data": {"some": "data"}},
                filetype=FileType.JSON,
            ),
        )

        result = await backend.datasets.get(id=dataset_id)
        assert result is not None
        assert result.has_data

    async def test_sqlalchemy_backend_doenst_allow_updating_dataset_type(
        self, a_dataset, store_dataset, dataset_with_data, backend: SQLAlchemyBackend
    ):
        backend.set_options(strict_dataset_types=False)
        dataset_with_data["type"] = "new_type"
        path = store_dataset(dataset_with_data)
        with pytest.raises(InvalidResource):
            await backend.datasets.update_from_file(a_dataset.id, path)
