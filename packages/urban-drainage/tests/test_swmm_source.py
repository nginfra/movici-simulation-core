"""Tests for the SWMM ``.inp`` dataset source."""

import textwrap

import pytest

from movici_simulation_core.preprocessing import MultipleEntityTypeSource
from movici_simulation_core.preprocessing.dataset_creator import (
    AttributeDataLoading,
    DatasetCreator,
    IDGeneration,
    IDLinking,
    SourcesSetup,
)
from movici_urban_drainage_model.swmm_source import SWMMSource

MINIMAL_INP = textwrap.dedent("""\
    [TITLE]
    Test drainage network

    [JUNCTIONS]
    ;Name Elev MaxDepth InitDepth SurDepth Aponded
    J1   10   5   0   0   0
    J2   9    5   0   0   0

    [OUTFALLS]
    ;Name Elev Type Gated
    O1   8    FREE   NO

    [STORAGE]
    ;Name Elev MaxDepth InitDepth Shape Coeff Expon Const
    ST1  4    6   0   FUNCTIONAL   0   0   500

    [CONDUITS]
    ;Name From To Length Roughness InOff OutOff InitFlow MaxFlow
    C1   J1   J2   100   0.01   0   0   0   0
    C2   J2   ST1  120   0.012  0   0   0   0

    [PUMPS]
    ;Name From To Curve Status Startup Shutoff
    PU1  ST1  O1   *   ON   0   0

    [XSECTIONS]
    C1   CIRCULAR   1.0   0   0   0   1
    C2   CIRCULAR   1.5   0   0   0   1

    [SUBCATCHMENTS]
    ;Name Gage Outlet Area %Imperv Width Slope Curb
    S1   RG1  J1   4   50   400   0.5   0

    [SUBAREAS]
    S1   0.01   0.1   0.05   0.05   25   OUTLET

    [INFILTRATION]
    S1   76.2   3.81   4   7   0

    [RAINGAGES]
    ;Name Format Interval SCF Source
    RG1  INTENSITY   1:00   1.0   TIMESERIES   TS1

    [COORDINATES]
    ;Node X Y
    J1   0    0
    J2   100  0
    O1   200  0
    ST1  150  50

    [VERTICES]
    C1   50   10

    [Polygons]
    S1   0    0
    S1   0    50
    S1   50   50

    [SYMBOLS]
    RG1  -100  100
""")


@pytest.fixture
def inp_file(tmp_path):
    path = tmp_path / "network.inp"
    path.write_text(MINIMAL_INP)
    return path


class TestSWMMSource:
    def test_is_multi_entity_source(self, inp_file):
        assert isinstance(SWMMSource(inp_file), MultipleEntityTypeSource)

    def test_has_all_entity_types(self, inp_file):
        expected = {
            "junctions",
            "outfalls",
            "storage",
            "conduits",
            "pumps",
            "orifices",
            "weirs",
            "outlets",
            "subcatchments",
            "raingages",
        }
        assert set(SWMMSource(inp_file).keys()) == expected

    def test_invalid_entity_type_raises_key_error(self, inp_file):
        with pytest.raises(KeyError, match="Unknown entity type"):
            SWMMSource(inp_file)["bogus"]

    def test_counts(self, inp_file):
        source = SWMMSource(inp_file)
        assert len(source["junctions"]) == 2
        assert len(source["outfalls"]) == 1
        assert len(source["storage"]) == 1
        assert len(source["conduits"]) == 2
        assert len(source["pumps"]) == 1
        assert len(source["weirs"]) == 0
        assert len(source["subcatchments"]) == 1
        assert len(source["raingages"]) == 1

    def test_junction_attributes(self, inp_file):
        junctions = SWMMSource(inp_file)["junctions"]
        assert junctions.get_attribute("name") == ["J1", "J2"]
        assert junctions.get_attribute("invert_elevation") == [10.0, 9.0]
        assert junctions.get_attribute("max_depth") == [5.0, 5.0]

    def test_outfall_attributes(self, inp_file):
        outfalls = SWMMSource(inp_file)["outfalls"]
        assert outfalls.get_attribute("name") == ["O1"]
        assert outfalls.get_attribute("invert_elevation") == [8.0]
        assert outfalls.get_attribute("outfall_type") == ["FREE"]

    def test_storage_attributes(self, inp_file):
        storage = SWMMSource(inp_file)["storage"]
        assert storage.get_attribute("name") == ["ST1"]
        assert storage.get_attribute("storage_constant") == [500.0]

    def test_conduit_topology_and_xsection(self, inp_file):
        conduits = SWMMSource(inp_file)["conduits"]
        assert conduits.get_attribute("from_node") == ["J1", "J2"]
        assert conduits.get_attribute("to_node") == ["J2", "ST1"]
        assert conduits.get_attribute("length") == [100.0, 120.0]
        assert conduits.get_attribute("cross_section_shape") == ["CIRCULAR", "CIRCULAR"]
        assert conduits.get_attribute("cross_section_geometry")[1] == [1.5, 0.0, 0.0, 0.0]

    def test_subcatchment_attributes(self, inp_file):
        subs = SWMMSource(inp_file)["subcatchments"]
        assert subs.get_attribute("name") == ["S1"]
        assert subs.get_attribute("raingage") == ["RG1"]
        assert subs.get_attribute("outlet_node") == ["J1"]
        assert subs.get_attribute("area") == [4.0]
        assert subs.get_attribute("max_infiltration_rate") == [76.2]

    def test_node_geometry_points(self, inp_file):
        geom = SWMMSource(inp_file)["junctions"].get_geometry("points")
        assert geom["geometry.x"] == [0.0, 100.0]
        assert geom["geometry.y"] == [0.0, 0.0]

    def test_link_geometry_lines_with_vertices(self, inp_file):
        geom = SWMMSource(inp_file)["conduits"].get_geometry("lines")
        lines = geom["geometry.linestring_2d"]
        # C1: J1(0,0) -> vertex(50,10) -> J2(100,0)
        assert lines[0] == [[0.0, 0.0], [50.0, 10.0], [100.0, 0.0]]
        # C2: J2(100,0) -> ST1(150,50)
        assert lines[1] == [[100.0, 0.0], [150.0, 50.0]]

    def test_subcatchment_geometry_polygon_closed(self, inp_file):
        geom = SWMMSource(inp_file)["subcatchments"].get_geometry("polygons")
        ring = geom["geometry.polygon_2d"][0]
        assert ring[0] == [0.0, 0.0]
        assert ring[-1] == ring[0]  # closed

    def test_node_geometry_wrong_type_raises(self, inp_file):
        with pytest.raises(ValueError, match="only supports 'points'"):
            SWMMSource(inp_file)["junctions"].get_geometry("lines")

    def test_link_geometry_wrong_type_raises(self, inp_file):
        with pytest.raises(ValueError, match="only supports 'lines'"):
            SWMMSource(inp_file)["conduits"].get_geometry("points")

    def test_node_bounding_box(self, inp_file):
        assert SWMMSource(inp_file)["junctions"].get_bounding_box() == (0.0, 0.0, 100.0, 0.0)

    def test_link_bounding_box_is_none(self, inp_file):
        assert SWMMSource(inp_file)["conduits"].get_bounding_box() is None

    def test_combined_bounding_box(self, inp_file):
        # nodes: J1(0,0) J2(100,0) O1(200,0) ST1(150,50)
        assert SWMMSource(inp_file).get_bounding_box() == (0.0, 0.0, 200.0, 50.0)

    def test_model_loaded_lazily_and_shared(self, inp_file):
        source = SWMMSource(inp_file)
        assert source.inp is None
        a = source["junctions"]
        assert source.inp is not None
        assert source["conduits"].inp is a.inp

    def test_from_source_info_with_entity_type(self, inp_file):
        source = SWMMSource.from_source_info(
            {"source_type": "swmm", "path": str(inp_file), "entity_type": "junctions"}
        )
        assert not isinstance(source, MultipleEntityTypeSource)
        assert len(source) == 2

    def test_from_source_info_without_entity_type(self, inp_file):
        source = SWMMSource.from_source_info({"source_type": "swmm", "path": str(inp_file)})
        assert isinstance(source, MultipleEntityTypeSource)


class TestSWMMSourceWithDatasetCreator:
    @pytest.fixture
    def config(self, inp_file):
        node_links = [
            {"entity_group": "drainage_junction_entities", "property": "name"},
            {"entity_group": "drainage_outfall_entities", "property": "name"},
            {"entity_group": "drainage_storage_entities", "property": "name"},
        ]
        return {
            "name": "test_drainage",
            "__sources__": {"net": {"source_type": "swmm", "path": str(inp_file)}},
            "data": {
                "drainage_junction_entities": {
                    "__meta__": {"source": "net.junctions", "geometry": "points"},
                    "reference": {"property": "name"},
                    "urban_drainage.invert_elevation": {"property": "invert_elevation"},
                },
                "drainage_outfall_entities": {
                    "__meta__": {"source": "net.outfalls", "geometry": "points"},
                    "reference": {"property": "name"},
                },
                "drainage_storage_entities": {
                    "__meta__": {"source": "net.storage", "geometry": "points"},
                    "reference": {"property": "name"},
                },
                "drainage_conduit_entities": {
                    "__meta__": {"source": "net.conduits", "geometry": "lines"},
                    "reference": {"property": "name"},
                    "shape.length": {"property": "length"},
                    "topology.from_node_id": {"property": "from_node", "id_link": node_links},
                    "topology.to_node_id": {"property": "to_node", "id_link": node_links},
                },
            },
        }

    def test_creates_entities(self, config):
        dataset = DatasetCreator(
            [SourcesSetup, AttributeDataLoading, IDGeneration], validate_config=False
        ).create(config)
        junctions = dataset["data"]["drainage_junction_entities"]
        assert junctions["reference"] == ["J1", "J2"]
        assert junctions["urban_drainage.invert_elevation"] == pytest.approx([10.0, 9.0])
        conduits = dataset["data"]["drainage_conduit_entities"]
        assert conduits["shape.length"] == pytest.approx([100.0, 120.0])

    def test_id_linking_resolves_topology(self, config):
        dataset = DatasetCreator(
            [SourcesSetup, AttributeDataLoading, IDGeneration, IDLinking], validate_config=False
        ).create(config)
        name_to_id = {}
        for eg_name in (
            "drainage_junction_entities",
            "drainage_outfall_entities",
            "drainage_storage_entities",
        ):
            eg = dataset["data"][eg_name]
            for name, eid in zip(eg["reference"], eg["id"]):
                name_to_id[name] = eid

        conduits = dataset["data"]["drainage_conduit_entities"]
        # C1: J1 -> J2 ; C2: J2 -> ST1
        assert conduits["topology.from_node_id"] == [name_to_id["J1"], name_to_id["J2"]]
        assert conduits["topology.to_node_id"] == [name_to_id["J2"], name_to_id["ST1"]]
