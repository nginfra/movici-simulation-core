import pathlib
import typing as t
from uuid import UUID

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.domain_model import BoundingBox, Dataset, Scenario
from movici_data_core.serialization import dump_dict, load_dict
from movici_simulation_core.types import FileType


class TestUpdateService:
    @pytest.fixture
    async def backend(self, backend: SQLAlchemyBackend, an_attribute_type):
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
