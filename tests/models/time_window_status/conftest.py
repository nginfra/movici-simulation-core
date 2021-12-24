import pytest

from movici_simulation_core.core.schema import AttributeSchema, DataType, AttributeSpec
from ..conftest import get_dataset


@pytest.fixture
def global_schema(global_schema: AttributeSchema):
    global_schema.add_attributes(
        [
            AttributeSpec("begin", DataType(str)),
            AttributeSpec("end", DataType(str)),
            AttributeSpec("job_begin", DataType(str)),
            AttributeSpec("job_end", DataType(str)),
            AttributeSpec("status", DataType(bool)),
        ]
    )
    return global_schema


@pytest.fixture
def maintenance_agenda(maintenance_agenda_dataset_name):
    return {
        "version": 3,
        "name": maintenance_agenda_dataset_name,
        "type": "maintenance_agenda",
        "display_name": "Test Maintenance Agenda",
        "data": {
            "maintenance_job_entities": {
                "begin": ["2020-01-01", "2020-02-01"],
                "end": ["2020-01-10", "2020-02-10"],
                "job_begin": ["2020-03-01", "2020-04-01"],
                "job_end": ["2020-04-01", "2020-04-02"],
                "id": [0, 1],
                "connection.to_dataset": ["a_road_network", "an_mv_network"],
                "connection.to_references": [["100"], ["500", "501"]],
                "reference": ["1", "2"],
            }
        },
    }


@pytest.fixture
def mv_network(mv_network_name):
    return get_dataset(
        name=mv_network_name,
        ds_type="mv_network",
        general={"enum": {"label": ["distribution", "industrial"]}},
        data={
            "electrical_node_entities": {
                "id": [0, 2, 4, 6, 8],
                "reference": ["499", "500", "501", "502", "503"],
                "labels": [[1], [0], [0], [0], [0]],
                "geometry.x": [1.5, 0.5, 0.5, 1.5, 1.5],
                "geometry.y": [0.4, 0.5, 1.5, 1.5, 0.5],
                "geometry.z": [0.0, 0.0, None, None, 0.0],
            },
            "electrical_load_entities": {
                "id": [20, 10, 30, 40, 15],
                "topology.node_id": [4, 2, 6, 8, 0],
                "operational.is_working_properly": [True, True, True, True, True],
            },
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
                "reference": ["100", "101", "102"],
                "geometry.linestring_3d": [
                    [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                    [[1.6, 0.5, 1.0], [1.5, 0.5, -1.0]],
                    [[-0.5, 0.5, 0.0], [0.5, 0.5, -1.0], [1.5, 0.5, 1.0], [2.5, 0.5, 1.0]],
                ],
            }
        },
    )
