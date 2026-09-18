import dataclasses
import pathlib
import typing as t
from uuid import UUID

from movici_data_core.bounding_box import calculate_bounding_box_from_data
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import (
    Dataset,
    DatasetFilter,
    DatasetFormat,
    DatasetType,
)
from movici_data_core.exceptions import (
    InvalidAction,
    InvalidResource,
    ResourceDoesNotExist,
    UnsupportedFileType,
)
from movici_data_core.file_helpers import tempfile_delete_on_error
from movici_data_core.marshalling import DatasetPatchIn, DatasetWithDataIn, DatasetWithDataOut
from movici_data_core.serialization import dump_dict
from movici_data_core.state_aggregator import DatasetStateAggregator
from movici_simulation_core.core.data_format import NON_DATA_DICT_KEYS
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


class DatasetService:
    def __init__(
        self,
        repository: SQLAlchemyRepository,
        serializer: ExternalSerializationStrategy,
        tmpfile_dir: pathlib.Path,
    ):
        self.repository = repository
        self.serializer = serializer
        if not tmpfile_dir.is_dir():
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

    async def delete(self, dataset_id: UUID):
        return await self.repository.datasets.delete(dataset_id)

    async def get_dataset_as_file(
        self,
        dataset_id: UUID,
        filetype: FileType = FileType.JSON,
        dataset_filter: DatasetFilter | None = None,
    ) -> pathlib.Path | None:
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            return None

        with tempfile_delete_on_error(
            suffix=filetype.default_extension,
            prefix=f"dataset-{existing.id}-{existing.name}-",
            dir=self.tmpfile_dir,
        ) as outfile:
            match existing.dataset_type.format:
                case DatasetFormat.ENTITY_BASED:
                    if filetype not in self.serializer.supported_file_types():
                        raise UnsupportedFileType(filetype)

                    data = await self.repository.dataset_data.get_entity_data(
                        dataset_id, dataset_filter=dataset_filter
                    )

                    # prevent pydantic from processing the data section
                    raw_data = DatasetWithDataOut.from_domain(
                        dataclasses.replace(existing, data={})
                    ).model_dump(mode="json")
                    raw_data["data"] = data
                    outfile.write(
                        self.serializer.dumps(
                            raw_data,
                            filetype=filetype,
                            non_data_dict_keys=NON_DATA_DICT_KEYS + ("type", "dataset_type"),
                        )
                    )

                case DatasetFormat.UNSTRUCTURED:
                    if dataset_filter is not None:
                        raise InvalidAction(
                            "Cannot provide a dataset filter when retrieving non-entity data"
                        )
                    data = await self.repository.dataset_data.get_unstructured_data(dataset_id)
                    #
                    # prevent pydantic from processing the data section
                    raw_data = DatasetWithDataOut.from_domain(
                        dataclasses.replace(existing, data={})
                    ).model_dump(mode="json")
                    raw_data["data"] = data
                    outfile.write(dump_dict(raw_data, filetype=filetype))

                case DatasetFormat.BINARY:
                    if dataset_filter is not None:
                        raise InvalidAction(
                            "Cannot provide a dataset filter when retrieving non-entity data"
                        )
                    streamer = await self.repository.dataset_data.stream_binary_data(dataset_id)
                    async for chunk in streamer:
                        outfile.write(chunk)
                case _:
                    raise UnsupportedFileType(filetype)
        return pathlib.Path(outfile.name)

    async def get_entity_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_entity_data(dataset_id)

    async def get_unstructured_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_unstructured_data(dataset_id)

    async def get_binary_data(self, dataset_id: UUID):
        gen = await self.repository.dataset_data.stream_binary_data(dataset_id)
        result = b""
        async for chunk in gen:
            result += chunk
        return result

    async def stream_binary_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.stream_binary_data(dataset_id)

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

    async def patch_from_file(self, dataset_id: UUID, path: pathlib.Path):
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            raise ResourceDoesNotExist("dataset", id=dataset_id)

        dataset_type = existing.dataset_type
        assert dataset_type.format is not None
        if dataset_type.format != DatasetFormat.ENTITY_BASED:
            raise InvalidAction(f"Cannot patch dataset with format '{dataset_type.format.value}'")

        patch = DatasetPatchIn.read_from_file(path, self.serializer)
        current_data = await self.repository.dataset_data.get_entity_data(dataset_id)
        aggregator = DatasetStateAggregator(allow_new_entities=True)
        aggregator.add_dataset_data(current_data, is_initial=True)
        aggregator.add_dataset_data(
            patch.data, undefined_values_overwrite=patch.undefined_values_overwrite
        )
        state = aggregator.state  # store to local variable to prevent extra work in state property

        await self.repository.datasets.update(
            dataset_id,
            dataclasses.replace(
                existing, data=state, bounding_box=calculate_bounding_box_from_data(state)
            ),
        )

    async def prune(self, dataset_id: UUID):
        await self.repository.datasets.prune(dataset_id)
        await self.repository.dataset_data.delete(dataset_id)

    async def get_summary(self, dataset_id: UUID):
        return await self.repository.datasets.get_summary(dataset_id)

    async def _update_entity_based_dataset_from_file(
        self, dataset_id: UUID, dataset_type: DatasetType, path: pathlib.Path
    ):
        dataset = DatasetWithDataIn.read_entity_based_dataset_from_file(path, self.serializer)
        dataset = dataclasses.replace(
            dataset,
            dataset_type=self._ensure_compatible_dataset_type(
                existing=dataset_type, new=dataset.dataset_type, dataset_id=dataset_id
            ),
            bounding_box=calculate_bounding_box_from_data(t.cast(dict, dataset.data)),
        )

        return await self.repository.datasets.update(dataset_id, dataset)

    async def _update_unstructured_dataset_from_file(
        self, dataset_id: UUID, dataset_type: DatasetType, path: pathlib.Path
    ):
        dataset = DatasetWithDataIn.read_unstructured_dataset_from_file(path)
        dataset = dataclasses.replace(
            dataset,
            dataset_type=self._ensure_compatible_dataset_type(
                existing=dataset_type, new=dataset.dataset_type, dataset_id=dataset_id
            ),
        )

        return await self.repository.datasets.update(dataset_id, dataset)

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

        return await self.repository.datasets.update(
            dataset.id, obj=dataclasses.replace(dataset, data=path)
        )

    @staticmethod
    def _ensure_compatible_dataset_type(existing: DatasetType, new: DatasetType, dataset_id: UUID):
        if new.format is None:
            new = dataclasses.replace(new, format=existing.format)
        if new != existing:
            raise InvalidResource("dataset", id=dataset_id, message="Cannot change dataset type")
        return existing
