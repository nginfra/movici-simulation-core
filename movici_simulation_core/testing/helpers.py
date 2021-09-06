import typing as t

import numpy as np

from movici_simulation_core.data_tracker.property import PropertySpec, DataType, PropertyField


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


def dataset_dicts_equal(a, b):
    return not _dataset_dicts_equal_helper(a, b, {}, "")


def assert_dataset_dicts_equal(a, b):
    errors = _dataset_dicts_equal_helper(a, b, {}, "")
    if errors:
        raise AssertionError("\n".join(f"{k or '/'}: {v}" for k, v in errors.items()))


def _dataset_dicts_equal_helper(
    a: t.Union[dict, np.ndarray, list],
    b: t.Union[dict, np.ndarray, list],
    current_errors: t.Dict[str, str],
    current_path="",
):
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() == b.keys():
            for key in a.keys():
                _dataset_dicts_equal_helper(
                    a[key], b[key], current_errors, current_path=current_path + "/" + str(key)
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
        elif len(a) and isinstance(a[0], (list, dict)) and isinstance(b[0], (list, dict)):
            for idx, (i_a, i_b) in enumerate(zip(a, b)):
                _dataset_dicts_equal_helper(i_a, i_b, current_errors, current_path + f"[{idx}]")
        else:
            if not np.array_equal(a, b):
                current_errors[current_path] = "lists not equal"
    elif isinstance(a, (np.ndarray, list)) and isinstance(b, (np.ndarray, list)):
        if not np.array_equal(a, b):
            current_errors[current_path] = "arrays not equal"
    else:
        if not a == b:
            current_errors[current_path] = f"{a} and {b} differ"
    return current_errors
