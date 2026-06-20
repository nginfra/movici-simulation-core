import tempfile
import typing as t
from uuid import UUID

import orjson
import pytest
from fastapi.testclient import TestClient

from movici_data_core.serialization import dump_dict
from movici_simulation_core.types import FileType


@pytest.fixture
def create_dataset(get_json, a_dataset_type, a_workspace):
    def _create_dataset(name="new_dataset", display_name="New Dataset", type=a_dataset_type.name):
        return get_json(
            "/datasets",
            params={"workspace": a_workspace.id},
            method="post",
            json={
                "name": name,
                "display_name": display_name,
                "type": type,
            },
        )

    return _create_dataset


@pytest.fixture
def dataset_data(a_dataset, an_entity_type, an_attribute_type):
    data = {an_entity_type.name: {"id": [1, 2, 3], an_attribute_type.name: [4, 5, 6]}}

    return {
        "name": a_dataset.name,
        "display_name": a_dataset.display_name,
        "type": a_dataset.dataset_type.name,
        "epsg_code": 1234,
        "general": {"some": "data"},
        "data": data,
    }


@pytest.fixture
def dataset_with_data(a_dataset, dataset_data, upload_dataset_data):
    response = upload_dataset_data(
        a_dataset.id, orjson.dumps(dataset_data), mimetype="application/json"
    )
    assert response.status_code == 200
    return response.json()["id"]


@pytest.fixture
def upload_dataset_data(client):
    def _upload_dataset_data(
        dataset_id: UUID | str, data: bytes, filename="somefile", mimetype: str | None = None
    ):
        with tempfile.TemporaryFile("w+b") as file:
            file.write(data)
            file.seek(0)
            return client.post(
                f"/datasets/{dataset_id}/data",
                files={"data": ("somefile", file, mimetype)},
            )

    return _upload_dataset_data


@pytest.fixture
def dataset_id(create_dataset):
    result = create_dataset()
    return result["id"]


def test_create_dataset(create_dataset):
    result = create_dataset()
    dataset_id = result.pop("id")
    assert dataset_id is not None
    assert result == {
        "result": "ok",
        "message": "dataset created",
    }


def test_list_datasets(get_json, a_dataset, dataset_id):
    result = get_json("/datasets", params={"workspace": a_dataset.workspace.id})
    dataset_ids = {ds["id"] for ds in result["datasets"]}
    assert dataset_ids == {str(a_dataset.id), dataset_id}


def test_get_dataset(get_json, dataset_id, a_dataset_type):
    dataset = get_json(f"/datasets/{dataset_id}")
    assert dataset.pop("created_at") is not None
    assert dataset.pop("updated_at") is not None
    assert dataset == {
        "id": dataset_id,
        "name": "new_dataset",
        "display_name": "New Dataset",
        "type": {
            "name": a_dataset_type.name,
            "format": "entity_based",
            "mimetype": None,
            "id": str(a_dataset_type.id),
        },
        "has_data": False,
    }


def test_update_dataset(get_json, dataset_id, a_dataset_type):
    result = get_json(
        f"/datasets/{dataset_id}",
        method="PUT",
        json={
            "id": dataset_id,
            "name": "new_name",
            "display_name": "New Name",
            "type": a_dataset_type.name,
        },
    )
    assert result == {
        "result": "ok",
        "id": dataset_id,
        "message": "dataset updated",
    }
    dataset = get_json(f"/datasets/{dataset_id}")
    assert dataset["name"] == "new_name"
    assert dataset["display_name"] == "New Name"


def test_delete_dataset(get_json, dataset_id):
    result = get_json(
        f"/datasets/{dataset_id}",
        method="DELETE",
    )
    assert result == {
        "result": "ok",
        "id": dataset_id,
        "message": "dataset deleted",
    }

    result = get_json(f"/datasets/{dataset_id}", expected_status=404)
    assert result == {
        "result": "error",
        "type": "not_found",
        "resource": "dataset",
        "message": "Resource not found",
        "id": dataset_id,
        "name": None,
    }


def test_get_create_and_get_entity_dataset_data(
    a_dataset, get_json, upload_dataset_data, dataset_data
):
    response = upload_dataset_data(
        a_dataset.id, orjson.dumps(dataset_data), mimetype="application/json"
    )
    assert response.json() == {
        "result": "ok",
        "id": str(a_dataset.id),
        "message": "dataset data created",
    }

    result = get_json(f"/datasets/{a_dataset.id}/data")
    assert result["data"] == dataset_data["data"]
    assert result["general"] == {"some": "data"}
    assert result["epsg_code"] == 1234


@pytest.mark.parametrize(
    "filetype, mimetype",
    [(FileType.JSON, "application/json"), (FileType.MSGPACK, "application/x-msgpack")],
)
def test_get_create_and_get_unstructured_dataset(
    filetype, mimetype, create_dataset, get_json, upload_dataset_data
):
    dataset: dict[str, t.Any] = {
        "name": "unstructured_dataset",
        "display_name": "Unstructured",
        "type": "tabular",
    }
    dataset_id = create_dataset(**dataset)["id"]

    data = {"some": "data"}
    dataset["data"] = data
    response = upload_dataset_data(dataset_id, dump_dict(dataset, filetype), mimetype=mimetype)

    assert response.status_code == 200, response.json()

    result = get_json(f"/datasets/{dataset_id}/data")

    assert result["data"] == data


def test_get_create_and_get_binary_data(create_dataset, client: TestClient, upload_dataset_data):
    dataset: dict[str, t.Any] = {
        "name": "binary_dataset",
        "display_name": "Binary Dataset",
        "type": "flooding_tape",
    }
    dataset_id = create_dataset(**dataset)["id"]

    data = b"somerawdata"
    response = upload_dataset_data(dataset_id, data, mimetype="application/x-netcdf")

    assert response.status_code == 200, response.json()

    result = client.get(f"/datasets/{dataset_id}/data")

    assert result.content == data


def test_delete_dataset_data_doesnt_delete_dataset(dataset_with_data, get_json, a_dataset):
    dataset_id = dataset_with_data
    result = get_json(f"/datasets/{dataset_id}/data", method="delete")
    assert result["message"] == "dataset data deleted"

    dataset = get_json(f"/datasets/{dataset_id}")
    assert dataset["id"] == dataset_id
    assert not dataset["has_data"]
