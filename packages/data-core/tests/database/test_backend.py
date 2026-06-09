import pathlib
import typing as t
from uuid import UUID

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyServer
from movici_data_core.database.model import DatabaseMode
from movici_data_core.domain_model import BoundingBox, Dataset, Scenario, Workspace
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from movici_data_core.serialization import dump_dict, load_dict
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.types import FileType


@pytest.fixture
async def backend(initialized_db: SQLAlchemyServer):
    async with initialized_db.get_backend() as backend:
        yield backend


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
    backend, database_mode, single_scenario_mode, single_workspace_mode
):
    assert backend.single_scenario_mode == single_scenario_mode
    assert backend.single_workspace_mode == single_workspace_mode


@pytest.mark.parametrize(
    # database_mode fixture is picked up in the initialized_db fixture in conftest
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
    initialized_db,
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
    async def backend(self, backend: SQLAlchemyBackend, a_dataset, create_default_types):
        await create_default_types(backend.repository)
        await backend.update_schema()
        return backend.for_workspace(a_dataset.workspace.id)

    @pytest.fixture
    def dataset_data(self, a_dataset: Dataset):
        return {
            "name": a_dataset.name,
            "type": a_dataset.dataset_type.name,
            "display_name": a_dataset.display_name,
            "epsg_code": 28992,
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
    def dataset_path(self, dataset_data, store_dataset):
        return store_dataset(dataset_data)

    async def test_list_dataset_with_data(
        self,
        backend: SQLAlchemyBackend,
        dataset_data,
        store_dataset,
        a_dataset_type,
        a_dataset,
    ):
        # fill a_dataset with entity_data
        await backend.datasets.update_from_file(a_dataset.id, store_dataset(dataset_data))

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

    async def test_backend_doenst_allow_updating_dataset_type(
        self, a_dataset, store_dataset, dataset_data, backend: SQLAlchemyBackend
    ):
        backend.set_options(strict_dataset_types=False)
        dataset_data["type"] = "new_type"
        path = store_dataset(dataset_data)
        with pytest.raises(InvalidResource):
            await backend.datasets.update_from_file(a_dataset.id, path)

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    async def test_get_entity_data_as_file(
        self,
        a_dataset: Dataset,
        dataset_data,
        dataset_path,
        backend: SQLAlchemyBackend,
        tmp_path: pathlib.Path,
        filetype: FileType,
    ):

        assert a_dataset.id is not None

        await backend.datasets.update_from_file(a_dataset.id, dataset_path)
        file = await backend.datasets.get_dataset_as_file(a_dataset.id, filetype=filetype)

        a_dataset = t.cast(Dataset, await backend.datasets.get(id=a_dataset.id))

        assert a_dataset.id is not None
        assert a_dataset.created_at is not None
        assert a_dataset.updated_at is not None

        assert file.parent == tmp_path
        assert file.suffix == filetype.default_extension
        result = load_dict(file.read_bytes(), filetype=filetype)
        assert result["type"].pop("id", None) is not None
        assert result == {
            **dataset_data,
            "type": {"name": dataset_data["type"], "format": "entity_based", "mimetype": None},
            "id": str(a_dataset.id),
            "created_at": a_dataset.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": a_dataset.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "epsg_code": 28992,
            "has_data": True,
            "bounding_box": [1.0, 2.0, 2.0, 3.0],
        }

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    async def test_get_unstructured_data_as_file(
        self, store_dataset, backend: SQLAlchemyBackend, tmp_path, filetype: FileType
    ):
        dataset_type = await backend.dataset_types.get(name="tabular")
        assert dataset_type is not None

        dataset_id = await backend.datasets.create(
            Dataset("some_dataset", "Some Dataset", dataset_type=dataset_type)
        )
        created = await backend.datasets.get(id=dataset_id)
        assert created is not None
        assert not created.has_data
        assert created.created_at is not None
        assert created.updated_at is not None

        await backend.datasets.update_from_file(
            dataset_id,
            store_dataset(
                {
                    "name": "some_dataset",
                    "display_name": "Some Dataset",
                    "type": "tabular",
                    "data": {"some": "data"},
                },
                filetype=filetype,
            ),
        )

        updated = await backend.datasets.get(id=dataset_id)
        assert updated is not None
        assert updated.has_data
        assert updated.created_at is not None
        assert updated.updated_at is not None

        file = await backend.datasets.get_dataset_as_file(dataset_id, filetype=filetype)
        assert file.parent == tmp_path
        assert file.suffix == filetype.default_extension

        result = load_dict(file.read_bytes(), filetype)
        assert result["type"].pop("id", None) is not None
        assert result == {
            "id": str(updated.id),
            "name": updated.name,
            "display_name": updated.display_name,
            "type": {"name": "tabular", "format": "unstructured", "mimetype": None},
            "has_data": True,
            "epsg_code": None,
            "general": None,
            "bounding_box": None,
            "created_at": updated.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": updated.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": {"some": "data"},
        }

    async def test_get_binary_data_as_file(
        self, store_dataset, backend: SQLAlchemyBackend, tmp_path
    ):
        filetype = FileType.NETCDF
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
            store_dataset(
                b"somedata" * 10,
                name="some_dataset",
                filetype=filetype,
            ),
        )

        file = await backend.datasets.get_dataset_as_file(dataset_id, filetype=filetype)
        assert file.parent == tmp_path
        assert file.suffix == filetype.default_extension

        result = file.read_bytes()
        assert result == b"somedata" * 10


class TestUpdateService:
    @pytest.fixture
    async def backend(
        self,
        backend: SQLAlchemyBackend,
        an_attribute_type,  # Required to prevent warning about attribute data type inference
        create_default_types,
    ):
        await create_default_types(backend.repository)
        await backend.update_schema()
        return backend

    @pytest.fixture
    def update_data(
        self, a_dataset: Dataset, a_scenario: Scenario, an_entity_type, an_attribute_type
    ):
        return {
            "dataset": {
                "name": a_dataset.name,
                "type": {"name": a_dataset.dataset_type.name},
            },
            "timestamp": 0,
            "iteration": 1,
            "model": {
                "name": a_scenario.models[0].name,
                "type": a_scenario.models[0].type.name,
            },
            "data": {
                an_entity_type.name: {
                    "id": [0, 1],
                    an_attribute_type.name: [1.0, 2.0],
                }
            },
        }

    @pytest.fixture
    def store_update(self, tmp_path):
        def _store(update_data, filetype: FileType = FileType.JSON):
            name = update_data["dataset"]["name"]
            timestamp = update_data["timestamp"]
            iteration = update_data["iteration"]
            update_data = dump_dict(update_data, filetype=filetype)
            file_path = (tmp_path / f"t{timestamp}_{iteration}_{name}").with_suffix(
                filetype.default_extension
            )
            file_path.write_bytes(update_data)
            return file_path

        return _store

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    async def test_store_update_from_file(
        self, backend: SQLAlchemyBackend, a_scenario, filetype: FileType, store_update, update_data
    ):
        backend = backend.for_scenario(a_scenario.id)
        assert len(await backend.updates.list()) == 0
        file = store_update(update_data, filetype)

        await backend.updates.store_update_from_file(file, filetype)
        assert len(await backend.updates.list()) == 1

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    async def test_get_update_as_file(
        self,
        a_dataset: Dataset,
        a_scenario: Scenario,
        backend: SQLAlchemyBackend,
        tmp_path: pathlib.Path,
        filetype: FileType,
        store_update,
        update_data,
    ):

        assert a_scenario.id is not None
        assert a_dataset.id is not None

        backend = backend.for_scenario(a_scenario.id)
        update_id = await backend.updates.store_update_from_file(
            store_update(update_data, filetype), filetype
        )

        file = await backend.updates.get_update_as_file(update_id, filetype=filetype)

        assert file.parent == tmp_path
        assert file.suffix == filetype.default_extension
        result = load_dict(file.read_bytes(), filetype=filetype)

        assert result["dataset"].pop("id", None) == str(a_dataset.id)
        assert result.pop("created_at", None) is not None
        result["dataset"]["type"] = {"name": result["dataset"]["type"]["name"]}
        assert result == {
            **update_data,
            "id": str(update_id),
        }

    async def test_creates_bounding_box_for_update(
        self,
        backend: SQLAlchemyBackend,
        a_scenario,
        an_entity_type,
        update_data,
        store_update,
    ):
        backend = backend.for_scenario(a_scenario.id)
        assert len(await backend.updates.list()) == 0

        update_data["data"] = {
            an_entity_type.name: {
                "id": [0, 1],
                "geometry.x": [1.0, 2.0],
                "geometry.y": [3.0, 4.0],
            }
        }

        file = store_update(update_data)
        update_id = await backend.updates.store_update_from_file(file, FileType.JSON)
        result = await backend.repository.updates.get_by_id(t.cast(UUID, update_id))
        assert result is not None
        assert result.bounding_box == BoundingBox(1.0, 3.0, 2.0, 4.0)
