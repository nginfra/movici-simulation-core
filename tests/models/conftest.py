import dataclasses
import itertools
import json
import pytest
import shutil
import typing as t
from pathlib import Path
from movici_simulation_core.core import Model
from movici_simulation_core.core.schema import AttributeSchema

from movici_simulation_core.model_connector.init_data import (
    DirectoryInitDataHandler,
)
from movici_simulation_core.models.common.attributes import CommonAttributes
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.utils.moment import TimelineInfo


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
def global_timeline_info():
    return TimelineInfo(0, 1, 0)


@pytest.fixture
def global_schema(global_schema):
    global_schema.use(CommonAttributes)
    return global_schema


@pytest.fixture
def init_data_handler(tmp_path_factory):
    root = tmp_path_factory.mktemp("init_data_handler")
    return DirectoryInitDataHandler(root)


@pytest.fixture
def add_init_data(init_data_handler):
    root = init_data_handler.root

    def _add_init_data(name, data: t.Union[dict, str, Path]):
        if isinstance(data, dict):
            root.joinpath(f"{name}.json").write_text(json.dumps(data))
            return
        path = Path(data)
        if not path.is_file():
            raise ValueError(f"{data} is not a valid file")
        target = (root / name).with_suffix(path.suffix)
        shutil.copyfile(path, target)

    return _add_init_data


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
def railway_network_name():
    return "a_railway_network"


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
                "geometry.x": [0, 1],
                "geometry.y": [0, 1],
                "geometry.z": [1.2, 1.2],
                "geometry.polygon": [
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
                ],
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
                "geometry.linestring_3d": [
                    [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                    [[1.1, 1.0, 1.0], [1.05, 1.0, -1.0]],
                    [[0, 0, 0.0], [0.1, 0.0, -1.0], [1, 1, 1.0], [-0.9, 1, 1.0]],
                ],
                "shape.length": [1.4142, 2.0006, 5.3154],
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
                "geometry.polygon": [
                    [[0, 0], [2000, 0], [2000, 2000], [0, 2000], [0, 0]],
                    [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5], [0, 0]],
                ],
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
        ids: t.Iterable,
        attributes: t.Iterable,
        key_name: str,
    ) -> dict:
        if not isinstance(ids, t.Iterable):
            ids = [ids]
        entities = {"id": list(ids)}
        for key, attr, in [
            (key_name, attributes),
        ]:
            if attr is not None:
                if not isinstance(attr, t.Iterable):
                    attr = [attr for _ in ids]
                entities[key] = attr

        return entities

    return _factory


@pytest.fixture
def road_network_for_traffic(road_network_name):
    r"""
     /--------v
    0<===1<---2

    """
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
                "topology.from_node_id": [1, 0, 1, 0],
                "topology.to_node_id": [0, 2, 2, 1],
                "geometry.linestring_2d": [
                    [[97701, 434000], [97700, 434000]],
                    [[97700, 434000], [97702, 434000]],
                    [[97701, 434000], [97704, 434000], [97702, 434000]],
                    [[97700, 434000], [97701, 434000]],
                ],
                "transport.layout": [[1, 0, 0, 0], [1, 0, 0, 0], [0, 2, 0, 0], [0, 1, 0, 0]],
                "transport.max_speed": [2.7778, 6.9444, 27.7778, 2.7778],
                "transport.capacity.hours": [50, 100, 25, 10],
            },
            "transport_node_entities": {
                "id": [0, 1, 2],
                "reference": ["RN0", "RN1", "RN2"],
                "geometry.x": [97700, 97701, 97702],
                "geometry.y": [434000, 434000, 434000],
            },
            "virtual_node_entities": {
                "id": [10, 11, 12],
                "reference": ["VN1", "VN2", "VN3"],
                "geometry.x": [97700.1, 97701.1, 97702.1],
                "geometry.y": [434000, 434000, 434000],
            },
            "virtual_link_entities": {
                "id": [1000, 1001, 1002],
                "reference": ["VL1", "VL2", "VL3"],
                "topology.from_node_id": [10, 11, 12],
                "topology.to_node_id": [0, 1, 2],
                "geometry.linestring_2d": [
                    [[97700.1, 434000], [97700, 434000]],
                    [[97701.1, 434000], [97701, 434000]],
                    [[97702.1, 434000], [97702, 434000]],
                ],
            },
        },
    }


@pytest.fixture
def road_network_for_traffic_with_line3d(road_network_for_traffic):
    entity_data = road_network_for_traffic["data"]["road_segment_entities"]
    linestrings = entity_data["geometry.linestring_2d"]
    del entity_data["geometry.linestring_2d"]

    for linestring in linestrings:
        for point in linestring:
            point.append(0.0)

    entity_data["geometry.linestring_3d"] = linestrings

    return road_network_for_traffic


@pytest.fixture
def water_network_for_traffic(water_network_name, road_network_for_traffic):
    water_network = road_network_for_traffic
    water_network["name"] = water_network_name
    water_network["data"]["waterway_segment_entities"] = water_network["data"][
        "road_segment_entities"
    ]
    del water_network["data"]["road_segment_entities"]

    # Entity index 0 has no extras, 1 has a lock, 2 has a bridge and 3 is closed

    water_network["data"]["waterway_segment_entities"]["transport.capacity.hours"] = [
        -999,
        100,
        -999,
        -999,
    ]

    water_network["data"]["waterway_segment_entities"]["transport.additional_time"] = [0, 0, 1, 0]

    water_network["data"]["waterway_segment_entities"]["transport.max_speed"][-1] = 1e-6
    water_network["general"] = {
        "special": {"waterway_segment_entities..transport.capacity.hours": -999}
    }

    return water_network


@pytest.fixture
def railway_network_for_traffic(railway_network_name):
    r"""The railway network for traffic calculations is designed such that
     * traffic along common routes for different OD-pairs is stacked
     * there is an alternative route that is longer than the shortest path, which is not used for
       simple traffic assignment (wherein capacity is not a limiting factor due to the choice of
       vdf)

    (10) -> 0
             \-v /--> 4 -v
               2 ------> 3 <- (12)
    (11) -> 1 -^

    """
    coord_zero = [97700, 434000]

    @dataclasses.dataclass
    class Point:
        x: float
        y: float

    def __post_init__(self):
        self.x += coord_zero[0]
        self.y += coord_zero[1]

    point_0 = Point(0, 0)
    point_1 = Point(0, 2)
    point_2 = Point(1, 1)
    point_3 = Point(3, 1)
    point_4 = Point(2, 0)

    vn_0 = Point(0.1, 0)
    vn_1 = Point(0.1, 2)
    vn_2 = Point(3.1, 0)

    def linestring(points: t.Sequence[Point]):
        return [[point.x, point.y] for point in points]

    def geometry_x(points: t.Sequence[Point]):
        return [point.x for point in points]

    def geometry_y(points: t.Sequence[Point]):
        return [point.y for point in points]

    return {
        "version": 3,
        "name": railway_network_name,
        "type": "transport_network",
        "display_name": "",
        "epsg_code": 28992,
        "data": {
            "track_segment_entities": {
                "id": [101, 102, 103, 104, 105],
                "reference": ["TS101", "TS102", "TS103", "TS104", "TS105"],
                "topology.from_node_id": [0, 1, 2, 2, 4],
                "topology.to_node_id": [2, 2, 3, 4, 3],
                "geometry.linestring_2d": [
                    linestring([point_0, point_2]),
                    linestring([point_1, point_2]),
                    linestring([point_2, point_3]),
                    linestring([point_2, point_4]),
                    linestring([point_4, point_3]),
                ],
                "transport.layout": [[0, 0, 1, 0]] * 5,
                "transport.max_speed": [5] * 5,
                "transport.passenger_vehicle_max_speed": [2] * 5,
                "transport.cargo_vehicle_max_speed": [1] * 5,
                "transport.capacity.hours": [1] * 5,
            },
            "transport_node_entities": {
                "id": [0, 1, 2, 3, 4],
                "reference": ["TN0", "TN1", "TN2", "TN3", "TN4"],
                "geometry.x": geometry_x([point_0, point_1, point_2, point_3, point_4]),
                "geometry.y": geometry_y([point_0, point_1, point_2, point_3, point_4]),
            },
            "virtual_node_entities": {
                "id": [10, 11, 12],
                "reference": ["VN1", "VN2", "VN3"],
                "geometry.x": geometry_x([vn_0, vn_1, vn_2]),
                "geometry.y": geometry_y([vn_0, vn_1, vn_2]),
                "transport.passenger_vehicle_frequency": [
                    [0, 1, 1],
                    [1, 0, 1],
                    [1, 1, 0],
                ],
                "transport.passenger_vehicle_capacity": [1, 1, 1],
            },
            "virtual_link_entities": {
                "id": [1000, 1001, 1002],
                "reference": ["VL1", "VL2", "VL3"],
                "topology.from_node_id": [10, 11, 12],
                "topology.to_node_id": [0, 1, 3],
                "geometry.linestring_2d": [
                    linestring([vn_0, point_0]),
                    linestring([vn_1, point_1]),
                    linestring([vn_2, point_3]),
                ],
            },
        },
    }


@pytest.fixture
def create_model_tester(tmp_path_factory, init_data, global_schema):
    testers: t.List[ModelTester] = []
    counter = itertools.count()

    def _create(
        model_type: t.Type[Model],
        config,
        tmp_dir: Path = None,
        schema: AttributeSchema = None,
        **kwargs,
    ):
        model = model_type(config)
        if tmp_dir is None:
            tmp_dir = tmp_path_factory.mktemp(f"init_data_{next(counter)}")
        if schema is None:
            schema = global_schema

        tester = ModelTester(model, tmp_dir=tmp_dir, global_schema=schema, **kwargs)
        for name, dataset in init_data:
            tester.add_init_data(name, dataset)
        testers.append(tester)
        return tester

    yield _create

    for tester in testers:
        tester.close()
