from itertools import count

import pytest


@pytest.fixture
def scenario_id(create_scenario_through_api, a_dataset, default_model_types):
    result = create_scenario_through_api(
        datasets=[{"name": a_dataset.name, "type": a_dataset.dataset_type.name}],
        models=[{"name": "model_a", "type": default_model_types[0].name}],
    )
    return result["id"]


@pytest.fixture
def create_update_through_api(scenario_id, get_json, a_dataset, an_entity_type, an_attribute_type):
    iterations = count()

    def _create_update(**kwargs):
        defaults = {
            "dataset": {"name": a_dataset.name},
            "model": {"name": "model_a"},
            "timestamp": 0,
            "iteration": next(iterations),
            "data": {
                an_entity_type.name: {
                    "id": [1, 2, 3],
                    an_attribute_type.name: [4, 5, 6],
                }
            },
        }

        result = get_json(
            "/updates",
            method="post",
            params={"scenario": str(scenario_id)},
            json={**defaults, **kwargs},
        )
        return result

    return _create_update


def test_create_update(create_update_through_api):
    result = create_update_through_api()
    update_id = result.pop("id")
    assert update_id is not None
    assert result == {
        "result": "ok",
        "message": "update created",
    }


def test_list_updates(get_json, create_update_through_api, scenario_id):
    create_update_through_api()
    create_update_through_api()
    create_update_through_api()

    result = get_json("/updates", params={"scenario": scenario_id})

    assert len({upd["id"] for upd in result["updates"]}) == 3


def test_get_update(
    get_json, create_update_through_api, a_dataset, an_entity_type, an_attribute_type
):
    update_data = {
        an_entity_type.name: {
            "id": [1, 2, 3],
            an_attribute_type.name: [4, 5, 6],
        }
    }
    update_id = create_update_through_api(data=update_data, timestamp=12, iteration=15)["id"]

    update = get_json(f"/updates/{update_id}")

    assert update.pop("created_at") is not None
    assert update.pop("dataset")["name"] == a_dataset.name
    assert update.pop("model")["name"] == "model_a"

    assert update == {
        "id": update_id,
        "timestamp": 12,
        "iteration": 15,
        "data": update_data,
    }


def test_delete_updates(get_json, scenario_id, create_update_through_api):
    create_update_through_api()
    create_update_through_api()
    create_update_through_api()

    def _get_update_count():
        result = get_json("/updates", params={"scenario": scenario_id})
        return len({upd["id"] for upd in result["updates"]})

    assert _get_update_count() == 3

    result = get_json("/updates/", params={"scenario": scenario_id}, method="DELETE")
    assert result == {
        "result": "ok",
        "id": scenario_id,
        "message": "updates deleted",
    }
    assert _get_update_count() == 0
