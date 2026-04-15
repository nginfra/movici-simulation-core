import typing as t
from uuid import UUID

import pytest
from movici_data_core.database import model as db_model
from movici_data_core.database.general import get_engine, get_options, initialize_database
from movici_data_core.database.model import Base, DatabaseMode
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import (
    AttributeType,
    Dataset,
    DatasetFormat,
    DatasetType,
    EntityType,
    ModelType,
    Scenario,
    Workspace,
)
from movici_data_core.validators import ModelConfigValidator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from movici_simulation_core.core import DataType


@pytest.fixture
async def db():
    async with get_engine("sqlite+aiosqlite://", echo=True) as engine:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.fixture
def session_factory(db):
    return async_sessionmaker(db)


@pytest.fixture
async def initialized_db(session_factory, database_mode):
    async with session_factory() as session:
        await initialize_database(session, mode=database_mode)
        await session.commit()


@pytest.fixture
async def session(session_factory, initialized_db):
    async with session_factory() as session:
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
        AttributeType("geometry.x", DataType(float)),
        AttributeType("geometry.y", DataType(float)),
        AttributeType("geometry.linestring_2d", DataType(float, unit_shape=(2,), csr=True)),
        AttributeType("topology.from_node_id", DataType(float)),
        AttributeType("topology.to_node_id", DataType(float)),
        AttributeType("transport.capacity", DataType(float)),
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
async def repository(
    session,
    default_dataset_types,
    default_entity_types,
    default_attribute_types,
    default_model_types,
    a_workspace,
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
    return repository.for_workspace(a_workspace.id)


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
