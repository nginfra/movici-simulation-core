import functools
from jsonschema import Draft7Validator


def model_config_validator(model_schema: dict):
    json_schema = Draft7Validator(assemble_json_schema(model_schema))

    def _validate(model_config):
        json_schema.validate(model_config)
        return True

    return _validate


def assemble_json_schema(model_schema: dict):
    json_schema = {"type": "object", "properties": {}}
    json_schema.update(model_schema["schema"])
    json_schema["properties"].update(
        {
            "type": {"type": "string"},
            "name": {"type": "string"},
        }
    )
    if name := model_schema.get("name"):
        json_schema["properties"]["type"]["pattern"] = rf"^{name}$"
    for entity_category in model_schema.get("entity_categories", []):
        add_entity_category(json_schema, entity_category)
    for dataset_category in model_schema.get("dataset_categories", []):
        add_dataset_category(json_schema, dataset_category)
    if model_schema.get("strict_validation"):
        json_schema["additionalProperties"] = False
    return json_schema


def _add_category(entry_factory):
    @functools.wraps(entry_factory)
    def _inner(schema: dict, category: dict):
        working_copy = category.copy()
        entry = entry_factory()
        name = working_copy.pop("name")
        working_copy.pop("type", None)
        required = working_copy.pop("required", False)
        if working_copy.pop("require_one", False):
            required = True
            entry.update(dict(minItems=1, maxItems=1))
        if required:
            schema.setdefault("required", []).append(name)
        entry.update(working_copy)
        schema["properties"][name] = entry

    return _inner


add_dataset_category = _add_category(
    lambda: {
        "type": "array",
        "items": {"type": "string", "minItems": 1, "maxItems": 1},
    }
)
add_entity_category = _add_category(
    lambda: {
        "type": "array",
        "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "string"}},
    }
)
