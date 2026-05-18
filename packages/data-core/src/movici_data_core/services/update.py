import pathlib
from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.exceptions import ResourceDoesNotExist, UnsupportedFileType
from movici_data_core.schema import UpdateWithDataOut
from movici_data_core.services.common import random_suffix
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
        self.tmpfile_dir = tmpfile_dir

    async def list(self):
        return await self.repository.updates.list()

    async def get_update_as_file(self, update_id: UUID, filetype: FileType = FileType.JSON):
        if filetype not in self.serializer.supported_file_types():
            raise UnsupportedFileType(filetype)

        result = await self.repository.updates.get_by_id(update_id, with_data=False)
        if result is None:
            raise ResourceDoesNotExist("update", id=update_id)
        outfile = (
            self.tmpfile_dir / f"update-{result.dataset.name}-{result.timestamp}"
            f"-{result.iteration}-{random_suffix()}"
        ).with_suffix(filetype.default_extension)

        raw_data = self.serializer.dumps(
            {
                **UpdateWithDataOut.from_domain(result).model_dump(mode="json"),
                "data": await self.repository.updates.get_data(update_id),
            },
            filetype=filetype,
        )
        outfile.write_bytes(raw_data)
        return outfile

    async def store_update_from_file(self, path: pathlib.Path, filetype: FileType = FileType.JSON):
        if filetype not in self.serializer.supported_file_types():
            raise UnsupportedFileType(filetype)
        # TODO: catch serializer errors
        # update_dict = self.serializer.loads(path.read_bytes(), filetype)
        # update_dict = load_dict(path.read_bytes(), filetype)

    async def delete_all(self):
        await self.repository.updates.delete_all()
