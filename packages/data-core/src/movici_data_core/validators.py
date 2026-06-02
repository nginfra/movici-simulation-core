import dataclasses
import typing as t
from uuid import UUID

from movici_data_core.domain_model import (
    AttributeType,
    EntityType,
    ModelType,
    ScenarioDataset,
    ScenarioModel,
)
from movici_data_core.exceptions import MoviciValidationError
from movici_simulation_core.validate import MoviciTypeLookup, ensure_schema, validate_and_process


@dataclasses.dataclass
class ModelConfigValidator:
    attribute_types: dict[str, AttributeType] = dataclasses.field(default_factory=dict)
    entity_types: dict[str, EntityType] = dataclasses.field(default_factory=dict)
    datasets: dict[str, ScenarioDataset] | None = None
    model_types: dict[str, ModelType] | None = None
    dataset_types_by_datasets: dict[str, str] | None = dataclasses.field(init=False)

    def __post_init__(self):
        self.dataset_types_by_datasets = (
            {ds.name: ds.type for ds in self.datasets.values()} if self.datasets else None
        )

    @classmethod
    def from_list_data(
        cls,
        attribute_types: t.Sequence[AttributeType],
        entity_types: t.Sequence[EntityType],
        datasets: t.Sequence[ScenarioDataset] | None = None,
    ):
        return cls(
            attribute_types={attr.name: attr for attr in attribute_types},
            entity_types={et.name: et for et in entity_types},
            datasets={ds.name: ds for ds in datasets} if datasets is not None else None,
        )

    # TODO: Once a Scenario contains ScenarioDatasets and ScenarioModels, this method can take
    # the scenario as an input argument
    def for_scenario(
        self, datasets: t.Sequence[ScenarioDataset], model_types: t.Sequence[ModelType]
    ):
        return dataclasses.replace(
            self,
            datasets={ds.name: ds for ds in datasets},
            model_types={mt.name: mt for mt in model_types},
        )

    def validated_model_type(self, config: dict):
        assert self.model_types is not None

        if "type" not in config:
            raise MoviciValidationError("type is a required field")

        model_type = config["type"]
        if not isinstance(model_type, str):
            raise MoviciValidationError("must be string", path="type")

        if model_type not in self.model_types:
            raise MoviciValidationError(f"invalid model_type {model_type}", path="type")

        return self.model_types[model_type]

    @property
    def lookup(self):
        return MoviciTypeLookup(
            attribute_types=self.attribute_types.keys(),
            entity_types=self.entity_types.keys(),
            datasets=self.dataset_types_by_datasets,
        )

    def process_model_configs(self, configs: list[dict]) -> list[ScenarioModel]:
        assert self.model_types is not None
        assert self.datasets is not None

        errors: list[MoviciValidationError] = []
        result: list[ScenarioModel] = []

        for idx, config in enumerate(configs):
            try:
                model_type = self.validated_model_type(config)
                result.append(self.parse_and_validate_model_config(config, model_type))
            except MoviciValidationError as e:
                errors.append(MoviciValidationError.from_errors(e, path=str(idx)))
        if errors:
            raise MoviciValidationError.from_errors(errors)
        return result

    def parse_and_validate_model_config(
        self, config: dict, model_type: ModelType
    ) -> ScenarioModel:
        if "name" not in config:
            raise MoviciValidationError("name is a required field")

        name = config["name"]
        if not isinstance(name, str):
            raise MoviciValidationError("must be string", path="name")

        refs, errors = validate_and_process(
            config,
            schema=ensure_schema(model_type.jsonschema),
            lookup=self.lookup,
            return_errors=True,
        )
        if not errors:
            return ScenarioModel(name, type=model_type, config=config, references=refs)
        raise MoviciValidationError.from_errors(errors)

    def iter_scenario_model_references(
        self, id: UUID, scenario_model: ScenarioModel
    ) -> t.Iterable[dict]:
        for ref in scenario_model.references:
            ref_data = {
                "scenario_model_id": id,
                "path": ref.json_path,
            }
            if ref.movici_type == "attribute":
                ref_data["attribute_type_id"] = self.attribute_types[ref.value].id
            elif ref.movici_type == "entityGroup":
                ref_data["entity_type_id"] = self.entity_types[ref.value].id
            elif ref.movici_type == "dataset":
                ref_data["dataset_id"] = self.datasets[ref.value].id if self.datasets else None
            yield ref_data
