import dataclasses
import pathlib
import typing as t
from uuid import UUID

from movici_data_core.bounding_box import calculate_bounding_box_from_data
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.exceptions import UnsupportedFileType
from movici_data_core.file_helpers import tempfile_delete_on_error
from movici_data_core.schema import UpdateIn, UpdateWithDataOut
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


class UpdateService:
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
        return await self.repository.updates.list()

    async def get_update_as_file(
        self, update_id: UUID, filetype: FileType = FileType.JSON
    ) -> pathlib.Path | None:
        if filetype not in self.serializer.supported_file_types():
            raise UnsupportedFileType(filetype)

        result = await self.repository.updates.get_by_id(update_id, with_data=True)
        if result is None:
            return result

        with tempfile_delete_on_error(
            suffix=filetype.default_extension,
            prefix=f"update-{result.dataset.name}-{result.timestamp}-{result.iteration}-",
            dir=self.tmpfile_dir,
        ) as outfile:
            UpdateWithDataOut.write_to_file(
                result, t.cast(t.BinaryIO, outfile), self.serializer, filetype
            )
        return pathlib.Path(outfile.name)

    async def store_update_from_file(
        self, path: pathlib.Path, filetype: FileType | None = None
    ) -> UUID:
        update = UpdateIn.read_from_file(path, self.serializer, filetype)
        return await self.repository.updates.create(
            dataclasses.replace(
                update,
                bounding_box=calculate_bounding_box_from_data(t.cast(dict, update.data)),
            )
        )

    async def delete_all(self):
        await self.repository.updates.delete_all()
