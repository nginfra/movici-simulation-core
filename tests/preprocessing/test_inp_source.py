"""Tests for INPSource DataSource."""

import textwrap

import pytest

from movici_simulation_core.preprocessing.data_sources import INPSource
from movici_simulation_core.preprocessing.dataset_creator import (
    AttributeDataLoading,
    DatasetCreator,
    IDGeneration,
    IDLinking,
    SourcesSetup,
)

MINIMAL_INP = textwrap.dedent("""\
    [TITLE]
    Test Network

    [JUNCTIONS]
    ;ID  Elev  Demand  Pattern
     J1  100   10
     J2  90    20

    [RESERVOIRS]
    ;ID  Head  Pattern
     R1  200

    [TANKS]
    ;ID  Elevation  InitLevel  MinLevel  MaxLevel  Diameter  MinVol  VolCurve  Overflow
     T1  150        10         0         20        50        0

    [PIPES]
    ;ID  Node1  Node2  Length  Diameter  Roughness  MinorLoss  Status
     P1  J1     J2     1000    300       100        0          Open
     P2  R1     J1     500     400       100        0          Open

    [PUMPS]
    ;ID  Node1  Node2  Parameters
     PU1 T1     J2     POWER 50

    [VALVES]
    ;ID  Node1  Node2  Diameter  Type  Setting  MinorLoss

    [OPTIONS]
    Units  LPS
    Headloss  H-W

    [COORDINATES]
    ;Node  X-Coord  Y-Coord
     J1    10.0     20.0
     J2    30.0     20.0
     R1    0.0      20.0
     T1    20.0     40.0

    [END]
""")


@pytest.fixture
def inp_file(tmp_path):
    path = tmp_path / "test_network.inp"
    path.write_text(MINIMAL_INP)
    yield path
    INPSource._model_cache.clear()


class TestINPSource:
    def test_junction_count(self, inp_file):
        source = INPSource(inp_file, "junctions")
        assert len(source) == 2

    def test_tank_count(self, inp_file):
        source = INPSource(inp_file, "tanks")
        assert len(source) == 1

    def test_reservoir_count(self, inp_file):
        source = INPSource(inp_file, "reservoirs")
        assert len(source) == 1

    def test_pipe_count(self, inp_file):
        source = INPSource(inp_file, "pipes")
        assert len(source) == 2

    def test_pump_count(self, inp_file):
        source = INPSource(inp_file, "pumps")
        assert len(source) == 1

    def test_valve_count(self, inp_file):
        source = INPSource(inp_file, "valves")
        assert len(source) == 0

    def test_junction_names(self, inp_file):
        source = INPSource(inp_file, "junctions")
        assert source.get_attribute("name") == ["J1", "J2"]

    def test_junction_elevation(self, inp_file):
        source = INPSource(inp_file, "junctions")
        # LPS units: elevation in meters, WNTR keeps as-is
        assert source.get_attribute("elevation") == [100.0, 90.0]

    def test_junction_base_demand(self, inp_file):
        source = INPSource(inp_file, "junctions")
        demands = source.get_attribute("base_demand")
        # LPS units: WNTR converts LPS → m³/s (÷1000)
        assert demands == pytest.approx([0.01, 0.02], rel=1e-6)

    def test_tank_attributes(self, inp_file):
        source = INPSource(inp_file, "tanks")
        assert source.get_attribute("name") == ["T1"]
        assert source.get_attribute("elevation") == [150.0]
        assert source.get_attribute("init_level") == [10.0]
        assert source.get_attribute("min_level") == [0.0]
        assert source.get_attribute("max_level") == [20.0]

    def test_reservoir_head(self, inp_file):
        source = INPSource(inp_file, "reservoirs")
        assert source.get_attribute("name") == ["R1"]
        assert source.get_attribute("base_head") == [200.0]

    def test_pipe_topology(self, inp_file):
        source = INPSource(inp_file, "pipes")
        assert source.get_attribute("start_node_name") == ["J1", "R1"]
        assert source.get_attribute("end_node_name") == ["J2", "J1"]

    def test_pipe_attributes(self, inp_file):
        source = INPSource(inp_file, "pipes")
        assert source.get_attribute("length") == [1000.0, 500.0]
        # LPS units: diameter in mm, WNTR converts to meters (÷1000)
        assert source.get_attribute("diameter") == pytest.approx([0.3, 0.4], rel=1e-6)
        assert source.get_attribute("roughness") == [100.0, 100.0]

    def test_pump_topology(self, inp_file):
        source = INPSource(inp_file, "pumps")
        assert source.get_attribute("start_node_name") == ["T1"]
        assert source.get_attribute("end_node_name") == ["J2"]

    def test_node_geometry_points(self, inp_file):
        source = INPSource(inp_file, "junctions")
        geom = source.get_geometry("points")
        assert "geometry.x" in geom
        assert "geometry.y" in geom
        assert geom["geometry.x"] == [10.0, 30.0]
        assert geom["geometry.y"] == [20.0, 20.0]

    def test_link_geometry_lines(self, inp_file):
        source = INPSource(inp_file, "pipes")
        geom = source.get_geometry("lines")
        assert "geometry.linestring_2d" in geom
        lines = geom["geometry.linestring_2d"]
        assert len(lines) == 2
        # P1: J1(10,20) -> J2(30,20)
        assert lines[0] == [[10.0, 20.0], [30.0, 20.0]]
        # P2: R1(0,20) -> J1(10,20)
        assert lines[1] == [[0.0, 20.0], [10.0, 20.0]]

    def test_node_bounding_box(self, inp_file):
        source = INPSource(inp_file, "junctions")
        bbox = source.get_bounding_box()
        assert bbox == (10.0, 20.0, 30.0, 20.0)

    def test_link_bounding_box_is_none(self, inp_file):
        source = INPSource(inp_file, "pipes")
        assert source.get_bounding_box() is None

    def test_from_source_info(self, inp_file):
        source = INPSource.from_source_info(
            {
                "source_type": "inp",
                "path": str(inp_file),
                "entity_type": "junctions",
            }
        )
        assert len(source) == 2

    def test_model_caching(self, inp_file):
        s1 = INPSource(inp_file, "junctions")
        s2 = INPSource(inp_file, "pipes")
        # Trigger model load
        len(s1)
        len(s2)
        assert s1._get_model() is s2._get_model()

    def test_invalid_entity_type(self, inp_file):
        with pytest.raises(ValueError, match="Unknown entity_type"):
            INPSource(inp_file, "bogus")


class TestINPSourceWithDatasetCreator:
    @pytest.fixture
    def config(self, inp_file):
        path = str(inp_file)
        return {
            "name": "test_water",
            "__sources__": {
                "junctions": {
                    "source_type": "inp",
                    "path": path,
                    "entity_type": "junctions",
                },
                "reservoirs": {
                    "source_type": "inp",
                    "path": path,
                    "entity_type": "reservoirs",
                },
                "tanks": {
                    "source_type": "inp",
                    "path": path,
                    "entity_type": "tanks",
                },
                "pipes": {
                    "source_type": "inp",
                    "path": path,
                    "entity_type": "pipes",
                },
            },
            "data": {
                "water_junction_entities": {
                    "__meta__": {"source": "junctions", "geometry": "points"},
                    "reference": {"property": "name"},
                    "water.elevation": {"property": "elevation"},
                },
                "water_reservoir_entities": {
                    "__meta__": {"source": "reservoirs", "geometry": "points"},
                    "reference": {"property": "name"},
                },
                "water_tank_entities": {
                    "__meta__": {"source": "tanks", "geometry": "points"},
                    "reference": {"property": "name"},
                },
                "water_pipe_entities": {
                    "__meta__": {"source": "pipes", "geometry": "lines"},
                    "reference": {"property": "name"},
                    "water.diameter": {"property": "diameter"},
                    "topology.from_node_id": {
                        "property": "start_node_name",
                        "id_link": [
                            {"entity_group": "water_junction_entities", "property": "name"},
                            {"entity_group": "water_reservoir_entities", "property": "name"},
                            {"entity_group": "water_tank_entities", "property": "name"},
                        ],
                    },
                    "topology.to_node_id": {
                        "property": "end_node_name",
                        "id_link": [
                            {"entity_group": "water_junction_entities", "property": "name"},
                            {"entity_group": "water_reservoir_entities", "property": "name"},
                            {"entity_group": "water_tank_entities", "property": "name"},
                        ],
                    },
                },
            },
        }

    def test_creates_dataset_with_entities(self, config):
        dataset = DatasetCreator(
            [SourcesSetup, AttributeDataLoading, IDGeneration],
            validate_config=False,
        ).create(config)

        junctions = dataset["data"]["water_junction_entities"]
        assert len(junctions["id"]) == 2
        assert junctions["reference"] == ["J1", "J2"]
        assert junctions["water.elevation"] == pytest.approx([100.0, 90.0])

    def test_id_linking_resolves_topology(self, config):
        dataset = DatasetCreator(
            [SourcesSetup, AttributeDataLoading, IDGeneration, IDLinking],
            validate_config=False,
        ).create(config)

        _junctions = dataset["data"]["water_junction_entities"]
        _reservoirs = dataset["data"]["water_reservoir_entities"]
        pipes = dataset["data"]["water_pipe_entities"]

        # Build name->id lookup from generated IDs
        name_to_id = {}
        for eg_name in (
            "water_junction_entities",
            "water_reservoir_entities",
            "water_tank_entities",
        ):
            eg = dataset["data"][eg_name]
            for name, eid in zip(eg["reference"], eg["id"]):
                name_to_id[name] = eid

        # P1: J1 -> J2
        assert pipes["topology.from_node_id"][0] == name_to_id["J1"]
        assert pipes["topology.to_node_id"][0] == name_to_id["J2"]
        # P2: R1 -> J1
        assert pipes["topology.from_node_id"][1] == name_to_id["R1"]
        assert pipes["topology.to_node_id"][1] == name_to_id["J1"]
