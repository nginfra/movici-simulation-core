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
                    a[key], b[key], current_errors, current_path=current_path + "/" + key
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

    elif isinstance(a, (np.ndarray, list)) and isinstance(b, (np.ndarray, list)):
        if not np.array_equal(a, b):
            current_errors[current_path] = "arrays not equal"
    else:
        current_errors[current_path] = f"incompatible types {type(a)} and {type(b)}"
    return current_errors
