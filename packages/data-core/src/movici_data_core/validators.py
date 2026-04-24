import dataclasses
import typing as t

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
    attribute_types: dict[str, AttributeType]
    entity_types: dict[str, EntityType]
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

    def for_scenario(
        self, datasets: t.Sequence[ScenarioDataset], model_types: t.Sequence[ModelType]
    ):
        return dataclasses.replace(
            self,
            datasets={ds.name: ds for ds in datasets},
            model_types={mt.name: mt for mt in model_types},
        )

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
