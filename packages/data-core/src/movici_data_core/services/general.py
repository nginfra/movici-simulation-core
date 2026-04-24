import typing as t

from movici_data_core.domain_model import (
    AttributeType,
    DatasetType,
    EntityType,
    ModelType,
    Workspace,
)
from movici_data_core.types import T_id
from movici_simulation_core import AttributeSchema

from .common import GenericService

T_dom = t.TypeVar("T_dom")


class WorkspaceService(GenericService[T_id, Workspace]):
    @property
    def _repository(self):
        return self.repository.workspaces


class DatasetTypeService(GenericService[T_id, DatasetType]):
    @property
    def _repository(self):
        return self.repository.dataset_types


class EntityTypeService(GenericService[T_id, EntityType]):
    @property
    def _repository(self):
        return self.repository.entity_types


class AttributeTypeService(GenericService[T_id, AttributeType]):
    @property
    def _repository(self):
        return self.repository.attribute_types

    async def as_schema(self):
        attribute_types = await self.list()
        return AttributeSchema(a.to_attribute_spec() for a in attribute_types)


class ModelTypeService(GenericService[T_id, ModelType]):
    @property
    def _repository(self):
        return self.repository.model_types
