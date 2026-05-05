from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import Update
from movici_simulation_core.types import ExternalSerializationStrategy


class UpdateService:
    def __init__(
        self,
        repository: SQLAlchemyRepository,
        serializer: ExternalSerializationStrategy,
    ):
        self.repository = repository
        self.serializer = serializer
        self.tmpfile_path = None

    async def list(self):
        return await self.repository.updates.list()

    async def get_update_as_file(self, id: UUID) -> Update | None:
        return

    async def create_update_from_file(self, id: UUID) -> Update | None:
        return

    async def delete_all(self):
        return
