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
    r"""SQLAlchemyRepository contains the collection of ``SQLResourceRepository``\s that are the
    repositories for the various resources. A SQLAlchemyRepository can be tied to a specific
    workspace or scenario, which is relevant for the `datasets`, `scenarios` and `updates`
    repositories.

    :param session: a SQLAlchemy async session
    :param options: the current database :class:`Options`
    :param workspace_id: an optional workspace UUID
    :param scenario_id: an optional scenario UUID
    """

    session: AsyncSession
    options: Options
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None

    def for_workspace(self, workspace_id: UUID):
        """Bind the repository to a specific workspace. This is generally done automatically by the
        :class:`SQLAlchemyBackend` managing this repository. A SQLAlchemyRepository must be bound
        to a specific workspace for operations on Datasets, Scenarios and Updates

        :param workspace_id: the Workspace UUID to bind the repository to
        :return: a copy of the SQLAlchemyRepository bound to the workspace. The original repository
            remains in tact
        """
        return dataclasses.replace(self, workspace_id=workspace_id)

    def for_scenario(self, scenario_id: UUID):
        """Bind the repository to a specific scenario. This is generally done automatically by the
        :class:`SQLAlchemyBackend` managing this repository. A SQLAlchemyRepository must be bound
        to a specific scenario for operations that require a specific scenario, such as retrieving,
        updating or deleting a Scenario.

        :param scenario_id: the Scenario UUID to bind the repository to
        :return: a copy of the SQLAlchemyRepository bound to the scenario. The original repository
            remains in tact
        """
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
