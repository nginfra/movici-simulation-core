from __future__ import annotations

import dataclasses
import datetime
import functools
import pathlib
import re
import typing as t
from uuid import UUID

from jsonschema import SchemaError
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    WithJsonSchema,
    field_validator,
)

from movici_data_core import domain_model
from movici_data_core.database.model import (
    ATTRIBUTE_DESCRIPTION_MAX_LENGTH,
    ATTRIBUTE_ENUM_NAME_MAX_LENGTH,
    ATTRIBUTE_NAME_MAX_LENGTH,
    ATTRIBUTE_UNIT_MAX_LENGTH,
    DATASET_TYPE_MIMETYPE_MAX_LENGTH,
    DEFAULT_DISPLAY_NAME_MAX_LENGTH,
    DEFAULT_NAME_MAX_LENGTH,
    SCENARIO_DESCRIPTION_MAX_LENGTH,
    snake_case_pattern,
)
from movici_data_core.domain_model import (
    AttributeSummary,
    AttributeType,
    BoundingBox,
    Dataset,
    DatasetFormat,
    DatasetSummary,
    DatasetType,
    EntityGroupSummary,
    EntityType,
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
    SimulationInfo,
    Update,
    UpdateModel,
    Workspace,
)
from movici_data_core.exceptions import (
    DeserializationError,
    MoviciValidationError,
    UnsupportedFileType,
)
from movici_data_core.serialization import load_dict
from movici_simulation_core import DataType
from movici_simulation_core.core.data_format import NON_DATA_DICT_KEYS, data_keys
from movici_simulation_core.types import ExternalSerializationStrategy, FileType
from movici_simulation_core.validate import movici_validator

T_dom = t.TypeVar("T_dom")

NameStr = t.Annotated[str, Field(max_length=DEFAULT_NAME_MAX_LENGTH, pattern=snake_case_pattern)]
AttributeNameStr = t.Annotated[
    str, Field(max_length=ATTRIBUTE_NAME_MAX_LENGTH, pattern=snake_case_pattern)
]

BoundingBoxField = t.Annotated[
    BoundingBox | None,
    PlainSerializer(lambda bbox: bbox.as_tuple_or_none()),
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
                {"type": "null"},
            ]
        }
    ),
]


class InModel(BaseModel, t.Generic[T_dom]):
    def to_domain(self) -> T_dom:
        raise NotImplementedError


class OutModel(BaseModel, t.Generic[T_dom]):
    """Base class for output (serialization) models

    :cvar __envelope__: An optional string that may be used as the envelope when serializing a
        sequence of objects. Instead of serializing to a list, the objects will be serialzed to
        a dictionary containing the envelope key, and then the serialized sequence of objects
    """

    model_config = ConfigDict(from_attributes=True)
    __envelope__: t.ClassVar[str | None] = None

    @classmethod
    def from_domain(cls, obj: T_dom):
        if cls.__envelope__ is not None:
            return cls.model_validate({cls.__envelope__: obj})
        return cls.model_validate(obj)


class WorkspaceIn(InModel):
    name: NameStr
    display_name: t.Annotated[str, Field(max_length=DEFAULT_DISPLAY_NAME_MAX_LENGTH)]

    def to_domain(self):
        return Workspace(name=self.name, display_name=self.display_name)


class WorkspaceOut(OutModel[Workspace]):
    id: UUID
    name: str
    display_name: str
    scenario_count: int
    dataset_count: int


class WorkspaceListOut(OutModel[t.Sequence[Workspace]]):
    __envelope__ = "workspaces"
    workspaces: list[WorkspaceOut]


class ShortDatasetIn(InModel[Dataset]):
    name: NameStr
    display_name: t.Annotated[str, Field(max_length=DEFAULT_DISPLAY_NAME_MAX_LENGTH)] = ""
    type: domain_model.DatasetType | NameStr

    def to_domain(self):
        return Dataset(
            name=self.name,
            display_name=self.display_name or self.name,
            dataset_type=DatasetType(self.type) if isinstance(self.type, str) else self.type,
        )


class ShortDatasetOut(OutModel[Dataset]):
    id: UUID
    name: str
    display_name: str
    # refer using namespace to statisfy sphinx autodoc
    type: domain_model.DatasetType = Field(validation_alias="dataset_type")
    has_data: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DatasetListOut(OutModel[t.Sequence[Dataset]]):
    __envelope__ = "datasets"
    datasets: list[ShortDatasetOut]


class ScenarioIn(BaseModel):
    name: NameStr
    display_name: t.Annotated[str, Field(max_length=DEFAULT_DISPLAY_NAME_MAX_LENGTH)]
    description: t.Annotated[str, Field(max_length=SCENARIO_DESCRIPTION_MAX_LENGTH)] = ""
    epsg_code: int | None = None
    simulation_info: SimulationInfoInOut
    models: list[ScenarioModelIn]
    datasets: list[ScenarioDatasetIn]

    def to_domain(self):
        return Scenario(
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            epsg_code=self.epsg_code,
            simulation_info=self.simulation_info.to_domain(),
            datasets=[ds.to_domain() for ds in self.datasets],
            models=[model.to_domain() for model in self.models],
        )


class SimulationInfoInOut(InModel[SimulationInfo], OutModel[SimulationInfo]):
    duration: int
    reference: float
    time_scale: float
    start_time: int
    mode: t.Literal["time_oriented"] = "time_oriented"

    def to_domain(self):
        return SimulationInfo(
            duration=self.duration,
            reference=self.reference,
            time_scale=self.time_scale,
            start_time=self.start_time,
            mode=self.mode,
        )


class ScenarioDatasetIn(InModel[ScenarioDataset]):
    name: NameStr
    # refer using namespace to statisfy sphinx autodoc
    type: domain_model.DatasetType | NameStr | None = None

    def to_domain(self):
        dataset_type = DatasetType(self.type) if isinstance(self.type, str) else self.type
        return ScenarioDataset(name=self.name, dataset_type=dataset_type)


class ScenarioDatasetOut(OutModel[ScenarioDataset]):
    name: str
    type: domain_model.DatasetType = Field(validation_alias="dataset_type")
    id: UUID


class ScenarioModelIn(InModel[ScenarioModel]):
    model_config = ConfigDict(extra="allow")
    name: NameStr
    type: NameStr | domain_model.ModelType

    def to_domain(self):
        return ScenarioModel(
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


class ShortScenarioOut(OutModel[Scenario]):
    id: UUID
    name: str
    display_name: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    status: ScenarioStatus
    has_updates: bool


class ScenarioOut(ShortScenarioOut):
    description: str
    epsg_code: int | None
    bounding_box: BoundingBoxField
    simulation_info: SimulationInfoInOut
    models: list[t.Annotated[ScenarioModelOut, BeforeValidator(ScenarioModelOut.from_domain)]]
    datasets: list[ScenarioDatasetOut]


class ScenarioListOut(OutModel[t.Sequence[Scenario]]):
    __envelope__ = "scenarios"
    scenarios: list[ShortScenarioOut]


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
    bounding_box: BoundingBoxField = None
    general: dict | None = None
    data: dict


class UpdateModelIn(InModel[UpdateModel]):
    name: NameStr
    type: NameStr | None = None

    def to_domain(self):
        return UpdateModel(
            name=self.name, type=ModelType(name=self.type) if self.type is not None else None
        )


class UpdateModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    type: t.Annotated[str, BeforeValidator(lambda v: v.name)]


class UpdateListOut(OutModel[t.Sequence[Update]]):
    __envelope__ = "updates"
    updates: list[ShortUpdateOut]


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
        file: pathlib.Path | t.BinaryIO,
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
        serializer.supported_file_type_or_raise(filetype)

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
        if isinstance(file, pathlib.Path):
            file.write_bytes(raw_data)
        else:
            file.write(raw_data)


class UpdateIn(InModel[Update]):
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
            be) read as a file of this type. If not given, or None, the filetype will be guessed
            from the filename (suffix)

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


class DatasetTypeListOut(OutModel[t.Sequence[DatasetType]]):
    __envelope__ = "dataset_types"
    dataset_types: list[DatasetTypeOut]


class DatasetTypeOut(OutModel[DatasetType]):
    id: UUID
    name: str
    format: DatasetFormat | None
    mimetype: str | None


class DatasetTypeInPartial(InModel):
    name: NameStr
    format: DatasetFormat | None
    mimetype: t.Annotated[str, Field(max_length=DATASET_TYPE_MIMETYPE_MAX_LENGTH)] | None = None

    def to_domain(self):
        return DatasetType(name=self.name, format=self.format, mimetype=self.mimetype)


class DatasetTypeIn(DatasetTypeInPartial):
    format: DatasetFormat  # type:ignore


class EntityTypeListOut(OutModel[t.Sequence[EntityType]]):
    __envelope__ = "entity_types"
    entity_types: list[EntityTypeOut]


class EntityTypeOut(OutModel[EntityType]):
    id: UUID
    name: str


class EntityTypeIn(InModel[EntityType]):
    name: NameStr

    def to_domain(self):
        return EntityType(name=self.name)


DataTypePrimitive = t.Literal["bool", "int", "float", "str"]


class DataTypeIn(InModel[DataType]):
    type: DataTypePrimitive
    unit_shape: list[int] = Field(default_factory=list)
    csr: bool = False

    def to_domain(self):
        primitives: dict[DataTypePrimitive, type] = {
            "bool": bool,
            "int": int,
            "float": float,
            "str": str,
        }

        return DataType(
            py_type=primitives[self.type], unit_shape=tuple(self.unit_shape), csr=self.csr
        )


class DataTypeOut(OutModel[DataType]):
    type: DataTypePrimitive
    unit_shape: list[int]
    csr: bool

    @classmethod
    def from_domain(cls, obj: DataType):
        primitives: dict[type, DataTypePrimitive] = {
            bool: "bool",
            int: "int",
            float: "float",
            str: "str",
        }
        return DataTypeOut(
            type=primitives[obj.py_type], unit_shape=list(obj.unit_shape), csr=obj.csr
        )


class AttributeTypeListOut(OutModel[t.Sequence[AttributeType]]):
    __envelope__ = "attribute_types"
    attribute_types: list[AttributeTypeOut]


class AttributeTypeOut(OutModel[AttributeType]):
    id: UUID
    name: str
    data_type: t.Annotated[DataTypeOut, BeforeValidator(DataTypeOut.from_domain)]
    unit: str
    description: str
    enum_name: str | None

    @classmethod
    def from_domain(cls, obj: AttributeType):
        return AttributeTypeOut(
            id=t.cast(UUID, obj.id),
            name=obj.name,
            data_type=obj.data_type,  # type: ignore
            unit=obj.unit,
            description=obj.description,
            enum_name=obj.enum_name,
        )


class AttributeTypeIn(InModel[AttributeType]):
    name: AttributeNameStr
    data_type: DataTypeIn
    unit: t.Annotated[str, Field(max_length=ATTRIBUTE_UNIT_MAX_LENGTH)] = ""
    description: t.Annotated[str, Field(max_length=ATTRIBUTE_DESCRIPTION_MAX_LENGTH)] = ""
    enum_name: (
        t.Annotated[
            str,
            Field(max_length=ATTRIBUTE_ENUM_NAME_MAX_LENGTH, pattern=re.compile(r"[a-z][a-z_]*")),
        ]
        | None
    ) = None

    def to_domain(self):
        return AttributeType(
            name=self.name,
            data_type=self.data_type.to_domain(),
            unit=self.unit,
            description=self.description,
            enum_name=self.enum_name,
        )


class ModelTypeListOut(OutModel[t.Sequence[ModelType]]):
    __envelope__ = "model_types"
    model_types: list[ModelTypeOut]


class ModelTypeIn(InModel[ModelType]):
    name: NameStr
    jsonschema: dict

    @field_validator("jsonschema", mode="after")
    @classmethod
    def _validate_jsonschema(cls, schema):
        try:
            # TODO: check that the schema does not contain malicious content, such as a bad regex
            movici_validator(schema).check_schema(schema)
        except SchemaError:
            raise ValueError("invalid schema") from None
        return schema

    def to_domain(self):
        return ModelType(name=self.name, jsonschema=self.jsonschema)


class ModelTypeOut(OutModel[ModelType]):
    id: UUID
    name: str
    jsonschema: dict


class DatasetSummaryOut(OutModel[DatasetSummary]):
    general: dict
    epsg_code: int | None
    bounding_box: BoundingBoxField
    entity_groups: t.Annotated[
        list[EntityGroupSummaryOut],
        BeforeValidator(lambda items: [EntityGroupSummaryOut.from_domain(i) for i in items]),
    ]
    count: int


class EntityGroupSummaryOut(OutModel[EntityGroupSummary]):
    name: str
    count: int
    attributes: t.Annotated[
        list[AttributeSummaryOut],
        BeforeValidator(lambda items: [AttributeSummaryOut.from_domain(i) for i in items]),
    ]


class AttributeSummaryOut(OutModel[AttributeSummary]):
    name: str
    data_type: t.Annotated[DataTypeOut, BeforeValidator(DataTypeOut.from_domain)]
    description: str
    enum_name: str | None
    unit: str
    min_val: bool | int | float | None
    max_val: bool | int | float | None


class OperationSuccess(BaseModel):
    id: UUID | str
    message: str
    result: t.Literal["ok"] = "ok"

    @classmethod
    def for_path_operation(cls, resource: str, id: UUID, verb: str):
        return OperationSuccess(id=id, message=f"{resource} {verb}")
