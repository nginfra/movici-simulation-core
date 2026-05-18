import dataclasses
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..model import Options
from .dataset import DatasetDataRepository, DatasetRepository
from .general import (
    AttributeTypeRepository,
    DatasetTypeRepository,
    EntityTypeRepository,
    ModelTypeRepository,
)
from .scenario import ScenarioRepository
from .updates import UpdateRepository
from .workspace import WorkspaceRepository


@dataclasses.dataclass
class SQLAlchemyRepository:
    session: AsyncSession
    options: Options
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None

    def for_workspace(self, workspace_id: UUID | None):
        if workspace_id is None:
            raise ValueError("A workspace id must be given")
        return dataclasses.replace(self, workspace_id=workspace_id)

    def for_scenario(self, scenario_id: UUID):
        return dataclasses.replace(self, scenario_id=scenario_id)

    # define these fields as properties to prevent cyclic references and simplify GC
    @property
    def workspaces(self):
        return WorkspaceRepository(self.session, self.options, self)

    @property
    def dataset_types(self):
        return DatasetTypeRepository(self.session, self.options, self)

    @property
    def entity_types(self):
        return EntityTypeRepository(self.session, self.options, self)

    @property
    def attribute_types(self):
        return AttributeTypeRepository(self.session, self.options, self)

    @property
    def model_types(self):
        return ModelTypeRepository(self.session, self.options, self)

    @property
    def datasets(self):
        return DatasetRepository(self.session, self.options, self, workspace_id=self.workspace_id)

    @property
    def dataset_data(self):
        return DatasetDataRepository(self.session, self.options, self)

    @property
    def scenarios(self):
        return ScenarioRepository(
            self.session,
            self.options,
            self,
            workspace_id=self.workspace_id,
            scenario_id=self.scenario_id,
        )

    @property
    def updates(self):
        if self.scenario_id is None:
            raise ValueError("SQLAlchemyRepository.scenario_id must be set")
        return UpdateRepository(self.session, self.options, self, scenario_id=self.scenario_id)


__all__ = [
    "DatasetDataRepository",
    "DatasetRepository",
    "AttributeTypeRepository",
    "DatasetTypeRepository",
    "EntityTypeRepository",
    "ModelTypeRepository",
    "ScenarioRepository",
    "UpdateRepository",
    "WorkspaceRepository",
    "SQLAlchemyRepository",
]
