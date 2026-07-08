import datetime
import pathlib
import uuid

import pytest
from pydantic import ValidationError

from movici_data_core.domain_model import (
    Dataset,
    DatasetFormat,
    DatasetType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
    SimulationInfo,
    Update,
    UpdateModel,
)
from movici_data_core.exceptions import (
    DeserializationError,
    MoviciValidationError,
    UnsupportedFileType,
)
from movici_data_core.file_helpers import tempfile_delete_on_error
from movici_data_core.marshalling import (
    AttributeTypeIn,
    DatasetTypeIn,
    DatasetWithDataIn,
    EntityTypeIn,
    ModelTypeIn,
    ScenarioDatasetIn,
    ScenarioIn,
    ScenarioModelIn,
    ScenarioOut,
    ShortDatasetIn,
    UpdateIn,
    UpdateModelIn,
    WorkspaceIn,
)
from movici_data_core.serialization import dump_dict
from movici_simulation_core import AttributeSchema, AttributeSpec, EntityInitDataFormat
from movici_simulation_core.testing import dataset_data_to_numpy
from movici_simulation_core.types import FileType


@pytest.fixture
def filetype():
    return FileType.JSON


@pytest.fixture
def data_section():
    return {
        "some_entities": {
            "id": [1],
            "attr": [12],
        }
    }


@pytest.fixture
def serializer():
    return EntityInitDataFormat(
        AttributeSchema([AttributeSpec("id", int), AttributeSpec("attr", int)])
    )


@pytest.fixture
def store_dict(tmp_path, filetype):
    default_filetype = filetype

    def _store_dict(update_dict, filetype=None):
        filetype = filetype or default_filetype
        with tempfile_delete_on_error(suffix=filetype.default_extension, dir=tmp_path) as file:
            file.write(dump_dict(update_dict, filetype))
        return pathlib.Path(file.name)

    return _store_dict


class TestDatasetWithDataIn:
    @pytest.fixture
    def dataset_dict(self, data_section):
        return {
            "name": "a_dataset",
            "display_name": "A Dataset",
            "type": {"name": "some_type", "format": "entity_based"},
            "general": {"some": "data"},
            "epsg_code": 1234,
            "data": data_section,
        }

    @pytest.fixture
    def dataset_path(self, dataset_dict, store_dict):
        return store_dict(dataset_dict)

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    def test_read_entity_dataset_from_file(self, filetype, dataset_path, serializer, data_section):
        dataset = DatasetWithDataIn.read_entity_based_dataset_from_file(
            dataset_path, serializer=serializer
        )
        assert dataset == Dataset(
            name="a_dataset",
            display_name="A Dataset",
            dataset_type=DatasetType(name="some_type", format=DatasetFormat.ENTITY_BASED),
            general={"some": "data"},
            epsg_code=1234,
            data=dataset_data_to_numpy(data_section),
        )

    def test_read_entity_dataset_with_type_as_str_from_file(
        self, filetype, dataset_dict, store_dict, serializer, data_section
    ):
        dataset_dict["type"] = "some_type"
        path = store_dict(dataset_dict)
        dataset = DatasetWithDataIn.read_entity_based_dataset_from_file(
            path, serializer=serializer
        )
        assert dataset == Dataset(
            name="a_dataset",
            display_name="A Dataset",
            dataset_type=DatasetType(name="some_type"),
            general={"some": "data"},
            epsg_code=1234,
            data=dataset_data_to_numpy(data_section),
        )

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    def test_read_unstructured_data_from_file(self, filetype, dataset_path, data_section):
        dataset = DatasetWithDataIn.read_unstructured_dataset_from_file(dataset_path)
        assert dataset == Dataset(
            name="a_dataset",
            display_name="A Dataset",
            dataset_type=DatasetType(name="some_type", format=DatasetFormat.ENTITY_BASED),
            general={"some": "data"},
            epsg_code=1234,
            data=data_section,
        )

    @pytest.mark.parametrize("format", [DatasetFormat.ENTITY_BASED, DatasetFormat.UNSTRUCTURED])
    def test_raises_if_invalid_filetype(self, format, tmp_path, serializer):
        path = tmp_path / "dataset.dat"
        path.write_bytes(b"somedata")

        with pytest.raises(UnsupportedFileType):
            if format == DatasetFormat.ENTITY_BASED:
                DatasetWithDataIn.read_entity_based_dataset_from_file(path, serializer)
            else:
                DatasetWithDataIn.read_unstructured_dataset_from_file(path)

    @pytest.mark.parametrize("format", [DatasetFormat.ENTITY_BASED, DatasetFormat.UNSTRUCTURED])
    def test_raises_on_unparsable_data(self, format, tmp_path, serializer):
        path = tmp_path / "dataset.json"
        path.write_bytes(b"somedata")

        with pytest.raises(DeserializationError):
            if format == DatasetFormat.ENTITY_BASED:
                DatasetWithDataIn.read_entity_based_dataset_from_file(path, serializer)
            else:
                DatasetWithDataIn.read_unstructured_dataset_from_file(path)


class TestUpdateIn:
    @pytest.fixture
    def created_at(self):
        return datetime.datetime.now(tz=datetime.timezone.utc)

    @pytest.fixture
    def update_dict(self, data_section, created_at: datetime.datetime):
        return {
            "dataset": {
                "name": "a_dataset",
                "type": {"name": "some_dstype"},
            },
            "model": {"name": "a_model", "type": "some_type"},
            "timestamp": 12,
            "iteration": 6,
            "created_at": created_at.isoformat(),
            "data": data_section,
        }

    @pytest.fixture
    def update_path(self, update_dict, store_dict):
        return store_dict(update_dict)

    @pytest.mark.parametrize("filetype", [FileType.JSON, FileType.MSGPACK])
    def test_read_update_from_file(
        self, filetype, data_section, update_path, serializer, created_at
    ):
        update = UpdateIn.read_from_file(update_path, serializer)
        assert update == Update(
            dataset=ScenarioDataset("a_dataset", dataset_type=DatasetType("some_dstype")),
            timestamp=12,
            iteration=6,
            model=UpdateModel(name="a_model", type=ModelType("some_type")),
            created_at=created_at,
            data=dataset_data_to_numpy(data_section),
        )

    def test_load_data_from_datset_name_as_data_key(self, update_dict, store_dict, serializer):
        data = update_dict.pop("data")
        update_dict[update_dict["dataset"]["name"]] = data
        path = store_dict(update_dict)

        update = UpdateIn.read_from_file(path, serializer)
        assert update.data is not None

    def test_raises_if_invalid_filetype(self, tmp_path, serializer):
        path = tmp_path / "dataset.dat"
        path.write_bytes(b"somedata")

        with pytest.raises(UnsupportedFileType):
            UpdateIn.read_from_file(path, serializer)

    def test_raises_on_unparsable_data(self, tmp_path, serializer):
        path = tmp_path / "dataset.json"
        path.write_bytes(b"somedata")

        with pytest.raises(DeserializationError):
            UpdateIn.read_from_file(path, serializer)

    def test_raises_if_no_data(self, update_dict, store_dict, serializer):
        del update_dict["data"]
        path = store_dict(update_dict)

        with pytest.raises(MoviciValidationError):
            UpdateIn.read_from_file(path, serializer)

    def test_raises_if_update_contains_data_for_multiple_datasets(
        self, update_dict, store_dict, serializer
    ):
        data = update_dict.pop("data")
        update_dict[update_dict["dataset"]["name"]] = data
        update_dict["another"] = data
        path = store_dict(update_dict)

        with pytest.raises(MoviciValidationError):
            UpdateIn.read_from_file(path, serializer)

    def test_raises_if_update_contains_data_for_different_dataset(
        self, update_dict, store_dict, serializer
    ):
        update_dict["another"] = update_dict.pop("data")
        path = store_dict(update_dict)

        with pytest.raises(MoviciValidationError):
            UpdateIn.read_from_file(path, serializer)


class TestScenarioInOut:
    @pytest.fixture
    def scenario_config(self):
        return {
            "name": "a_scenario",
            "display_name": "A scenario",
            "description": "lalala description",
            "epsg_code": 1234,
            "simulation_info": {
                "mode": "time_oriented",
                "start_time": 12,
                "duration": 42,
                "time_scale": 1.5,
                "reference": 9000.1,
            },
            "models": [
                {"name": "model1", "type": "model_a", "dataset": "a_dataset"},
                {"name": "model3", "type": "model_c"},
            ],
            "datasets": [{"name": "dataset_a", "type": "some_type"}],
        }

    def test_validate_scenario_config_in(self, scenario_config):
        assert ScenarioIn.model_validate(scenario_config).to_domain() == Scenario(
            name="a_scenario",
            display_name="A scenario",
            description="lalala description",
            epsg_code=1234,
            simulation_info=SimulationInfo(
                start_time=12, duration=42, time_scale=1.5, reference=9000.1, mode="time_oriented"
            ),
            models=[
                ScenarioModel(
                    "model1", type=ModelType("model_a"), config={"dataset": "a_dataset"}
                ),
                ScenarioModel("model3", type=ModelType("model_c"), config={}),
            ],
            datasets=[ScenarioDataset(name="dataset_a", dataset_type=DatasetType("some_type"))],
        )

    def test_dump_scenario_out(self, scenario_config):
        scenario_id = uuid.uuid4()
        dataset_id = uuid.uuid4()
        dataset_type_id = uuid.uuid4()
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        scenario_config["id"] = scenario_id
        scenario_config["datasets"][0]["id"] = dataset_id
        scenario_config["datasets"][0]["type"] = {
            "name": scenario_config["datasets"][0]["type"],
            "id": dataset_type_id,
            "format": DatasetFormat.ENTITY_BASED,
            "mimetype": None,
        }
        scenario_config["created_at"] = now
        scenario_config["updated_at"] = now
        scenario_config["has_updates"] = False
        scenario_config["status"] = ScenarioStatus.READY
        assert (
            ScenarioOut.from_domain(
                Scenario(
                    name="a_scenario",
                    id=scenario_id,
                    display_name="A scenario",
                    description="lalala description",
                    epsg_code=1234,
                    simulation_info=SimulationInfo(
                        start_time=12,
                        duration=42,
                        time_scale=1.5,
                        reference=9000.1,
                        mode="time_oriented",
                    ),
                    created_at=now,
                    updated_at=now,
                    models=[
                        ScenarioModel(
                            "model1", type=ModelType("model_a"), config={"dataset": "a_dataset"}
                        ),
                        ScenarioModel("model3", type=ModelType("model_c"), config={}),
                    ],
                    datasets=[
                        ScenarioDataset(
                            id=dataset_id,
                            name="dataset_a",
                            dataset_type=DatasetType(
                                "some_type", id=dataset_type_id, format=DatasetFormat.ENTITY_BASED
                            ),
                        )
                    ],
                )
            ).model_dump()
            == scenario_config
        )

    @pytest.mark.parametrize(
        "payload, expected",
        [
            (
                {"name": "a_dataset", "type": "a_type"},
                ScenarioDataset("a_dataset", DatasetType("a_type")),
            ),
            (
                {"name": "a_dataset", "type": {"name": "a_type"}},
                ScenarioDataset("a_dataset", DatasetType("a_type")),
            ),
            (
                {"name": "a_dataset", "type": None},
                ScenarioDataset("a_dataset", None),
            ),
        ],
    )
    def test_scenario_dataset_in(self, payload, expected):
        assert ScenarioDatasetIn.model_validate(payload).to_domain() == expected


@pytest.mark.parametrize(
    "cls, base_payload, error_payload",
    [
        (WorkspaceIn, {"name": "a", "display_name": "a"}, {"name": "A"}),
        (ShortDatasetIn, {"name": "a", "display_name": "a", "type": {"name": "a"}}, {"name": "A"}),
        (DatasetTypeIn, {"name": "a", "format": "binary"}, {"name": "A"}),
        (
            ScenarioIn,
            {
                "name": "a",
                "display_name": "a",
                "simulation_info": {
                    "mode": "time_oriented",
                    "duration": 1,
                    "reference": 0,
                    "time_scale": 1,
                    "start_time": 1,
                },
                "models": [],
                "datasets": [],
            },
            {"name": "A"},
        ),
        (ScenarioDatasetIn, {"name": "a", "type": "a"}, {"name": "A"}),
        (ScenarioDatasetIn, {"name": "a", "type": "a"}, {"type": "A"}),
        (ScenarioModelIn, {"name": "a", "type": "a"}, {"name": "A"}),
        (ScenarioModelIn, {"name": "a", "type": "a"}, {"type": "A"}),
        (UpdateModelIn, {"name": "a", "type": "a"}, {"name": "A"}),
        (UpdateModelIn, {"name": "a", "type": "a"}, {"type": "A"}),
        (EntityTypeIn, {"name": "a"}, {"name": "A"}),
        (
            AttributeTypeIn,
            {
                "name": "a",
                "data_type": {"type": "float", "unit_shape": [], "csr": False},
                "enum_name": "a",
            },
            {"name": "A"},
        ),
        (
            AttributeTypeIn,
            {
                "name": "a",
                "data_type": {"type": "float", "unit_shape": [], "csr": False},
                "enum_name": "a",
            },
            {"enum_name": "A"},
        ),
        (ModelTypeIn, {"name": "a", "jsonschema": {}}, {"name": "A"}),
    ],
)
def test_snake_case(cls, base_payload, error_payload):
    assert isinstance(cls(**base_payload), cls)
    with pytest.raises(ValidationError):
        cls(**{**base_payload, **error_payload})
