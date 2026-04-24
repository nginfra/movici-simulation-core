import dataclasses
import pathlib
import typing as t

from movici_data_core.domain_model import (
    Dataset,
    DatasetFormat,
    DatasetType,
)
from movici_data_core.exceptions import InvalidAction, InvalidResource, ResourceDoesNotExist
from movici_data_core.serialization import load_dict
from movici_data_core.types import MoviciDataRepository, T_id
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


class DatasetService(t.Generic[T_id]):
    def __init__(
        self, repository: MoviciDataRepository, serializer: ExternalSerializationStrategy
    ):
        self.repository = repository
        self.serializer = serializer

    async def list(self):
        return await self.repository.datasets.list()

    async def get(self, name: str | None = None, id: T_id | None = None) -> Dataset | None:
        if name is not None:
            result = await self.repository.datasets.get_by_name(name)
        elif id is not None:
            result = await self.repository.datasets.get_by_id(id)
        else:
            raise InvalidAction("Dataset name or id is required")

        if result is not None:
            assert result.id is not None
            result.has_data = await self.repository.dataset_data.exists_for(result.id)
        return result

    async def get_entity_data(self, dataset_id: T_id):
        return await self.repository.dataset_data.get_entity_data(dataset_id)

    async def get_unstructured_data(self, dataset_id: T_id):
        return await self.repository.dataset_data.get_unstructured_data(dataset_id)

    async def stream_binary_data(self, dataset_id: T_id):
        return self.repository.dataset_data.stream_binary_data(dataset_id)

    async def create(self, dataset: Dataset):
        return await self.repository.datasets.create(dataset)

    async def update_from_file(
        self, dataset_id: T_id, path: pathlib.Path, mimetype: str | None = None
    ):
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            raise ResourceDoesNotExist("dataset", id=dataset_id)
        dataset_type = existing.dataset_type
        if dataset_type.format == DatasetFormat.ENTITY_BASED:
            file_type = self._ensure_supported_file_type(
                dataset_id, dataset_type, path, self.serializer.supported_file_types()
            )
            dataset_dict = self.serializer.loads(path.read_bytes(), file_type)
            # TODO: use apilevel deserialization (eg pydantic) for deserialization
            if dataset_dict.get("type") != dataset_type.name:
                raise InvalidResource(
                    "dataset", id=dataset_id, message="Cannot change dataset type"
                )

            dataset = Dataset(
                name=dataset_dict["name"],
                display_name=dataset_dict.get("display_name", dataset_dict["name"]),
                dataset_type=dataset_type,
                general=dataset_dict.get("general"),
                epsg_code=dataset_dict.get("epsg_code"),
                data=dataset_dict.get("data", {}),
            )

            return await self.repository.datasets.update_with_data(
                dataset_id, dataset, dataset_type.format
            )
        elif dataset_type.format == DatasetFormat.UNSTRUCTURED:
            file_type = self._ensure_supported_file_type(
                dataset_id, dataset_type, path, (FileType.JSON, FileType.MSGPACK)
            )

            dataset_dict = load_dict(path.read_bytes(), file_type)

            # TODO: use apilevel deserialization (eg pydantic) for deserialization
            if dataset_dict["type"] != dataset_type.name:
                raise InvalidResource(
                    "dataset",
                    id=dataset_id,
                    message="Cannot change dataset type for unstructured dataset",
                )
            dataset = Dataset(
                name=dataset_dict["name"],
                display_name=dataset_dict.get("display_name", dataset_dict["name"]),
                dataset_type=dataset_type,
                general=dataset_dict.get("general"),
                epsg_code=dataset_dict.get("epsg_code"),
                data=dataset_dict.get("data", {}),
            )

            return await self.repository.datasets.update_with_data(
                dataset_id, dataset, dataset_type.format
            )

        elif dataset_type.format == DatasetFormat.BINARY:
            if (
                dataset_type.mimetype is not None
                and mimetype is not None
                and dataset_type.mimetype != mimetype
            ):
                raise InvalidResource(
                    "dataset",
                    id=dataset_id,
                    message=(
                        f'Invalid mimetype. Expected "{dataset_type.mimetype}", got {mimetype}'
                    ),
                )

            return await self.repository.datasets.update_with_data(
                dataset_id,
                obj=dataclasses.replace(existing, data=path),
                format=dataset_type.format,
            )

        else:
            assert False, "should not get here"

    @staticmethod
    def _ensure_supported_file_type(
        dataset_id: T_id,
        dataset_type: DatasetType,
        path: pathlib.Path,
        supported_file_types: t.Container[FileType],
    ):
        file_type = FileType.from_extension(path.suffix)
        if file_type not in supported_file_types:
            raise InvalidResource(
                "dataset",
                id=dataset_id,
                message=f"Unsupported file type '{path.suffix}' for"
                f" dataset with type {dataset_type.name}",
            )
        return file_type
