import typing as t

import numpy as np

from .entity_groups import LineEntity, PointEntity, PolygonEntity

modality_link_entities = {
    "roads": "road_segment_entities",
    "waterways": "waterway_segment_entities",
    "tracks": "track_segment_entities",
    "passenger_tracks": "track_segment_entities",
    "cargo_tracks": "track_segment_entities",
}

supported_geometry_types = {
    "point": PointEntity,
    "line": LineEntity,
    "polygon": PolygonEntity,
}


def get_transport_info(model_config: t.Dict[str, t.Optional[t.List[str]]]) -> t.Tuple[str, str]:
    return_dataset_type = ""
    return_dataset = ""
    allowed_legacy_keys = 1

    if "modality" in model_config and "dataset" in model_config:
        return_dataset_type = model_config["modality"]
        return_datasets = model_config["dataset"]
        allowed_legacy_keys = 0

    legacy_keys = [key for key in ("roads", "waterways", "tracks") if model_config.get(key, None)]
    if len(legacy_keys) != allowed_legacy_keys:
        raise RuntimeError(
            "Supply either 'modality' and 'dataset' in the model config or exactly"
            " one of ['roads', 'waterways', 'tracks']"
        )
    if legacy_keys:
        return_dataset_type = legacy_keys[0]
        return_datasets = model_config[return_dataset_type]

    if isinstance(return_datasets, str):
        return_dataset = return_datasets
    elif isinstance(return_datasets, list):
        if len(return_datasets) != 1:
            raise RuntimeError("You can only have one dataset in config")

        return_dataset = return_datasets[0]
    else:
        raise RuntimeError(
            f"Cannot determine transport info for model {model_config.get('name', '<unknown>')}"
        )

    return return_dataset_type, return_dataset


def try_get_geometry_type(geometry_type):
    try:
        return supported_geometry_types[geometry_type]
    except KeyError:
        raise ValueError(
            f"models geometry_type must be one of {[k for k in supported_geometry_types.keys()]}"
        )


def find_y_in_x(x: np.ndarray, y: np.ndarray):
    """
    find position of y in x, adapted from https://stackoverflow.com/a/8251757
    """
    return np.searchsorted(x, y, sorter=np.argsort(x))


def safe_divide(numerator, denominator, fill_value):
    with np.errstate(divide="ignore", invalid="ignore"):
        rv = numerator / denominator
    rv[~np.isfinite(rv)] = fill_value
    return rv
