import typing as t
from unittest.mock import patch
from uuid import UUID

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from movici_data_core.database import model as db_model
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.database.general import get_options, initialize_database
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
    Update,
    Workspace,
)
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.core import DataType


@pytest.fixture
def dbapi_url():
    return "sqlite+aiosqlite://"


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.fixture
async def database_server(dbapi_url, tmp_path):
    async with SQLAlchemyServer(dbapi_url, tmpfile_dir=tmp_path).begin() as server:
        async with server.engine.begin() as conn:
            await conn.run_sync(db_model.Base.metadata.create_all)
        yield server


@pytest.fixture
async def initialized_db(database_server: SQLAlchemyServer, database_mode):
    async with database_server.get_session() as session:
        await initialize_database(session, mode=database_mode)
        yield database_server


@pytest.fixture
async def session(initialized_db: SQLAlchemyServer):
    async with initialized_db.get_session() as session:
        yield session


@pytest.fixture
def default_dataset_types():
    return [
        DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED),
        DatasetType(
            name="flooding_tape", format=DatasetFormat.BINARY, mimetype="application/x-netcdf"
        ),
        DatasetType(name="tabular", format=DatasetFormat.UNSTRUCTURED),
    ]


@pytest.fixture
def default_entity_types():
    return [
        EntityType("roads"),
        EntityType("transport_nodes"),
        EntityType("virtual_nodes"),
        EntityType("virtual_links"),
    ]


@pytest.fixture
def default_attribute_types():
    return [
        AttributeType("id", DataType(int), description="Entity ID"),
        AttributeType("geometry.x", DataType(float), unit="m"),
        AttributeType("geometry.y", DataType(float), unit="m"),
        AttributeType("geometry.linestring_2d", DataType(float, unit_shape=(2,), csr=True)),
        AttributeType("topology.from_node_id", DataType(float)),
        AttributeType("topology.to_node_id", DataType(float)),
        AttributeType("transport.capacity", DataType(float)),
        AttributeType("labels", DataType(int, (), True), enum_name="label"),
    ]


@pytest.fixture
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
def create_default_types(
    default_dataset_types, default_entity_types, default_attribute_types, default_model_types
):
    created = False

    async def _create(repository: SQLAlchemyRepository):
        nonlocal created
        if created:
            return
        for dataset_type in default_dataset_types:
            await repository.dataset_types.create(dataset_type)
        for entity_type in default_entity_types:
            await repository.entity_types.create(entity_type)
        for attribute_type in default_attribute_types:
            await repository.attribute_types.create(attribute_type)
        for model_type in default_model_types:
            await repository.model_types.create(model_type)
        created = True

    return _create


@pytest.fixture
async def repository(session, create_default_types, a_workspace):
    with patch.object(RawDataProcessor, "RAW_DATA_CHUNK_SIZE", 10):
        options = await get_options(session)
        repository = SQLAlchemyRepository(session, options)
        await create_default_types(repository)
        yield repository.for_workspace(a_workspace.id)


@pytest.fixture
async def get_model_config_validator(repository: SQLAlchemyRepository, a_workspace: Workspace):
    async def _get_validator_for_workspace(workspace_id: UUID | None = None):
        workspace_id = workspace_id or a_workspace.id
        assert workspace_id is not None
        return ModelConfigValidator.from_list_data(
            attribute_types=await repository.attribute_types.list(),
            entity_types=await repository.entity_types.list(),
        )

    return _get_validator_for_workspace


@pytest.fixture
async def model_config_validator(get_model_config_validator):
    return await get_model_config_validator()


@pytest.fixture
def create_scenario(repository: SQLAlchemyRepository, a_workspace, get_model_config_validator):
    async def _create_scenario(scenario: Scenario, workspace_id=None):
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
    async def _create_update(timestamp, iteration, ids, array, scenario_id=None):
        scenario_id = scenario_id or a_scenario.id
        update = Update(
            dataset=ScenarioDataset(a_dataset.name, a_dataset.dataset_type.name),
            timestamp=timestamp,
            iteration=iteration,
            model_name=a_scenario.models[0]["name"],
            model_type=a_scenario.models[0]["type"],
            data={
                an_entity_type.name: {
                    "id": {"data": np.asarray(ids)},
                    an_attribute_type.name: {"data": np.asarray(array)},
                }
            },
        )

        return await repository.for_scenario(scenario_id).updates.create(update)

    return _create_update


@pytest.fixture
async def a_workspace(session: AsyncSession):
    workspace = db_model.Workspace(name="default", display_name="Default Workspace")
    session.add(workspace)
    await session.flush()
    return workspace.to_domain()


@pytest.fixture
async def a_dataset_type(repository: SQLAlchemyRepository):
    return await repository.dataset_types.get_by_name("transport_network")


@pytest.fixture
async def an_entity_type(repository: SQLAlchemyRepository):
    return await repository.entity_types.get_by_name("roads")


@pytest.fixture
async def an_attribute_type(repository: SQLAlchemyRepository) -> AttributeType:
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
async def a_csr_attribute_type(repository: SQLAlchemyRepository) -> AttributeType:
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
async def a_dataset(repository: SQLAlchemyRepository, a_dataset_type):
    dataset_id = await repository.datasets.create(
        Dataset(
            name="a_transport_network",
            display_name="A Transport Network",
            dataset_type=a_dataset_type,
        ),
    )

    return t.cast(Dataset, await repository.datasets.get_by_id(dataset_id))


@pytest.fixture
async def a_scenario(
    default_model_types, a_dataset, repository: SQLAlchemyRepository, create_scenario
):
    scenario = Scenario(
        name="a_scenario",
        display_name="A Scenario",
        description="Scenario for testing",
        epsg_code=28992,
        simulation_info={"some": "info"},
        datasets=[
            {
                "name": a_dataset.name,
                "type": a_dataset.dataset_type.name,
            }
        ],
        models=[
            {
                "name": "model1",
                "type": default_model_types[0].name,
                "dataset": a_dataset.name,
                "entity_group": "transport_nodes",
                "attribute": "id",
            },
            {
                "name": "model2",
                "type": default_model_types[1].name,
                "field": "value",
            },
        ],
    )
    scenario_id = await create_scenario(scenario)
    return t.cast(Scenario, await repository.scenarios.for_id(scenario_id).get_by_id())
