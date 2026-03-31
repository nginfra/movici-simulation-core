from movici_data_core.database.model import DatabaseMode
from movici_data_core.general import get_options, get_version, initialize_database


async def test_initialize_db_sets_default_version(session):
    await initialize_database(session, mode=DatabaseMode.SINGLE_SCENARIO)
    await session.flush()
    assert (await get_version(session)) == "v1"


async def test_initialize_db_for_single_scenario_sets_flags(session):
    await initialize_database(session, mode=DatabaseMode.SINGLE_SCENARIO)
    options = await get_options(session)

    assert options.mode == DatabaseMode.SINGLE_SCENARIO
    assert not options.STRICT_DATASET_TYPES
    assert not options.STRICT_ENTITY_TYPES
    assert not options.STRICT_ATTRIBUTES
    assert not options.STRICT_MODELS
    assert not options.STRICT_MODEL_CONFIGS


async def test_initialize_db_for_single_scenario_creates_default_workspace(session):
    await initialize_database(session, mode=DatabaseMode.SINGLE_SCENARIO)
    options = await get_options(session)

    assert options.default_workspace is not None
    assert options.default_workspace.name == "__default__"
    assert options.default_workspace.display_name == "__default__"


async def test_initialize_db_for_multiple_workspaces_sets_flags(session):
    await initialize_database(session, mode=DatabaseMode.MULTIPLE_WORKSPACES)
    options = await get_options(session)

    assert options.mode == DatabaseMode.MULTIPLE_WORKSPACES
    assert options.STRICT_DATASET_TYPES
    assert options.STRICT_ENTITY_TYPES
    assert options.STRICT_ATTRIBUTES
    assert options.STRICT_MODELS
    assert options.STRICT_MODEL_CONFIGS


async def test_initialize_db_for_multiple_workspaces_does_not_create_default_workspace(session):
    await initialize_database(session, mode=DatabaseMode.MULTIPLE_WORKSPACES)
    options = await get_options(session)

    assert options.default_workspace is None
