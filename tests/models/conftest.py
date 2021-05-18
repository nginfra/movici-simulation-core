import collections
from typing import Iterable, Optional, Dict

import pytest


@pytest.fixture
def model_name():
    return "some_model"


@pytest.fixture
def init_data():
    return []


@pytest.fixture
def time_scale():
    return 1


@pytest.fixture
def config(
    model_config,
    init_data,
    time_scale,
):
    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 730,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture
def road_network_name():
    return "a_road_network"


@pytest.fixture
def water_network_name():
    return "a_water_network"


@pytest.fixture
def mv_network_name():
    return "an_mv_network"


@pytest.fixture
def overlap_dataset_name():
    return "an_overlap_dataset"


@pytest.fixture
def knotweed_dataset_name():
    return "a_knotweed_dataset"


@pytest.fixture
def maintenance_agenda_dataset_name():
    return "a_maintenance_agenda"


@pytest.fixture
def area_dataset_name():
    return "an_area_dataset"


def get_dataset(name, ds_type, data, **kwargs):
    ds = {
        "version": 3,
        "name": name,
        "type": ds_type,
        "display_name": "",
        "epsg_code": 28992,
        "data": data,
    }
    ds.update(kwargs)
    return ds


@pytest.fixture
def knotweed_dataset(knotweed_dataset_name):
    return get_dataset(
        name=knotweed_dataset_name,
        ds_type="knotweed",
        data={
            "knotweed_entities": {
                "point_properties": {
                    "position_x": [0, 1],
                    "position_y": [0, 1],
                    "position_z": [1.2, 1.2],
                },
                "shape_properties": {
                    "polygon": [
                        [
                            [0, 0],
                            [0, 1],
                            [1, 1],
                            [1, 0],
                            [0, 0],
                        ],
                        [
                            [1, 1],
                            [1, 2],
                            [2, 2],
                            [2, 1],
                            [1, 1],
                        ],
                    ]
                },
                "id": [0, 1],
                "knotweed.stem_density": [80.0, 100.0],
                "reference": ["Knotweed1", "Knotweed2"],
            }
        },
    )


@pytest.fixture
def road_network(road_network_name):
    return get_dataset(
        name=road_network_name,
        ds_type="random_type",
        data={
            "road_segment_entities": {
                "id": [1, 2, 3],
                "reference": ["Road1", "Road2", "Road3"],
                "shape_properties": {
                    "linestring_3d": [
                        [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                        [[1.1, 1.0, 1.0], [1.05, 1.0, -1.0]],
                        [[0, 0, 0.0], [0.1, 0.0, -1.0], [1, 1, 1.0], [-0.9, 1, 1.0]],
                    ]
                },
                "line_properties": {"length": [1.4142, 2.0006, 5.3154]},
            }
        },
    )


@pytest.fixture
def area_dataset(area_dataset_name):
    return get_dataset(
        name=area_dataset_name,
        ds_type="impact_indicator",
        data={
            "area_entities": {
                "id": [0, 2],
                "shape_properties": {
                    "polygon": [
                        [[0, 0], [2000, 0], [2000, 2000], [0, 2000], [0, 0]],
                        [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5], [0, 0]],
                    ]
                },
            }
        },
    )


@pytest.fixture
def overlap_dataset(overlap_dataset_name):
    return get_dataset(
        name=overlap_dataset_name,
        ds_type="random_type",
        data={"overlap_entities": {"id": list(range(1, 1000))}},
    )


@pytest.fixture
def get_entity_update():
    def _factory(
        ids: Iterable, properties: Iterable, key_name: str, component_name: Optional[str] = None
    ) -> Dict:
        if not isinstance(ids, collections.Iterable):
            ids = [ids]
        entities = {"id": list(ids)}
        for key, prop, component in [
            (key_name, properties, component_name),
        ]:
            if prop is not None:
                if not isinstance(prop, collections.Iterable):
                    prop = [prop for _ in ids]
                if component is None:
                    entities[key] = prop
                else:
                    if component not in entities:
                        entities[component] = {}
                    entities[component][key] = prop

        return entities

    return _factory


@pytest.fixture
def road_network_for_traffic(road_network_name):
    return {
        "version": 3,
        "name": road_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "data": {
            "road_segment_entities": {
                "id": [101, 102, 103, 104],
                "reference": ["RS1", "RS102", "RS103", "RS104"],
                "line_properties": {"from_node_id": [1, 0, 1, 0], "to_node_id": [0, 2, 2, 1]},
                "shape_properties": {
                    "linestring_2d": [
                        [[97701, 434000], [97700, 434000]],
                        [[97700, 434000], [97702, 434000]],
                        [[97701, 434000], [97704, 434000], [97702, 434000]],
                        [[97700, 434000], [97701, 434000]],
                    ]
                },
                "transport.layout": [[1, 0, 0, 0], [1, 0, 0, 0], [0, 2, 0, 0], [0, 1, 0, 0]],
                "transport.max_speed": [2.7778, 6.9444, 27.7778, 2.7778],
                "transport.capacity.hours": [50, 100, 25, 10],
            },
            "transport_node_entities": {
                "id": [0, 1, 2],
                "reference": ["RN0", "RN1", "RN2"],
                "point_properties": {
                    "position_x": [97700, 97701, 97702],
                    "position_y": [434000, 434000, 434000],
                },
            },
            "virtual_node_entities": {
                "id": [10, 11, 12],
                "reference": ["VN1", "VN2", "VN3"],
                "point_properties": {
                    "position_x": [97700.1, 97701.1, 97702.1],
                    "position_y": [434000, 434000, 434000],
                },
            },
            "virtual_link_entities": {
                "id": [1000, 1001, 1002],
                "reference": ["VL1", "VL2", "VL3"],
                "line_properties": {
                    "from_node_id": [10, 11, 12],
                    "to_node_id": [0, 1, 2],
                },
                "shape_properties": {
                    "linestring_2d": [
                        [[97700.1, 434000], [97700, 434000]],
                        [[97701.1, 434000], [97701, 434000]],
                        [[97702.1, 434000], [97702, 434000]],
                    ]
                },
            },
        },
    }


@pytest.fixture
def road_network_for_traffic_with_line3d(road_network_for_traffic):
    shape_properties = road_network_for_traffic["data"]["road_segment_entities"][
        "shape_properties"
    ]
    linestrings = shape_properties["linestring_2d"]
    del shape_properties["linestring_2d"]

    for linestring in linestrings:
        for point in linestring:
            point.append(0.0)

    shape_properties["linestring_3d"] = linestrings

    return road_network_for_traffic


@pytest.fixture
def water_network_for_traffic(water_network_name, road_network_for_traffic):
    water_network = road_network_for_traffic
    water_network["name"] = water_network_name
    water_network["data"]["waterway_segment_entities"] = water_network["data"][
        "road_segment_entities"
    ]
    del water_network["data"]["road_segment_entities"]
    return water_network
