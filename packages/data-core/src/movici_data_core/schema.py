from __future__ import annotations

import dataclasses
import datetime
import functools
import pathlib
import typing as t
from uuid import UUID

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
)

from movici_data_core import domain_model
from movici_data_core.domain_model import (
    BoundingBox,
    DatasetType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    SimulationInfo,
    Update,
    UpdateModel,
)
from movici_data_core.exceptions import (
    DeserializationError,
    MoviciValidationError,
    UnsupportedFileType,
)
from movici_data_core.serialization import load_dict
from movici_simulation_core.core.data_format import NON_DATA_DICT_KEYS, data_keys
from movici_simulation_core.types import ExternalSerializationStrategy, FileType

T_dom = t.TypeVar("T_dom")


BoundingBoxField = t.Annotated[
    BoundingBox,
    PlainSerializer(lambda bbox: bbox.as_tuple_or_none()),
    WithJsonSchema(
        {
            "title": "Bounding Box",
            "type": "array",
            "maxItems": 4,
            "minItems": 4,
            "items": {"type": "number"},
        }
    ),
]


class OutModel(BaseModel, t.Generic[T_dom]):
    model_config = ConfigDict(from_attributes=True)
    __envelope__: t.ClassVar[str | None] = None

    @classmethod
    def from_domain(cls, obj: T_dom):
        if cls.__envelope__ is not None:
            return cls.model_validate({cls.__envelope__: obj})
        return cls.model_validate(obj)


class WorkspaceIn(BaseModel):
    name: str
    display_name: str

    def to_domain(self):
        return domain_model.Workspace(name=self.name, display_name=self.display_name)


class WorkspaceOut(WorkspaceIn, OutModel[domain_model.Workspace]):
    id: UUID
    scenario_count: int
    dataset_count: int


class WorkspaceListOut(OutModel[t.Sequence[domain_model.Workspace]]):
    __envelope__ = "workspaces"
    workspaces: list[WorkspaceOut]


class ShortDatasetIn(BaseModel):
    name: str
    display_name: str = ""
    type: DatasetType | str

    def to_domain(self):
        return domain_model.Dataset(
            name=self.name,
            display_name=self.display_name or self.name,
            dataset_type=DatasetType(self.type) if isinstance(self.type, str) else self.type,
        )


class ShortDatasetOut(OutModel[domain_model.Dataset]):
    id: UUID
    name: str
    display_name: str
    type: DatasetType = Field(validation_alias="dataset_type")
    has_data: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DatasetList(OutModel[t.Sequence[domain_model.Dataset]]):
    __envelope__ = "datasets"
    datasets: list[ShortDatasetOut]


class ScenarioIn(BaseModel):
    name: str
    display_name: str
    description: str = ""
    epsg_code: int | None = None
    simulation_info: SimulationInfoInOut
    models: list[ScenarioModelIn]
    datasets: list[ScenarioDatasetIn]

    def to_domain(self):
        return domain_model.Scenario(
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            epsg_code=self.epsg_code,
            simulation_info=self.simulation_info.to_domain(),
            datasets=[ds.to_domain() for ds in self.datasets],
            models=[model.to_domain() for model in self.models],
        )


class SimulationInfoInOut(OutModel[SimulationInfo]):
    duration: int
    reference: float
    time_scale: float
    start_time: int
    mode: t.Literal["time_oriented"] = "time_oriented"

    def to_domain(self):
        return domain_model.SimulationInfo(
            duration=self.duration,
            reference=self.reference,
            time_scale=self.time_scale,
            start_time=self.start_time,
            mode=self.mode,
        )


class ScenarioDatasetIn(BaseModel):
    name: str
    type: DatasetType | str | None

    def to_domain(self):
        dataset_type = DatasetType(self.type) if isinstance(self.type, str) else self.type
        return ScenarioDataset(name=self.name, dataset_type=dataset_type)


class ScenarioDatasetOut(OutModel[ScenarioDataset]):
    name: str
    type: DatasetType = Field(validation_alias="dataset_type")
    id: UUID


class ScenarioModelIn(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: str | ModelType

    def to_domain(self):
        return domain_model.ScenarioModel(
            name=self.name,
            type=ModelType(self.type) if isinstance(self.type, str) else self.type,
            config=self.__pydantic_extra__ or {},
        )


class ScenarioModelOut(OutModel[ScenarioModel]):
    model_config = ConfigDict(extra="allow")
    name: str
    type: t.Annotated[
        str | ModelType, BeforeValidator(lambda v: v.name if isinstance(v, ModelType) else v)
    ]

    @classmethod
    def from_domain(cls, obj: ScenarioModel):
        return ScenarioModelOut(name=obj.name, type=obj.type, **obj.config)


class ScenarioOut(OutModel[Scenario]):
    id: UUID
    name: str
    display_name: str
    description: str
    epsg_code: int | None
    simulation_info: SimulationInfoInOut
    models: list[t.Annotated[ScenarioModelOut, BeforeValidator(ScenarioModelOut.from_domain)]]
    datasets: list[ScenarioDatasetOut]


class DatasetWithDataIn(ShortDatasetIn):
    """Full input dataset model, only relevant for `ENTITY_BASED` and `UNSTRUCTURED` datasets"""

    epsg_code: int | None = None
    general: dict | None = None
    data: dict | None = None

    @classmethod
    def read_entity_based_dataset_from_file(
        cls, path: pathlib.Path, serializer: ExternalSerializationStrategy
    ):
        filetype = FileType.from_extension(path.suffix)
        if filetype not in serializer.supported_file_types():
            raise UnsupportedFileType(filetype)

        dataset_dict = cls.load_dict(
            path,
            filetype,
            dict_loader=functools.partial(
                serializer.loads, non_data_dict_keys=NON_DATA_DICT_KEYS + ("type", "dataset_type")
            ),
        )
        dataset_data = dataset_dict.pop("data", {})
        dataset = DatasetWithDataIn.model_validate(dataset_dict).to_domain()
        return dataclasses.replace(dataset, data=dataset_data)

    @classmethod
    def read_unstructured_dataset_from_file(cls, path: pathlib.Path):
        filetype = FileType.from_extension(path.suffix)
        if filetype not in (FileType.JSON, FileType.MSGPACK):
            raise UnsupportedFileType(filetype)
        dataset_dict = cls.load_dict(path, filetype, dict_loader=load_dict)
        dataset_data = dataset_dict.pop("data", {})
        dataset = DatasetWithDataIn.model_validate(dataset_dict).to_domain()
        return dataclasses.replace(dataset, data=dataset_data)

    @classmethod
    def load_dict(
        cls, path: pathlib.Path, filetype, dict_loader: t.Callable[[bytes, FileType], dict]
    ) -> dict:
        try:
            return dict_loader(path.read_bytes(), filetype)
        except (TypeError, ValueError) as e:
            raise DeserializationError from e

    def to_domain(self):
        return dataclasses.replace(
            super().to_domain(),
            general=self.general,
            epsg_code=self.epsg_code,
            data=self.data,
        )


class DatasetWithDataOut(ShortDatasetOut):
    """Full output dataset model, only relevant for `ENTITY_BASED` and `UNSTRUCTURED` datasets"""

    epsg_code: int | None = None
    bounding_box: BoundingBoxField | None = None
    general: dict | None = None
    data: dict


class UpdateModelIn(BaseModel):
    name: str
    type: str | None = None

    def to_domain(self):
        return UpdateModel(
            name=self.name, type=ModelType(name=self.type) if self.type is not None else None
        )


class UpdateModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    type: t.Annotated[str, BeforeValidator(lambda v: v.name)]


class ShortUpdateOut(OutModel[Update]):
    id: UUID
    dataset: ScenarioDatasetOut
    model: UpdateModelOut
    timestamp: int
    iteration: int
    created_at: datetime.datetime


class UpdateWithDataOut(ShortUpdateOut):
    data: dict | None

    @classmethod
    def write_to_file(
        cls,
        update: Update,
        path: pathlib.Path | t.BinaryIO,
        serializer: ExternalSerializationStrategy,
        filetype: FileType,
    ):
        """
        Serialize and write an Update to a file.

        :param update: the Update to write
        :param file: Either a ``pathlib.Path`` or a file-like object. If given a file-like object
            it must be opened writable in bytes mode. This method will not open or close the object
        :param serializer: an object implementing ``ExternalSerializationStrategy``, usually
            ``EntityInitDataFormat``
        :param filetype: A :class:`FileType`. This must be a ``FileType`` that is supported by
            the serializer
        """
        if not isinstance(update.data, dict):
            raise TypeError(
                f"Update data must be of type dict, not type {type(update.data).__name__}"
            )

        # strip data from the update since it interferes with pydantic
        data = update.data
        update = dataclasses.replace(update, data=None)

        raw_data = serializer.dumps(
            {
                **UpdateWithDataOut.from_domain(update).model_dump(mode="json"),
                "data": data,
            },
            filetype=filetype,
            non_data_dict_keys=NON_DATA_DICT_KEYS + ("model", "dataset"),
        )
        if isinstance(path, pathlib.Path):
            path.write_bytes(raw_data)
        else:
            path.write(raw_data)


class UpdateIn(BaseModel):
    """Validator for incoming updates. The validator does not process the updates "data" key, this
    must be done separately. However, the ``read_from_file`` method, does process the "data" key
    as well
    """

    dataset: ScenarioDatasetIn
    model: UpdateModelIn
    timestamp: int
    iteration: int
    created_at: datetime.datetime | None = None

    @classmethod
    def read_from_file(
        cls,
        path: pathlib.Path,
        serializer: ExternalSerializationStrategy,
        filetype: FileType | None = None,
    ) -> Update:
        """Read an Update from a file. The update cannot contain multiple keys that contain dataset
        data, and that key must either be ``"data"`` or the update's dataset name

        :param path: A path to an file containing an update. The file must be in a format that the
        serializer supports, which is generally either JSON or MessagePack.
        :param serializer: An object that inherits from ``ExternalSerializationStrategy``.
        :param filetype: The filetype for the file. If given, it will be explictly (attempted to
        be) read as a file of this type. If not given, or None, the filetype will be guessed from
            the filename (suffix)

        :return: An Update with the data section in Movici format
        """
        filetype = filetype or FileType.from_extension(path.suffix)
        if filetype not in serializer.supported_file_types():
            raise UnsupportedFileType(filetype)

        try:
            update_dict = serializer.loads(
                path.read_bytes(),
                filetype,
                non_data_dict_keys=NON_DATA_DICT_KEYS + ("dataset", "model"),
            )
        except (TypeError, ValueError) as e:
            # TODO: better error message from serializer.loads
            raise DeserializationError from e

        all_data_keys = data_keys(
            update_dict, ignore_keys=NON_DATA_DICT_KEYS + ("dataset", "model")
        )

        # Our data format in theory supports multiple datasets in updates. This is required because
        # models may need to send an update on multiple datasets in a single update. In that case
        # the multiple datasets are added to the update with the dataset name as a key in the root
        # level of the update dict. In the data-core side, we only support a single dataset per
        # so we need to extract exactly one data key containing a dataset. The key can either be
        # "data" or the dataset's name (as given under the "dataset_name" key)
        if len(all_data_keys) == 0:
            raise MoviciValidationError({"data": ["data is a required key"]})
        if len(all_data_keys) > 1:
            raise MoviciValidationError("Please only supply a single data key")
        data_key = next(iter(all_data_keys))

        update = UpdateIn.model_validate(update_dict).to_domain()

        if data_key not in (update.dataset.name, "data"):
            raise MoviciValidationError({data_key: ["data key is not equal to dataset name"]})
        data = update_dict.pop(data_key)

        return dataclasses.replace(update, data=data)

    def to_domain(self):
        return Update(
            dataset=self.dataset.to_domain(),
            timestamp=self.timestamp,
            iteration=self.iteration,
            model=self.model.to_domain(),
            created_at=self.created_at,
        )
