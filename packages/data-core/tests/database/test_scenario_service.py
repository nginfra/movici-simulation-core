from movici_data_core.database.backend import SQLAlchemyBackend


async def test_get_scenario_by_name(backend: SQLAlchemyBackend, a_workspace, a_scenario):
    backend = backend.for_workspace(a_workspace.id)
    scenario = await backend.scenarios.get(name=a_scenario.name)
    assert scenario is not None
    assert scenario.id == a_scenario.id


async def test_get_scenario_by_id(backend: SQLAlchemyBackend, a_workspace, a_scenario):
    backend = backend.for_workspace(a_workspace.id)
    scenario = await backend.scenarios.get(id=a_scenario.id)
    assert scenario is not None
    assert scenario.name == a_scenario.name


async def test_get_active_scenario(backend: SQLAlchemyBackend, a_scenario):
    backend = backend.for_scenario(a_scenario.id)
    scenario = await backend.scenarios.get()
    assert scenario is not None
    assert scenario.name == a_scenario.name
