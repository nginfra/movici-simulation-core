import collections
from typing import Dict, Iterable, Optional

import pytest


@pytest.fixture
def maintenance_agenda(maintenance_agenda_dataset_name):
    return {
        "version": 3,
        "name": maintenance_agenda_dataset_name,
        "type": "maintenance_agenda",
        "display_name": "Test Maintenance Agenda",
        "general": {"enum": {"maintenance_job_entities": {"type": ["replacement"]}}},
        "data": {
            "maintenance_job_entities": {
                "maintenance.window_begin.date": ["2020-01-01", "2020-02-01"],
                "maintenance.window_end.date": ["2020-01-10", "2020-02-10"],
                "maintenance.job_begin.date": ["2020-03-01", "2020-04-01"],
                "maintenance.job_end.date": ["2020-04-01", "2020-04-02"],
                "maintenance.job_duration.days": [200, 40],
                "id": [0, 1],
                "type": [0, 0],
                "connection_properties": {
                    "to_dataset_type": ["road_network", "mv_network"],
                    "to_dataset": ["a_road_network", "an_mv_network"],
                    "to_references": [["100"], ["500", "501"]],
                },
                "reference": ["1", "2"],
            }
        },
    }


@pytest.fixture
def mv_network_name():
    return "an_mv_network"


@pytest.fixture
def mv_network(mv_network_name):
    return {
        "version": 3,
        "name": mv_network_name,
        "type": "mv_network",
        "display_name": "",
        "epsg_code": 28992,
        "general": {"enum": {"label": ["distribution", "industrial"]}},
        "data": {
            "electrical_node_entities": {
                "id": [0, 2, 4, 6, 8],
                "reference": ["499", "500", "501", "502", "503"],
                "labels": [[1], [0], [0], [0], [0]],
                "point_properties": {
                    "position_x": [1.5, 0.5, 0.5, 1.5, 1.5],
                    "position_y": [0.4, 0.5, 1.5, 1.5, 0.5],
                    "position_z": [0.0, 0.0, None, None, 0.0],
                },
            },
            "electrical_load_entities": {
                "id": [20, 10, 30, 40, 15],
                "oneside_element_properties": {"node_id": [4, 2, 6, 8, 0]},
                "operation_status_properties": {
                    "is_working_properly": [True, True, True, True, True]
                },
            },
        },
    }


@pytest.fixture
def road_network_name():
    return "a_road_network"


@pytest.fixture
def road_network(road_network_name):
    return {
        "version": 3,
        "name": road_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {
            "road_segment_entities": {
                "id": [1, 2, 3],
                "reference": ["100", "101", "102"],
                "shape_properties": {
                    "linestring_3d": [
                        [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                        [[1.6, 0.5, 1.0], [1.5, 0.5, -1.0]],
                        [[-0.5, 0.5, 0.0], [0.5, 0.5, -1.0], [1.5, 0.5, 1.0], [2.5, 0.5, 1.0]],
                    ]
                },
            }
        },
    }


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
