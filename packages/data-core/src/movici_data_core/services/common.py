import typing as t
from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.database.repository.common import GenericResourceRepository
from movici_data_core.exceptions import InvalidAction

T_dom = t.TypeVar("T_dom")


class GenericService(t.Generic[T_dom]):
    def __init__(self, repository: SQLAlchemyRepository):
        self.repository = repository

    @property
    def _repository(self) -> GenericResourceRepository[T_dom]:
        raise NotImplementedError

    async def list(self):
        return await self._repository.list()

    async def get(self, name: str | None = None, id: UUID | None = None) -> T_dom | None:
        if name is not None:
            result = await self._repository.get_by_name(name)
        elif id is not None:
            result = await self._repository.get_by_id(id)
        else:
            raise InvalidAction("name or id is required")

        return result

    async def create(self, obj: T_dom):
        return await self._repository.create(obj)

    async def update(self, id: UUID, obj: T_dom):
        return await self._repository.update(id=id, obj=obj)

    async def delete(self, id: UUID):
        return await self._repository.delete(id)
