from __future__ import annotations

import copy
import dataclasses
import datetime
import enum
import pathlib
import typing as t
from uuid import UUID

from movici_simulation_core.core import AttributeSpec, DataType
from movici_simulation_core.validate import MoviciDataRefInfo


class DatasetFormat(str, enum.Enum):
    """Format types for dataset storage.

    Matches the ``format`` field used in the platform:

    * ``ENTITY_BASED``: Entity-oriented JSON data, destructured into numpy arrays. Entity data is
      split up into entity groups that contain attributes. see also :ref:`movici-data-format`
    * ``UNSTRUCTURED``: Unstructured JSON data, stored as blob but JSON-loadable. A Dataset with
      ``UNSTRUCTURED`` data contains a ``"data"`` sections that can be JSON encoded, but is
      otherwise schemaless
    * ``BINARY``: Binary data, stored as blob and passed transparently. A Dataset with ``BINARY``
      data can contain any data that is not validated by ``movici-data-core``
    """

    ENTITY_BASED = "entity_based"
    UNSTRUCTURED = "unstructured"
    BINARY = "binary"


class ScenarioStatus(str, enum.Enum):
    INVALID = "invalid"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @classmethod
    def from_simulation_status(cls, simulation_status: SimulationStatus):
        return ScenarioStatus(simulation_status.value)


class SimulationStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


AttributeDataType = t.Type[bool | int | float | str]


def utcnow():
    return datetime.datetime.now(tz=datetime.timezone.utc)


@dataclasses.dataclass
class Workspace:
    """A Workspace is a logical unit for bundling Scenarios and Datasets. A Scenario must be in the
    same Workspace as any Dataset it references. Workspaces may group Scenarios and Datasets that
    belong to a certain project, organisation or that otherwise logically belong together.

    :param name: a *snake_case* workspace name, must be unique in the database
    :param display_name: a human readably display name
    :param id: the workspace ``UUID`` in the database (if any)
    :param scenario_count: the number of scenarios in this workspace
    :param dataset_count: the number of datasets in this workspace
    """

    name: str
    display_name: str
    id: UUID | None = dataclasses.field(compare=False, default=None)
    scenario_count: int | None = None
    dataset_count: int | None = None


@dataclasses.dataclass
class DatasetType:
    """A DatasetType determines the meaning of a Dataset. Every Dataset must have a type. Examples
    may be ``transport_network`` or ``tabular``

    :param name: a *snake_case* name, must be unique in the database
    :param format: determines how Dataset data is formatted
    :param mimetype: in case of a ``DatasetFormat.BINARY`` format, a dataset type may
        specify a mimetype. When adding data, the mimetype may be validated if given
    """

    name: str
    format: DatasetFormat | None = None
    mimetype: str | None = None
    id: UUID | None = dataclasses.field(compare=False, default=None)

    def is_equivalent(self, other: DatasetType):
        if self.format is None or other.format is None:
            return self.name == other.name
        return self == other


@dataclasses.dataclass
class EntityType:
    """Representation of an entity type

    :param name: a *snake_case* name, must be unique in the database
    :param id: the entity type ``UUID`` in the database (if any)
    """

    name: str
    id: UUID | None = dataclasses.field(compare=False, default=None)


@dataclasses.dataclass
class AttributeType:
    """
    An attribute type contains information about an attribute. Every attribute must have a type.
    Equivalent to an :class:`AttributeSpec` and can be converted to and from :class:`AttributeSpec`

    :param name: a *snake_case* name for the attribute type. Must be unique in the database
    :param data_type: The data type of the attribute
    :param id: the attribute type ``UUID`` in the database (if any)
    :param unit: the unit of the attribute, such as ``m`` or ``s``. Default ``""`` (emtpy string)
    :param description: a description of the attribute describing it's meaning. Default
      ``""`` (empty string)
    :param enum_name: (Optional) in case of an ``enum`` attribute, the name of the ``enum``
    """

    name: str
    data_type: DataType

    id: UUID | None = dataclasses.field(compare=False, default=None)

    unit: str = ""
    description: str = ""
    enum_name: str | None = None

    @classmethod
    def from_attribute_spec(cls, spec: AttributeSpec):
        """Convert an :class:`AttributeSpec` to an :class:`AttributeType`"""
        return cls(name=spec.name, data_type=spec.data_type, enum_name=spec.enum_name)

    def to_attribute_spec(self):
        """Convert an :class:`AttributeType` to an :class:`AttributeSpec`"""
        return AttributeSpec(name=self.name, data_type=self.data_type, enum_name=self.enum_name)


@dataclasses.dataclass
class ModelType:
    """A model type is a definition of a model that may be used in a ``Scenario``. It must contain
    a jsonschema that validates model configs for that type in the ``Scenario`` config

    :param name: a *snake_case* name, must be unique in the database
    :param jsonschema: a ``jsonschema`` dict to validate any model configs for this model
      type. The json schema may contain movici custom keys such as ``movici.type`` and
      ``movici.datasetType``, to indicate a field is a reference to a Movici object such as a
      ``Dataset``,  ``EntityType`` or ``AttributeType``
    :param id: the model type ``UUID`` in the database (if any)
    """

    name: str
    jsonschema: dict | None = dataclasses.field(compare=False, default=None)

    id: UUID | None = dataclasses.field(compare=False, default=None)


class BoundingBox(t.NamedTuple):
    """Representation of a bounding box, if any of the components are ``None``, the bounding box
    is considered incomplete and reduces to ``None``
    """

    min_x: float | None
    min_y: float | None
    max_x: float | None
    max_y: float | None

    @classmethod
    def empty(cls) -> BoundingBox:
        """Return an empty BoundingBox (all fields set to None) that can be use as a basis for
        generating a bounding box from multiple datasets/updates
        """
        return BoundingBox(None, None, None, None)

    @classmethod
    def from_tuple_or_none(
        cls, obj: tuple[float | None, float | None, float | None, float | None] | None
    ):
        return BoundingBox(*obj) if obj else BoundingBox.empty()

    def as_tuple_or_none(self):
        if self.min_x is None or self.min_y is None or self.max_x is None or self.max_y is None:
            return None
        return self


@dataclasses.dataclass
class SimulationInfo:
    """A class to hold information about the time settings of the scenario. In a simulation, time
    progresses in discrete intervals, each with a time step of ``time_scale`` seconds. The total
    duration of the simulation is ``duration`` discrete intervals. The simulation starts at the
    discrete time step ``start_time``. For purposes of calculating the absolute (wall clock) time
    in the simulation, at ``t=start_time``, the absolute time has a unix timestamp
    ``reference``

    :param duration: the duration of the scenario in discrete time steps
    :param reference: the unix timestamp inside the simulation at ``t=0``
    :param time_scale: the size of a single discrete timestep in seconds. Default: ``1``
    :param start_time: the discrete time step to start the simulation at, usually ``t=0``.
      default: ``0``
    :param mode: must be set to ``"time_oriented". Default ``"time_oriented"``
    """

    duration: int
    reference: float
    time_scale: float = 1
    start_time: int = 0
    mode: t.Literal["time_oriented"] = "time_oriented"

    @classmethod
    def default(cls):
        return cls(reference=0, duration=1)


@dataclasses.dataclass
class SimulationStatusInfo:
    SIMULATION_REPORT_THRESHOLD = datetime.timedelta(seconds=10)
    status: SimulationStatus
    timestamp: datetime.datetime

    def get_scenario_status(self) -> ScenarioStatus:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc)
        status = self.status
        if (
            self.status == SimulationStatus.RUNNING
            and self.timestamp + self.SIMULATION_REPORT_THRESHOLD < timestamp
        ):
            status = SimulationStatus.FAILED
        return ScenarioStatus.from_simulation_status(status)


@dataclasses.dataclass
class Scenario:
    r"""A Scenario is a description of a simulation. It contains a collection of models that should
    work togehter on a collection of datasets in order to perform a certain, specific, calculation,
    as well as other information such as the timeline information

    :param name: a *snake_case* name, must be unique in the workspace
    :param display_name: a human readable display name
    :param description: a human readable description of the scenario
    :param epsg_code: The coordinate reference system (as an EPSG code) of the scenario
    :param bounding_box: the scenario bounding box (output only)
    :param simulation_info: the scenario simulation info
    :param simulation_status_info: a :class:`SimulationStatusInfo` object
    :param status: the scenario status
    :param id: the scenario ``UUID`` in the database (if any)
    :param workspace: The workspace the scenario belongs to (if any)
    :param created_at: the datetime the scenario was created
    :param updated_at: the datetime the scenario was updated
    :param models: a list of ``ScenarioModel``\s for this scenario
    :param datasets: a list of ``ScenarioDataset``\s for this scenario
    """

    name: str
    display_name: str
    description: str

    epsg_code: int | None = None
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)
    simulation_info: SimulationInfo = dataclasses.field(default_factory=SimulationInfo.default)
    simulation_status_info: SimulationStatusInfo | None = None
    status: ScenarioStatus = ScenarioStatus.READY

    id: UUID | None = None
    workspace: Workspace | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    models: list[ScenarioModel] = dataclasses.field(default_factory=list)
    datasets: list[ScenarioDataset] = dataclasses.field(default_factory=list)
    has_updates: bool = False

    def with_status(self, datasets_have_data: dict[UUID, bool]):
        """Return a new ``Scenario`` with the ``status`` field updated based on the availability
        of required initial data and its ``SimulationStatusInfo``. Every entry in
        ``Scenario.datasets`` must have an ``id``.

        A Scenario status is ``INVALID`` as long as its datasets do not have data. Otherwise, it
        depends on its simulation status (which can be set through the api). A ``RUNNING``
        simulation status is only valid if it has been last set within a certain time threshold,
        otherwise it will be assumed that the simulation has stalled, marking it ``FAILED``. If the
        scenario has no simulation status but it has updates, then the status will be assumed to be
        ``SUCCEEDED``. If there is no simulation status, and no updates, but all its datasets have
        data, then the scenario is marked ``READY``

        :param datasets_have_data: a dictionary with Dataset UUIDs as keys and a boolean indicating
            whether that dataset has data available. Any dataset that is configured for the
            scenario but not in ``datasets_have_data`` is ignored
        :return: A copy of the ``Scenario`` with the updated ``status`` field
        """
        status = ScenarioStatus.READY  # the default status is READY
        dataset_ids = {dataset.id for dataset in self.datasets}
        if None in dataset_ids:
            raise ValueError(
                "every dataset in Scenario.datasets must have an"
                " id set in order to calculate the status"
            )
        if not all(
            datasets_have_data.get(ds_id, True) for ds_id in t.cast(set[UUID], dataset_ids)
        ):
            status = ScenarioStatus.INVALID
        else:
            if self.has_updates:
                status = ScenarioStatus.SUCCEEDED
            if self.simulation_status_info is not None:
                status = self.simulation_status_info.get_scenario_status()
        return dataclasses.replace(self, status=status)


@dataclasses.dataclass
class ScenarioDataset:
    """A representation of a dataset in a scenario

    :param name: the dataset name
    :param dataset_type: the dataset dataset type
    :param id: the dataset ``UUID`` in the database (if any)
    """

    name: str
    dataset_type: DatasetType | None = dataclasses.field(default=None)
    id: UUID | None = dataclasses.field(compare=False, default=None)

    @classmethod
    def from_dataset(cls, dataset: Dataset):
        return ScenarioDataset(
            name=dataset.name,
            dataset_type=dataset.dataset_type,
            id=dataset.id,
        )


@dataclasses.dataclass
class ScenarioModel:
    """A configured model in a scenario

    :param name: a *snake_case* model name. Must be unique in a scenario
    :param type: the model type
    :param config: the model config dict
    :param references: a list of :class:`MoviciDataRefInfo` objects that were extracted from the
        model config dict
    """

    name: str
    type: ModelType
    config: dict = dataclasses.field(default_factory=dict)
    references: list[MoviciDataRefInfo] = dataclasses.field(default_factory=list, compare=False)

    def __post_init__(self):
        if invalid_fields := self.config.keys() & {"name", "type"}:
            raise ValueError(
                "Prohibited keys in found in ScenarioModel.config: "
                + ", ".join(sorted(invalid_fields))
            )

    def with_populated_config(self):
        return dataclasses.replace(self, config=self._populated_config())

    def as_dict(self):
        result = self._populated_config()
        result["name"] = self.name
        result["type"] = self.type.name
        return result

    def _populated_config(self):
        result = copy.deepcopy(self.config)

        for ref in self.references:
            ref.set_value(result)
        return result


DatasetData = dict | bytes | t.BinaryIO | pathlib.Path


@dataclasses.dataclass
class Dataset:
    """
    :param name: a *snake_case* dataset name, must be unique in the Workspace
    :param display_name: a human readable display name
    :param dataset_type: the dataset's type
    :param id: the dataset ``UUID`` in the database (if any)
    :param workspace: the :class:`Workspace` the dataset belongs to (if any)
    :param general: the dataset's general section (dict) for ``ENTITY_BASED`` and ``UNSTRUCTURED``
        datasets (if any)
    :param epsg_code: the dataset's CRS as an EPSG code
    :param bounding_box: the datasets :class:`BoundingBox` if it contains geospatial data (output
        only)
    :param created_at: the datetime the dataset was created
    :param updated_at: the datetime the dataset was updated
    :param data: the dataset's data, if presented or loaded
    :param has_data: whether the dataset has data in the database
    """

    name: str
    display_name: str
    dataset_type: DatasetType
    id: UUID | None = None
    workspace: Workspace | None = None

    general: dict | None = None
    epsg_code: int | None = None
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    data: DatasetData | None = None
    has_data: bool = False


@dataclasses.dataclass
class UpdateModel:
    """A short form of a ``ScenarioModel`` to be used by ``Update``. Contains only the name and
    the type, and the type is optional
    :param name: the model name from the scenario
    :param type: Optional ``ModelType`` from the scenario.
    """

    name: str
    type: ModelType | None = None

    @classmethod
    def from_scenario_model(cls, scenario_model: ScenarioModel):
        return UpdateModel(scenario_model.name, type=scenario_model.type)


@dataclasses.dataclass
class Update:
    """An Update is a change to the :term:`World State` in a simulation. An update is always
    produced by a model at a certain timestamp

    :param dataset: The dataset this update changes the state for
    :param timestamp: the discrete time step this update was produced in the simulation
    :param iteration: the iteration at the timestamp this update was created. Every update in a
        scenario must have a unique (timestamp, iteration) combination
    :param model: the model in the scenario that produced the update
    :param bounding_box: The bounding_box of the update, in case it contains geospatial attributes.
        the values should be in the same CRS as its dataset
    :param id: the update ``UUID`` in the database (if any)
    :param created_at: the datetime the update was created
    :param data: the update data payload
    """

    dataset: ScenarioDataset
    timestamp: int
    iteration: int

    model: UpdateModel
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)

    id: UUID | None = None
    created_at: datetime.datetime | None = None
    data: DatasetData | None = None


@dataclasses.dataclass
class DatasetSummary:
    """A DatasetSummary is an overview of the entity groups and attributes in a (``ENTITY_BASED``
    dataset. It also contains some other information, such as the dataset general section as well
    as the EPSG code and bounding box. A ``DatasetSummary`` is an output only object

    :param general: the dataset general section
    :param epsg_code: the dataset's CRS as an EPSG code
    :param bounding_box: the dataset's :class:`BoundingBox` if it contains geospatial data
    :param entity_groups: a summary of the entity groups in the dataset
    :param count: the total number of entities in the dataset
    """

    general: dict
    epsg_code: int | None
    bounding_box: BoundingBox
    entity_groups: list[EntityGroupSummary]
    count: int


@dataclasses.dataclass
class EntityGroupSummary:
    """an entry in the :attr:`DatasetSummary.entity_groups` list. Contains a summary of a single
    entity group.

    :param name: the entity group name (equal to its type)
    :param count: the number of entities in this entity group
    :param attributes: a summary of the attributes in the entity groups
    """

    name: str
    count: int
    attributes: list[AttributeSummary]


T_datatype = t.TypeVar("T_datatype", bool, int, float, str)


# TODO: Reuse fields from AttributeType, perhaps introducing a BaseAttributeType class
@dataclasses.dataclass
class AttributeSummary(t.Generic[T_datatype]):
    """an entry in the :attr:`EntityGroupSummary.entity_groups` list. Contains a summary of a
    single entity group.

    :param name: the attribute name (equal to its type)
    :param data_type: the attribute's data type
    :param description: the attribute type's description
    :param enum_name: the attribute type's enum name (if any)
    :param unit: the attributes type's unit
    :param min_val: the minimum value of the attribute for the associated entity group (if any)
    :param max_val: the maximum value of the attribute for the associated entity group (if any)
    """

    name: str
    data_type: DataType[T_datatype]
    description: str
    enum_name: str | None
    unit: str
    min_val: T_datatype | None
    max_val: T_datatype | None
