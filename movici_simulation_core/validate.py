from __future__ import annotations

import dataclasses
import json
import re
import typing as t
from pathlib import Path

from jsonschema import exceptions, validators

import movici_simulation_core.core.schema as schema


class MoviciTypeReport(exceptions.ValidationError):
    """Indicates the existence of a ``movici.type`` field in the instance. By deriving from
    ``exceptions.ValidationError``, we hook into the existing ``jsonschema`` code that sets the
    location of the fields. In our own code we process and drop these "errors" so that they are not
    raised as actual errors
    """

    def __init__(self, movici_type: str, instance: str) -> None:
        self.movici_type = movici_type
        super().__init__(message=f"<{movici_type}>{instance}", instance=instance)

    def asinfo(
        self,
    ):
        return MoviciDataRefInfo(path=self.path, movici_type=self.movici_type, value=self.instance)


def movici_dataset_type(validator, ds_type, instance, schema):
    if not validator.is_type(instance, "string"):
        return

    if not (movici_type := schema.get("movici.type")) == "dataset":
        return

    # In case the instance is not a valid dataset, there is no need to also valid its
    # (hypothetical) dataset type
    if validator.validate_movici_type(instance, movici_type) is not None:
        return

    if not validator.has_dataset_type(instance, ds_type):
        yield exceptions.ValidationError(f"dataset '{instance}' is not of type '{ds_type}'")


def movici_type(validator, movici_type, instance, schema):
    if not validator.is_type(instance, "string"):
        return
    if error := validator.validate_movici_type(instance, movici_type):
        yield exceptions.ValidationError(error)
    yield MoviciTypeReport(movici_type, instance)


# The following functions ``anyOf`` and ``oneOf`` are adapted from ``jsonschema._validators``


def anyOf(validator, anyOf, instance, schema):
    all_errors = []

    for index, subschema in enumerate(anyOf):
        reps, errs = extract_reports(validator.descend(instance, subschema, schema_path=index))
        if not errs:
            yield from reps
            break
        all_errors.extend(errs)
    else:
        yield exceptions.ValidationError(
            f"{instance!r} is not valid under any of the given schemas",
            context=all_errors,
        )


def oneOf(validator, oneOf, instance, schema):
    subschemas = enumerate(oneOf)
    all_errors = []
    has_error = False
    reports = []
    for index, subschema in subschemas:
        reports, errs = extract_reports(validator.descend(instance, subschema, schema_path=index))
        if not errs:
            first_valid = subschema
            break
        all_errors.extend(errs)
    else:
        has_error = True
        yield exceptions.ValidationError(
            f"{instance!r} is not valid under any of the given schemas",
            context=all_errors,
        )

    more_valid = [
        each for _, each in subschemas if validator.evolve(schema=each).is_valid(instance)
    ]
    if more_valid:
        has_error = True

        more_valid.append(first_valid)
        reprs = ", ".join(repr(schema) for schema in more_valid)
        yield exceptions.ValidationError(f"{instance!r} is valid under each of {reprs}")

    if not has_error:
        yield from reports


def extract_reports(errors):
    reports, real_errors = [], []
    for err in errors:
        (reports if isinstance(err, MoviciTypeReport) else real_errors).append(err)
    return reports, real_errors


class MoviciTypeLookup:
    """class for looking up wether a specific dataset, entity_group, attribute exists or whether
    a dataset is of a specific type. Used alongside ``validate_and_process``. This class
    can be subclassed to provide custom logic for determining whether these objects exist
    """

    def dataset(self, dataset_name) -> bool:
        raise True

    def entity_group(self, entity_type) -> bool:
        raise True

    def attribute(self, attribute_type) -> bool:
        raise True

    def dataset_type(self, dataset_name, required_type) -> bool:
        raise True


class FromDictLookup(MoviciTypeLookup):
    def __init__(
        self,
        datasets: t.Optional[t.List[dict]] = None,
        entity_types: t.Optional[list] = None,
        attribute_types: t.Optional[list] = None,
        validate_dataset_types: bool = True,
    ) -> None:

        self.datasets = self.entity_types = self.attribute_types = None
        if datasets is not None:
            self.datasets = {
                ds["name"]: (ds["type"] if validate_dataset_types else None) for ds in datasets
            }
        if entity_types is not None:
            self.entity_types = set(entity_types)
        if attribute_types is not None:
            self.attribute_types = {e["name"] for e in attribute_types}

    def dataset(self, dataset_name):
        return self.datasets is None or dataset_name in self.datasets

    def entity_group(self, entity_type):
        return self.entity_types is None or entity_type in self.entity_types

    def attribute(self, attribute_type):
        return self.attribute_types is None or attribute_type in self.attribute_types

    def dataset_type(self, dataset_name, required_type):
        if self.datasets is None:
            return True
        try:
            return self.datasets[dataset_name] in (None, required_type)
        except KeyError:
            return False


class AttributeSchemaLookup(MoviciTypeLookup):
    def __init__(
        self,
        dataset_names: t.Optional[t.Sequence[str]] = None,
        schema: t.Optional[schema.AttributeSchema] = None,
    ):
        self.dataset_names = set(dataset_names) if dataset_names is not None else None
        self.schema = schema

    def dataset(self, dataset_name):
        return self.dataset_names is None or dataset_name in self.dataset_names

    def attribute(self, attribute_type):
        return self.schema is None or attribute_type in self.schema.attributes


def validate_and_process(
    instance: t.Any, schema: dict, lookup: MoviciTypeLookup = FromDictLookup(), return_errors=False
) -> t.Union[
    t.List[MoviciDataRefInfo],
    t.Tuple[t.List[MoviciDataRefInfo], t.List[exceptions.ValidationError]],
]:
    r"""Extension of ``jsonschema.validators.validate`` that strips out and processes
    ``MoviciTypeReport``\s
    """

    cls = movici_validator(schema, lookup=lookup)
    cls.check_schema(schema)
    validator = cls(schema)

    data_refs = []
    errors = []
    for candidate in validator.iter_errors(instance):
        if isinstance(candidate, MoviciTypeReport):
            data_refs.append(candidate.asinfo())
        else:
            errors.append(candidate)
    if return_errors:
        return data_refs, errors

    error = exceptions.best_match(errors)
    if error is not None:
        raise error
    return data_refs


def _extract_reports_from_error(
    error: exceptions.ValidationError,
) -> t.Tuple[MoviciTypeReport, t.Optional[exceptions.ValidationError]]:
    if isinstance(error, MoviciTypeReport):
        return [error], None

    # ValidationErrors may either be a single error, or a container of errors (in case of anyOf,
    # oneof, etc) kept in ValidationError.context. We filter out MoviciTypeReports from the real
    # ValidationErrors. If there no real errors left, we drop the container sinces it's no longer
    # an error. Otherwise we keep it.

    if not error.context:
        return [], error

    reports = []
    real_errors = []

    for candidate in error.context:
        if isinstance(candidate, MoviciTypeReport):
            reports.append(candidate)
            continue
        elif candidate.context:
            reports, candidate = _extract_reports_from_error(candidate)
            reports.extend(reports)

        if candidate is not None:
            real_errors.append(candidate)

    if real_errors:
        error.context = real_errors
    else:
        error = None
    return reports, error


def movici_validator(schema, lookup: MoviciTypeLookup = FromDictLookup()):
    BaseValidator = validators.extend(
        validators.validator_for(schema, default=validators.Draft7Validator),
        {
            "oneOf": oneOf,
            "anyOf": anyOf,
            "movici.datasetType": movici_dataset_type,
            "movici.type": movici_type,
        },
    )

    class MoviciValidator(BaseValidator):
        def validate_movici_type(self, instance, movici_type):
            if movici_type == "dataset" and not lookup.dataset(instance):
                return f"dataset '{instance}' is not available in the scenario"
            if movici_type == "entityGroup" and not lookup.entity_group(instance):
                return f"Entity type '{instance}' does not exist"
            if movici_type == "attribute" and not lookup.attribute(instance):
                return f"Attribute '{instance}' does not exist"

        def has_dataset_type(self, instance: str, dataset_type: str):
            return lookup.dataset_type(instance, dataset_type)

    return MoviciValidator


@dataclasses.dataclass
class MoviciDataRefInfo:
    path: t.Tuple[t.Union[str, int], ...]
    movici_type: t.Literal["dataset", "entityGroup", "attribute"]
    value: str

    def __post_init__(self):
        if isinstance(self.path, tuple):
            return
        if isinstance(self.path, str):
            self.path = self._parse_json_path(self.path)
        elif isinstance(self.path, t.Sequence):
            self.path = tuple(self.path)

    def set_value(self, obj):
        self._set_value(obj, self.value)

    def unset_value(self, obj):
        self._set_value(obj, None)

    def _set_value(self, obj, val):
        for i, p in enumerate(self.path):
            if i == len(self.path) - 1:
                obj[p] = val
                return
            obj = obj[p]

    @property
    def json_path(self):
        rv = "$"
        for path in self.path:
            if isinstance(path, str):
                rv += "." + path
            elif isinstance(path, int):
                rv += f"[{path}]"
            else:
                raise ValueError(f"{path} is not a valid path identifier")
        return rv

    @staticmethod
    def _parse_json_path(path: str) -> t.Tuple[t.Union[str, int], ...]:
        rv = []
        root = re.compile(r"^(?P<tok>\$)(?P<tail>.*)$")
        prop = re.compile(r"^.(?P<tok>[A-Za-z_][A-Za-z0-9_]*)(?P<tail>.*)$")
        indx = re.compile(r"^\[(?P<tok>[0-9]+)\](?P<tail>.*)$")
        if not (match := root.match(path)):
            raise ValueError("Path must start with $")
        path = match.group("tail")

        while path:
            if match := prop.match(path):
                rv.append(match.group("tok"))
            elif match := indx.match(path):
                rv.append(int(match.group("tok")))
            else:
                raise ValueError(f"Invalid syntax '{path[:10]}'")
            path = match.group("tail")
        return tuple(rv)


class ConfigVersion(t.TypedDict, total=False):
    schema: dict
    convert_from: t.Dict[str, t.Callable[[dict], dict]]


def ensure_valid_config(
    config: dict,
    target_version: str,
    versions: t.Dict[str, ConfigVersion],
    add_name_and_type=True,
):
    try:
        config = json.loads(json.dumps(config))
    except (TypeError, json.JSONDecodeError):
        raise TypeError(f"config {config} is not a valid JSON-encodable object")

    version = versions[target_version]
    schema = ensure_schema(version["schema"], add_name_and_type)
    errors = get_validation_errors(config, schema)

    if not errors:
        return config

    for ver, converter in version.get("convert_from", {}).items():
        legacy_version = versions[ver]
        schema = ensure_schema(legacy_version["schema"])
        errs = get_validation_errors(config, schema)
        if not errs:
            return converter(config)

    raise (exceptions.best_match(errors))


def ensure_schema(schema_identifier: t.Union[dict, str, Path], add_name_and_type=True):
    if isinstance(schema_identifier, dict):
        schema = schema_identifier
    else:
        schema = json.loads(Path(schema_identifier).read_text())
    if add_name_and_type:
        schema["properties"]["name"] = {"type": "string"}
        schema["properties"]["type"] = {"type": "string"}
    return schema


def get_validation_errors(config, schema):
    return validate_and_process(config, schema, return_errors=True)[1]
