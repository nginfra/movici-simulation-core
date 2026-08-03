import pathlib
import typing as t

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.domain_model import Dataset, DatasetFormat
from movici_data_core.exceptions import InvalidResource
from movici_data_core.serialization import dump_dict, load_dict
from movici_simulation_core.testing import dataset_data_to_numpy
from movici_simulation_core.types import FileType


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

    async def test_get_entity_data(self, a_dataset, dataset_data, backend: SQLAlchemyBackend):
        await backend.repository.dataset_data.create(
            a_dataset.id,
            dataset_data_to_numpy(dataset_data["data"]),
            format=DatasetFormat.ENTITY_BASED,
        )

        result = await backend.datasets.get_entity_data(a_dataset.id)
        assert result.keys() == {"transport_nodes"}

    async def test_get_unstructured_data(self, a_dataset, backend: SQLAlchemyBackend):
        await backend.repository.dataset_data.create(
            a_dataset.id,
            {"some": "data"},
            format=DatasetFormat.UNSTRUCTURED,
        )

        result = await backend.datasets.get_unstructured_data(a_dataset.id)
        assert result == {"some": "data"}

    async def test_get_binary_data(self, a_dataset, backend: SQLAlchemyBackend):
        await backend.repository.dataset_data.create(
            a_dataset.id, b"somebinarydata", format=DatasetFormat.BINARY
        )

        result = await backend.datasets.get_binary_data(a_dataset.id)
        assert result == b"somebinarydata"

    async def test_stream_binary_data(self, a_dataset, backend: SQLAlchemyBackend):
        await backend.repository.dataset_data.create(
            a_dataset.id, b"somebinarydata", format=DatasetFormat.UNSTRUCTURED, chunk_size=2
        )

        result = b""
        async for chunk in await backend.datasets.stream_binary_data(a_dataset.id):
            result += chunk

        assert result == b"somebinarydata"

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
