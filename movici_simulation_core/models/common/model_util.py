import typing as t

from .entities import PointEntity, LineEntity, PolygonEntity

dataset_to_segments = {
    "roads": "road_segment_entities",
    "waterways": "waterway_segment_entities",
    "tracks": "track_segment_entities",
}

supported_geometry_types = {
    "point": PointEntity,
    "line": LineEntity,
    "polygon": PolygonEntity,
}


def get_transport_type(model_config: t.Dict[str, t.Optional[t.List[str]]]) -> str:
    return_dataset_type = ""
    dataset_count = 0

    for dataset_type in ["roads", "waterways", "tracks"]:
        dataset_name_list = model_config.get(dataset_type, [])
        if dataset_name_list:
            if len(dataset_name_list) > 1:
                raise RuntimeError("You can only have one dataset in config")
            return_dataset_type = dataset_type
            dataset_count += 1

    if dataset_count != 1:
        raise RuntimeError("There should be exactly one of [roads, waterways, tracks] in config")

    return return_dataset_type


def try_get_geometry_type(geometry_type):
    try:
        return supported_geometry_types[geometry_type]
    except KeyError:
        raise ValueError(
            f"models geometry_type must be one of {[k for k in supported_geometry_types.keys()]}"
        )
