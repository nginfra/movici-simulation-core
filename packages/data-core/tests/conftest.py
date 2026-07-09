import contextlib
import dataclasses
import shutil
import typing as t
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from movici_data_core.database import model as db_model
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.database.general import _default_flags, get_options, initialize_database
from movici_data_core.database.model import DatabaseMode
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.database.repository.common import RawDataProcessor
from movici_data_core.domain_model import (
    AttributeType,
    Dataset,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    SimulationInfo,
    Update,
    UpdateModel,
    Workspace,
)
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.core import DataType
from movici_simulation_core.testing import dataset_data_to_numpy

DBAPI_URL = "sqlite+aiosqlite://"


@pytest.fixture(scope="session")
def session_dbs_path(tmp_path_factory):
    return tmp_path_factory.mktemp("session_dbs")


@pytest.fixture(scope="session")
async def base_db_session(session_dbs_path):
    """a session scoped database that acts as the 'master' for all other database files. It has
    the database schema created but is otherwise completely empty. It returns the path for
    the sqlite db file
    """

    db_path = session_dbs_path / "base.db"

    dbapi_url = f"sqlite+aiosqlite:///{db_path}"

    async with SQLAlchemyServer(dbapi_url, tmpfile_dir=None).begin() as server:
        async with server.engine.begin() as conn:
            await conn.run_sync(db_model.Base.metadata.create_all)
            await conn.commit()
    return db_path


@pytest.fixture(scope="session")
async def initialized_db_session(base_db_session, session_dbs_path):
    """a session scoped fixture to a sqlite database path that is initialized for the
    MULTIPLE_WORKSPACES database mode.
    """
    new_path = session_dbs_path / "initialized_db.db"
    shutil.copy(base_db_session, new_path)

    dbapi_url = f"sqlite+aiosqlite:///{new_path}"
    async with SQLAlchemyServer(dbapi_url, tmpfile_dir=None).begin() as server:
        async with server.get_session() as session:
            await initialize_database(session, mode=DatabaseMode.MULTIPLE_WORKSPACES)
            await session.commit()
    return new_path


@pytest.fixture(scope="session")
async def default_db_session(
    initialized_db_session,
    session_dbs_path,
    default_dataset_types,
    default_entity_types,
    default_attribute_types,
    default_model_types,
):
    """a session scoped fixture to a sqlite database path that is initialized for the
    MULTIPLE_WORKSPACES database mode and has default types inserted. This is also the default
    db for most test cases
    """
    new_path = session_dbs_path / "default_db.db"
    shutil.copy(initialized_db_session, new_path)

    dbapi_url = f"sqlite+aiosqlite:///{new_path}"
    async with (
        SQLAlchemyServer(dbapi_url, tmpfile_dir=None).begin() as server,
        server.get_session() as session,
    ):
        options = await get_options(session)
        repository = SQLAlchemyRepository(session, options)

        for dataset_type in default_dataset_types:
            await repository.dataset_types.create(dataset_type)
        for entity_type in default_entity_types:
            await repository.entity_types.create(entity_type)
        for attribute_type in default_attribute_types:
            await repository.attribute_types.create(attribute_type)
        for model_type in default_model_types:
            await repository.model_types.create(model_type)
        await session.commit()
    return new_path


@pytest.fixture
def begin_server_from_session_db(tmp_path):
    db_path = tmp_path / "movici.db"

    @contextlib.asynccontextmanager
    async def _copy_and_begin(session_db_path):
        shutil.copy(session_db_path, db_path)
        dbapi_url = f"sqlite+aiosqlite:///{db_path}"
        async with SQLAlchemyServer(dbapi_url, tmp_path).begin() as server:
            yield server

    return _copy_and_begin


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.fixture
def set_database_mode(database_mode):
    async def _set_mode(db: SQLAlchemyServer):
        async with db.get_backend() as backend:
            await backend.set_database_mode(new_mode=database_mode)
            backend.set_options(**{k.lower(): v for k, v in _default_flags(database_mode).items()})

    return _set_mode


@pytest.fixture
async def base_db(begin_server_from_session_db, base_db_session):
    async with begin_server_from_session_db(base_db_session) as server:
        yield server


@pytest.fixture
async def initialized_db(begin_server_from_session_db, initialized_db_session, set_database_mode):
    async with begin_server_from_session_db(initialized_db_session) as server:
        await set_database_mode(server)
        yield server


@pytest.fixture
async def default_db(begin_server_from_session_db, default_db_session, set_database_mode):
    async with begin_server_from_session_db(default_db_session) as server:
        await set_database_mode(server)
        yield server


@pytest.fixture
def db(default_db):
    """An alias for the default_db fixture"""
    return default_db


@pytest.fixture
async def session(db: SQLAlchemyServer):
    async with db.get_session() as session:
        yield session


@pytest.fixture
async def default_backend(db: SQLAlchemyServer, session: AsyncSession):
    return await db.get_backend_for_session(session)


@pytest.fixture
async def backend(default_backend):
    """an alias for the default_backend fixture"""
    return default_backend


@pytest.fixture
async def get_repository(db: SQLAlchemyServer, a_workspace):
    @contextlib.asynccontextmanager
    async def _with_repository():
        async with db.get_session() as session:
            repository = await SQLAlchemyRepository.for_session(session)
            yield repository.for_workspace(a_workspace.id)
            await session.commit()

    return _with_repository


@pytest.fixture
async def repository(session: AsyncSession, a_workspace):
    with patch.object(RawDataProcessor, "RAW_DATA_CHUNK_SIZE", 10):
        repository = await SQLAlchemyRepository.for_session(session)
        yield repository.for_workspace(a_workspace.id)


@pytest.fixture(scope="session")
def default_dataset_types():
    return [
        DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED),
        DatasetType(
            name="flooding_tape", format=DatasetFormat.BINARY, mimetype="application/x-netcdf"
        ),
        DatasetType(name="tabular", format=DatasetFormat.UNSTRUCTURED),
    ]


@pytest.fixture(scope="session")
def default_entity_types():
    return [
        EntityType("roads"),
        EntityType("transport_nodes"),
        EntityType("virtual_nodes"),
        EntityType("virtual_links"),
    ]


@pytest.fixture(scope="session")
def default_attribute_types():
    return [
        AttributeType("id", DataType(int), description="Entity ID"),
        AttributeType("geometry.x", DataType(float), unit="m"),
        AttributeType("geometry.y", DataType(float), unit="m"),
        AttributeType("geometry.linestring_2d", DataType(float, unit_shape=(2,), csr=True)),
        AttributeType("topology.from_node_id", DataType(int)),
        AttributeType("topology.to_node_id", DataType(int)),
        AttributeType("transport.capacity", DataType(float)),
        AttributeType("labels", DataType(int, (), True), enum_name="label"),
    ]


@pytest.fixture(scope="session")
def default_model_types():
    return [
        ModelType(
            "model_a",
            jsonschema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "movici.type": "dataset"},
                    "entity_group": {"type": "string", "movici.type": "entityGroup"},
                    "attribute": {"type": "string", "movici.type": "attribute"},
                },
            },
        ),
        ModelType(
            "model_b",
            jsonschema={
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {"field": {"type": "string"}},
            },
        ),
    ]


@pytest.fixture
async def get_model_config_validator(get_repository, a_workspace: Workspace):
    async def _get_validator_for_workspace(workspace_id: UUID | None = None):
        workspace_id = workspace_id or a_workspace.id
        assert workspace_id is not None
        async with get_repository() as repository:
            return ModelConfigValidator.from_list_data(
                attribute_types=await repository.attribute_types.list(),
                entity_types=await repository.entity_types.list(),
            )

    return _get_validator_for_workspace


@pytest.fixture
async def model_config_validator(get_model_config_validator):
    return await get_model_config_validator()


@pytest.fixture
def create_scenario(get_repository, a_workspace, get_model_config_validator):
    async def _create_scenario(scenario: Scenario, workspace_id=None):
        async with get_repository() as repository:
            workspace_id = workspace_id or a_workspace.id
            return await repository.for_workspace(workspace_id).scenarios.create(
                scenario, await get_model_config_validator()
            )

    return _create_scenario


@pytest.fixture
async def create_update(
    repository: SQLAlchemyRepository,
    a_scenario,
    a_dataset,
    an_attribute_type,
    an_entity_type,
):
    async def _create_update(
        timestamp, iteration, ids=None, array=None, data=None, dataset=None, scenario_id=None
    ):
        scenario_id = scenario_id or a_scenario.id
        if data is None:
            if ids is None or array is None:
                raise ValueError("supply either ids and array or data")
            data = {
                an_entity_type.name: {
                    "id": ids,
                    an_attribute_type.name: array,
                }
            }
        dataset = dataset or a_dataset
        update = Update(
            dataset=ScenarioDataset(dataset.name, dataset.dataset_type),
            timestamp=timestamp,
            iteration=iteration,
            model=UpdateModel(name=a_scenario.models[0].name, type=a_scenario.models[0].type),
            data=dataset_data_to_numpy(data),
        )

        return await repository.for_scenario(scenario_id).updates.create(update)

    return _create_update


@pytest.fixture
async def a_workspace(db: SQLAlchemyServer):
    async with db.get_session() as session:
        repository = await SQLAlchemyRepository.for_session(session)
        options = await get_options(session)
        if options.default_workspace is not None:
            return options.default_workspace.to_domain()

        workspace = Workspace(name="default", display_name="Default Workspace")
        workspace_id = await repository.workspaces.create(workspace)
        await session.commit()
        return dataclasses.replace(workspace, id=workspace_id)


@pytest.fixture
async def a_dataset_type(get_repository):
    async with get_repository() as repository:
        return await repository.dataset_types.get_by_name("transport_network")


@pytest.fixture
async def an_entity_type(get_repository):
    async with get_repository() as repository:
        return await repository.entity_types.get_by_name("roads")


@pytest.fixture
async def an_attribute_type(get_repository) -> AttributeType:
    async with get_repository() as repository:
        attribute_id = await repository.attribute_types.create(
            AttributeType(
                name="some.attribute",
                data_type=DataType(float),
                unit="m/s",
                description="a description",
            )
        )
        return t.cast(AttributeType, await repository.attribute_types.get_by_id(attribute_id))


@pytest.fixture
async def a_csr_attribute_type(get_repository) -> AttributeType:
    async with get_repository() as repository:
        attribute_id = await repository.attribute_types.create(
            AttributeType(
                name="csr.attribute",
                data_type=DataType(float, csr=True),
                unit="m/s",
                description="a description",
            )
        )
        return t.cast(AttributeType, await repository.attribute_types.get_by_id(attribute_id))


@pytest.fixture
async def a_dataset(get_repository, a_dataset_type):
    async with get_repository() as repository:
        dataset_id = await repository.datasets.create(
            Dataset(
                name="a_transport_network",
                display_name="A Transport Network",
                dataset_type=a_dataset_type,
            ),
        )

        return t.cast(Dataset, await repository.datasets.get_by_id(dataset_id))


@pytest.fixture
async def a_dataset_with_data(get_repository, a_dataset, an_entity_type, an_attribute_type):
    dataset_data = dataset_data_to_numpy(
        {an_entity_type.name: {"id": [1, 2, 3], an_attribute_type.name: [10.0, 20.0, 30.0]}}
    )
    async with get_repository() as repository:
        await repository.dataset_data.create(
            a_dataset.id, dataset_data, format=DatasetFormat.ENTITY_BASED
        )

    return dataclasses.replace(a_dataset, has_data=True, data=dataset_data)


@pytest.fixture
async def a_scenario(default_model_types, a_dataset, get_repository, create_scenario):
    async with get_repository() as repository:
        if repository.scenario_id is not None:
            return await repository.scenarios.get()

        scenario = Scenario(
            name="a_scenario",
            display_name="A Scenario",
            description="Scenario for testing",
            epsg_code=28992,
            simulation_info=SimulationInfo.default(),
            datasets=[ScenarioDataset.from_dataset(a_dataset)],
            models=[
                ScenarioModel(
                    name="model1",
                    type=default_model_types[0],
                    config={
                        "dataset": a_dataset.name,
                        "entity_group": "transport_nodes",
                        "attribute": "id",
                    },
                ),
                ScenarioModel(
                    name="model2",
                    type=default_model_types[1],
                    config={
                        "field": "value",
                    },
                ),
            ],
        )
        scenario_id = await create_scenario(scenario)
        return t.cast(Scenario, await repository.scenarios.for_id(scenario_id).get())
