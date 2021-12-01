import typing as t
from pathlib import Path

import numpy as np

from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import PropertySpec, DataType, PropertyField
from movici_simulation_core.data_tracker.state import TrackedState


def dataset_data_to_numpy(data: t.Union[dict, np.ndarray, list]):
    if isinstance(data, dict):
        if "data" in data:
            return data
        return {key: dataset_data_to_numpy(val) for key, val in data.items()}
    return {"data": np.asarray(data)}


def get_property(name="prop", component=None, **kwargs):
    spec = dict(
        spec=PropertySpec(name=name, component=component, data_type=DataType(int, (), False))
    )
    return PropertyField(**{**spec, **kwargs})


T = t.TypeVar("T", bound=EntityGroup)


def create_entity_group_with_data(entity_type: t.Union[T, t.Type[T]], data: dict) -> T:
    DATASET = "dummy"
    state = TrackedState()
    entity_group = state.register_entity_group(DATASET, entity_type)
    schema = AttributeSchema(prop.spec for prop in entity_type.all_properties().values())
    state.receive_update(
        EntityInitDataFormat(schema).load_json({DATASET: {entity_group.__entity_name__: data}})
    )
    return entity_group


def compare_dataset_dicts(a, b, rtol=1e-5, atol=1e-8):
    return _dataset_dicts_equal_helper(a, b, {}, rtol=rtol, atol=atol)


def dataset_dicts_equal(a, b, rtol=1e-5, atol=1e-8):
    return not _dataset_dicts_equal_helper(a, b, {}, rtol=rtol, atol=atol)


def assert_dataset_dicts_equal(a, b, rtol=1e-5, atol=1e-8):
    errors = _dataset_dicts_equal_helper(a, b, {}, rtol=rtol, atol=atol)
    if errors:
        raise AssertionError("\n".join(f"{k or '/'}: {v}" for k, v in errors.items()))


def _dataset_dicts_equal_helper(
    a: t.Union[dict, np.ndarray, list],
    b: t.Union[dict, np.ndarray, list],
    current_errors: t.Dict[str, str],
    current_path="",
    rtol=1e-5,
    atol=1e-8,
):
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() == b.keys():
            for key in a.keys():
                _dataset_dicts_equal_helper(
                    a[key],
                    b[key],
                    current_errors,
                    current_path=current_path + "/" + str(key),
                    rtol=rtol,
                    atol=atol,
                )
        else:
            missing_keys = a.keys() - b.keys()
            extra_keys = b.keys() - a.keys()
            messages = []
            if missing_keys:
                messages.append(f"missing keys: {missing_keys}")
            if extra_keys:
                messages.append(f"extra keys: {extra_keys}")
            current_errors[current_path] = ";".join(messages)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            current_errors[current_path] = f"lists not of equal length {len(a)} vs {len(b)}"
        for idx, (i_a, i_b) in enumerate(zip(a, b)):
            _dataset_dicts_equal_helper(
                i_a, i_b, current_errors, current_path + f"[{idx}]", rtol=rtol, atol=atol
            )

    elif isinstance(a, (np.ndarray, list)) and isinstance(b, (np.ndarray, list)):
        if np.issubdtype(getattr(a, "dtype") or getattr(b, "dtype"), float) and not np.allclose(
            a, b, rtol=rtol, atol=atol, equal_nan=True
        ):
            current_errors[current_path] = f"{a} not equal to {b}"

        if not np.array_equal(a, b):
            current_errors[current_path] = f"{a} not equal to {b}"
    elif a is not None and b is not None and (isinstance(a, float) or isinstance(b, float)):
        if not np.isclose(a, b, rtol=rtol, atol=atol):
            current_errors[current_path] = f"{a} not close to {b}"
    else:
        if not a == b:
            current_errors[current_path] = f"{a} not equal to {b}"

    return current_errors


def list_dir(path: Path):
    return [file.name for file in path.iterdir()]


def data_mask_compare(data_mask):
    if isinstance(data_mask, dict):
        return {k: data_mask_compare(v) for k, v in data_mask.items()}
    elif isinstance(data_mask, list):
        return set(data_mask)
    return data_mask
