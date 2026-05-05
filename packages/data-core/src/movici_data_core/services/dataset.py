import dataclasses
import pathlib
import random
import typing as t
from string import ascii_lowercase
from uuid import UUID

from movici_data_core.api_model import DatasetOut
from movici_data_core.bounding_box import calculate_bounding_box_from_data
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import (
    Dataset,
    DatasetFormat,
    DatasetType,
    Workspace,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    ResourceDoesNotExist,
    UnsupportedFileType,
)
from movici_data_core.serialization import dump_dict, load_dict
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


def random_suffix(length=6):
    return "".join(random.choice(ascii_lowercase) for _ in range(length))  # noqa: S311


class DatasetService:
    def __init__(
        self,
        repository: SQLAlchemyRepository,
        serializer: ExternalSerializationStrategy,
        tmpfile_dir: pathlib.Path,
    ):
        self.repository = repository
        self.serializer = serializer
        if not tmpfile_dir.exists() and tmpfile_dir.is_dir():
            raise OSError(f"{tmpfile_dir} is not a valid directory")
        self.tmpfile_dir = tmpfile_dir

    async def list(self):
        return await self.repository.datasets.list()

    async def get(self, name: str | None = None, id: UUID | None = None) -> Dataset | None:
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

    async def create(self, dataset: Dataset):
        return await self.repository.datasets.create(dataset)

    async def update(self, dataset_id: UUID, dataset: Dataset):
        return await self.repository.datasets.update(dataset_id, dataset)

    async def get_dataset_as_file(self, dataset_id: UUID, filetype: FileType = FileType.JSON):
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            raise ResourceDoesNotExist("dataset", id=dataset_id)
        outfile = (
            self.tmpfile_dir
            / f"{t.cast(Workspace, existing.workspace).name}-{existing.name}-{random_suffix()}"
        ).with_suffix(filetype.default_extension)
        dataset_as_dict = DatasetOut.from_domain(existing).model_dump(mode="json")
        match existing.dataset_type.format:
            case DatasetFormat.ENTITY_BASED:
                if filetype not in self.serializer.supported_file_types():
                    raise UnsupportedFileType(filetype)

                data = await self.repository.dataset_data.get_entity_data(dataset_id)

                raw_data = self.serializer.dumps(
                    {
                        **dataset_as_dict,
                        "data": data,
                    },
                    filetype=filetype,
                )
                outfile.write_bytes(raw_data)

            case DatasetFormat.UNSTRUCTURED:
                data = await self.repository.dataset_data.get_unstructured_data(dataset_id)
                raw_data = dump_dict({**dataset_as_dict, "data": data}, filetype=filetype)
                outfile.write_bytes(raw_data)
            case DatasetFormat.BINARY:
                with open(outfile, "wb") as fp:
                    _, streamer = await self.repository.dataset_data.stream_binary_data(dataset_id)
                    async for chunk in streamer:
                        fp.write(chunk)
            case _:
                raise UnsupportedFileType(filetype)
        return outfile

    async def get_entity_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_entity_data(dataset_id)

    async def get_unstructured_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_unstructured_data(dataset_id)

    async def stream_binary_data(self, dataset_id: UUID):
        return self.repository.dataset_data.stream_binary_data(dataset_id)

    async def update_from_file(
        self, dataset_id: UUID, path: pathlib.Path, mimetype: str | None = None
    ):
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            raise ResourceDoesNotExist("dataset", id=dataset_id)
        dataset_type = existing.dataset_type
        match existing.dataset_type.format:
            case DatasetFormat.ENTITY_BASED:
                return await self._update_entity_based_dataset_from_file(
                    dataset_id, dataset_type, path
                )

            case DatasetFormat.UNSTRUCTURED:
                return await self._update_unstructured_dataset_from_file(
                    dataset_id, dataset_type, path
                )

            case DatasetFormat.BINARY:
                return await self._update_binary_dataset_from_file(
                    existing, path, mimetype=mimetype
                )

        assert False, "should not get here"

    async def _update_entity_based_dataset_from_file(
        self, dataset_id: UUID, dataset_type: DatasetType, path: pathlib.Path
    ):
        file_type = self._ensure_supported_file_type(
            dataset_id, dataset_type, path, self.serializer.supported_file_types()
        )
        dataset_dict = self.serializer.loads(path.read_bytes(), file_type)
        # TODO: use apilevel deserialization (eg pydantic) for deserialization
        if dataset_dict.get("type") != dataset_type.name:
            raise InvalidResource("dataset", id=dataset_id, message="Cannot change dataset type")
        dataset_data = dataset_dict.get("data", {})
        dataset = Dataset(
            name=dataset_dict["name"],
            display_name=dataset_dict.get("display_name", dataset_dict["name"]),
            dataset_type=dataset_type,
            general=dataset_dict.get("general"),
            epsg_code=dataset_dict.get("epsg_code"),
            bounding_box=calculate_bounding_box_from_data(dataset_data),
            data=dataset_data,
        )

        return await self.repository.datasets.update_with_data(
            dataset_id, dataset, DatasetFormat.ENTITY_BASED
        )

    async def _update_unstructured_dataset_from_file(
        self, dataset_id: UUID, dataset_type: DatasetType, path: pathlib.Path
    ):
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
            dataset_id, dataset, DatasetFormat.UNSTRUCTURED
        )

    async def _update_binary_dataset_from_file(
        self, dataset: Dataset, path: pathlib.Path, mimetype: str | None
    ):
        assert dataset.id is not None
        dataset_type = dataset.dataset_type
        if (
            dataset_type.mimetype is not None
            and mimetype is not None
            and dataset.dataset_type.mimetype != mimetype
        ):
            raise InvalidResource(
                "dataset",
                id=dataset.id,
                message=(f'Invalid mimetype. Expected "{dataset_type.mimetype}", got {mimetype}'),
            )

        return await self.repository.datasets.update_with_data(
            dataset.id,
            obj=dataclasses.replace(dataset, data=path),
            format=DatasetFormat.BINARY,
        )

    @staticmethod
    def _ensure_supported_file_type(
        dataset_id: UUID,
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
