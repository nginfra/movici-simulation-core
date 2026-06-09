import typing as t
from uuid import UUID

from movici_data_core.domain_model import (
    AttributeType,
    DatasetType,
    EntityType,
    ModelType,
    Workspace,
)
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_simulation_core import AttributeSchema

from .common import GenericService

T_dom = t.TypeVar("T_dom")


class WorkspaceService(GenericService[Workspace]):
    @property
    def _repository(self):
        return self.repository.workspaces

    async def ensure_valid_workspace(self, name_or_id: str) -> Workspace:
        # try workspace as a UUID
        try:
            workspace_id = UUID(name_or_id)
        except ValueError:
            workspace_id = None

        if workspace_id is not None:
            # workspace was given as a uuid
            workspace_obj = await self._repository.get_by_id(id=workspace_id)
            if workspace_obj is None:
                raise ResourceDoesNotExist("workspace", id=workspace_id)
        else:
            # workspace was given as a name
            workspace_obj = await self._repository.get_by_name(name_or_id)
            if workspace_obj is None:
                raise ResourceDoesNotExist("workspace", name=name_or_id)

        return workspace_obj

    async def with_counts(self, workspace: Workspace):
        return await self._repository.with_counts(workspace)


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
