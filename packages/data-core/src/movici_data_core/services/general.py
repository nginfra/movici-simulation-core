import typing as t
from uuid import UUID

from movici_data_core.domain_model import (
    AttributeType,
    DatasetType,
    EntityType,
    ModelType,
    Workspace,
)
from movici_simulation_core import AttributeSchema

from .common import GenericService, ensure_valid_workspace

T_dom = t.TypeVar("T_dom")


class WorkspaceService(GenericService[Workspace]):
    @property
    def _repository(self):
        return self.repository.workspaces

    async def ensure_valid_workspace(self, name_or_id: str | None) -> Workspace:
        return await ensure_valid_workspace(name_or_id, self.repository)

    async def get_with_counts(self, name: str | None = None, id: UUID | None = None):
        result = await self.get(name, id)
        if result is None:
            return result
        return await self._repository.with_counts(result)


class DatasetTypeService(GenericService[DatasetType]):
    @property
    def _repository(self):
        return self.repository.dataset_types


class EntityTypeService(GenericService[EntityType]):
    @property
    def _repository(self):
        return self.repository.entity_types


class AttributeTypeService(GenericService[AttributeType]):
    @property
    def _repository(self):
        return self.repository.attribute_types

    async def as_schema(self):
        attribute_types = await self.list()
        return AttributeSchema(a.to_attribute_spec() for a in attribute_types)


class ModelTypeService(GenericService[ModelType]):
    @property
    def _repository(self):
        return self.repository.model_types
