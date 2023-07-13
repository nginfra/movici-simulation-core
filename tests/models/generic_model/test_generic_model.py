from unittest.mock import Mock

import pytest

from movici_simulation_core.models.generic_model.generic_model import (
    EntityGroupBlock,
    FunctionBlock,
    GenericModelGraph,
    GeoMapBlock,
    GeoReduceBlock,
    GraphFactory,
    IncompleteSource,
    InputBlock,
    OutputBlock,
    create_graph,
)


def create_config(blocks, outputs=None, entity_groups=None):
    entity_groups = entity_groups or {
        "some_block": {"path": ["my_dataset", "some_entities"], "geometry": "point"},
        "another_block": {"path": ["my_dataset", "another_entities"], "geometry": "point"},
    }
    outputs = outputs or []
    return {"entity_groups": entity_groups, "blocks": blocks, "outputs": outputs}


@pytest.fixture
def config():
    return {
        "entity_groups": {
            "pois": {"path": ["my_dataset", "poi_entities"], "geometry": "point"},
            "areas": {"path": ["total_area", "area_entities"], "geometry": "polygon"},
        },
        "blocks": {
            "pois_in_area": {
                "type": "geomap",
                "source": "pois",
                "target": "areas",
                "function": "overlap",
            },
            "pois_without_power": {
                "type": "georeduce",
                "source": "poi_has_power",
                "target": "pois_in_area",
                "function": "sum",
            },
            "poi_has_power": {
                "type": "input",
                "entity_group": "pois",
                "attribute": "operational.has_power",
            },
        },
        "outputs": [
            {
                "source": "pois_without_power",
                "attribute": "impact.pois_without_power",
            },
        ],
    }


class TestGraphFactory:
    @pytest.fixture
    def graph_factory(self):
        factory = GraphFactory(None)
        factory.blocks_by_name = {"some_block": object(), "another_block": object()}
        return factory

    @pytest.mark.parametrize("blocks", [[], ["some_block"], ["some_block", "another_block"]])
    def test_get_blocks_by_name(self, blocks, graph_factory):
        result = graph_factory.get_blocks_by_name(blocks)
        for block in blocks:
            assert result[block] is graph_factory.blocks_by_name[block]

    @pytest.mark.parametrize(
        "requested,missing",
        [
            (["some_block", "missing_block"], ["missing_block"]),
            (
                ["missing_block", "also_missing"],
                ["missing_block", "also_missing"],
            ),
        ],
    )
    def test_get_blocks_by_name_raises_on_missing_blocks(self, requested, missing, graph_factory):
        with pytest.raises(IncompleteSource) as e:
            graph_factory.get_blocks_by_name(requested)
        assert e.value.missing == missing

    @pytest.mark.parametrize(
        "config, expected",
        [
            (
                {"type": "input", "entity_group": "some_block", "attribute": "some_attribute"},
                lambda blocks: InputBlock(
                    entity_group=blocks["some_block"], attribute_name="some_attribute"
                ),
            ),
            (
                {"type": "output", "source": "some_block", "attribute": "some_attribute"},
                lambda blocks: OutputBlock(
                    source=blocks["some_block"], attribute_name="some_attribute"
                ),
            ),
            (
                {
                    "type": "entity_group",
                    "path": ["some_dataset", "some_group"],
                    "geometry": "point",
                },
                lambda _: EntityGroupBlock(
                    dataset="some_dataset", entity_group="some_group", geometry="point"
                ),
            ),
            (
                {
                    "type": "geomap",
                    "source": "some_block",
                    "target": "another_block",
                    "function": "nearest",
                },
                lambda blocks: GeoMapBlock(
                    source=blocks["some_block"], target=blocks["another_block"], function="nearest"
                ),
            ),
            (
                {
                    "type": "georeduce",
                    "source": "some_block",
                    "target": "another_block",
                    "function": "sum",
                },
                lambda blocks: GeoReduceBlock(
                    source=blocks["some_block"], target=blocks["another_block"], function="sum"
                ),
            ),
            (
                {
                    "type": "function",
                    "expression": "some_block+another_block",
                },
                lambda blocks: FunctionBlock(
                    sources="sources are not checked with __eq__",
                    expression="some_block+another_block",
                ),
            ),
        ],
    )
    def test_create_block(self, graph_factory: GraphFactory, config, expected):
        assert graph_factory.create_block(config) == expected(graph_factory.blocks_by_name)

    def test_function_block_sources(self, graph_factory: GraphFactory):
        block = graph_factory.create_block(
            {"type": "function", "expression": "some_block+another_block"}
        )
        assert block.sources == {
            "some_block": graph_factory.blocks_by_name["some_block"],
            "another_block": graph_factory.blocks_by_name["another_block"],
        }


def test_create_simple_graph():
    config = create_config(
        entity_groups={"entities": {"path": ["my_dataset", "some_entities"], "geometry": "point"}},
        blocks={
            "some_input": {
                "type": "input",
                "entity_group": "entities",
                "attribute": "some_attribute",
            }
        },
        outputs=[{"source": "some_input", "attribute": "some_output"}],
    )

    graph = create_graph(config)
    eg_block = EntityGroupBlock("my_dataset", "some_entities", "point")
    input_block = InputBlock(eg_block, "some_attribute")
    output_block = OutputBlock(input_block, attribute_name="some_output")
    assert graph.blocks == [eg_block, input_block, output_block]


def test_create_graph_with_deferred_dependencies():
    graph = create_graph(
        {
            "entity_groups": {
                "pois": {"path": ["my_dataset", "poi_entities"], "geometry": "point"},
                "areas": {"path": ["total_area", "area_entities"], "geometry": "polygon"},
            },
            "blocks": {
                "pois_in_area": {
                    "type": "geomap",
                    "source": "pois",
                    "target": "areas",
                    "function": "overlap",
                },
                "pois_without_power": {
                    "type": "georeduce",
                    "source": "poi_has_power",
                    "target": "pois_in_area",
                    "function": "sum",
                },
                "poi_has_power": {
                    "type": "input",
                    "entity_group": "pois",
                    "attribute": "operational.has_power",
                },
            },
            "outputs": [
                {
                    "source": "pois_without_power",
                    "attribute": "impact.pois_without_power",
                },
            ],
        }
    )
    pois = EntityGroupBlock("my_dataset", "poi_entities", "point")
    areas = EntityGroupBlock("total_area", "area_entities", "polygon")
    poi_has_power = InputBlock(entity_group=pois, attribute_name="operational.has_power")
    pois_in_area = GeoMapBlock(source=pois, target=areas, function="overlap")
    pois_without_power = GeoReduceBlock(source=poi_has_power, target=pois_in_area, function="sum")
    output_1 = OutputBlock(pois_without_power, attribute_name="impact.pois_without_power")
    assert graph.blocks == [
        pois,
        areas,
        pois_in_area,
        poi_has_power,
        pois_without_power,
        output_1,
    ]


def test_create_graph_raises_for_missing_block_defitinion():
    with pytest.raises(ValueError) as e:
        create_graph(
            {
                "entity_groups": {},
                "blocks": {
                    "some_block": {
                        "type": "function",
                        "expression": "missing",
                    },
                    "another_block": {
                        "type": "function",
                        "expression": "also_missing",
                    },
                },
                "outputs": [],
            }
        )
    assert str(e.value) == "Blocks missing or cycle detected for blocks: missing, also_missing"


def test_create_graph_raises_on_cyclic_graph():
    with pytest.raises(ValueError) as e:
        create_graph(
            {
                "entity_groups": {},
                "blocks": {
                    "some_block": {
                        "type": "function",
                        "expression": "another_block",
                    },
                    "another_block": {
                        "type": "function",
                        "expression": "some_block",
                    },
                },
                "outputs": [],
            }
        )
    assert str(e.value) == "Blocks missing or cycle detected for blocks: another_block, some_block"


def test_raises_for_duplicate_keys_in_config():
    with pytest.raises(ValueError) as e:
        create_graph(
            create_config(
                {
                    "some_block": {
                        "type": "input",
                        "entity_group": "another_block",
                        "attribute": "some_attribute",
                    }
                }
            )
        )
    assert str(e.value) == "Duplicate block name detected: some_block"


class TestGraph:
    @pytest.mark.parametrize("func", ["setup", "initialize", "reset", "validate"])
    def test_graph_proxies_functions(self, func):
        blocks = [Mock(), Mock()]
        graph = GenericModelGraph(blocks)
        getattr(graph, func)()
        assert all(getattr(b, func).call_count == 1 for b in blocks)

    def test_inputs_to_outputs(self):
        config = create_config(
            blocks={
                "some_input": {
                    "type": "input",
                    "entity_group": "some_block",
                    "attribute": "some_attribute",
                },
                "another_input": {
                    "type": "input",
                    "entity_group": "some_block",
                    "attribute": "another_attribute",
                },
                "function_a": {
                    "type": "function",
                    "expression": "some_input",
                },
                "function_b": {
                    "type": "function",
                    "expression": "function_a+another_input",
                },
            },
            outputs=[
                {"source": "some_input", "attribute": "output_1"},
                {"source": "function_b", "attribute": "output_2"},
            ],
        )

        expected_names = {
            "some_input": ["output:some_input:output_1", "output:function_b:output_2"],
            "another_input": ["output:function_b:output_2"],
        }

        factory = GraphFactory(config)
        factory.create_graph()
        blocks_by_name = factory.blocks_by_name

        graph = create_graph(config)
        expected = {
            blocks_by_name[inp]: [blocks_by_name[output] for output in outputs]
            for inp, outputs in expected_names.items()
        }
        assert graph.inputs_to_outputs == expected

    def test_graph_validates_succesfully(self, config):
        graph = create_graph(config)
        assert graph.validate() is None

    invalid_graphs = [
        (
            "inputs that have no output",
            {
                "entity_groups": {
                    "some_block": {"path": ["my_dataset", "entity_group"], "geometry": "point"},
                },
                "blocks": {
                    "input": {
                        "type": "input",
                        "entity_group": "some_block",
                        "attribute": "some_attribute",
                    }
                },
                "outputs": [],
            },
        ),
        (
            "duplicate outputs",
            {
                "entity_groups": {
                    "some_block": {"path": ["my_dataset", "entity_group"], "geometry": "point"},
                },
                "blocks": {
                    "input": {
                        "type": "input",
                        "entity_group": "some_block",
                        "attribute": "some_attribute",
                    },
                    "func": {"type": "function", "expression": "input"},
                },
                "outputs": [
                    {"source": "input", "attribute": "some_attr"},
                    {"source": "func", "attribute": "some_attr"},
                ],
            },
        ),
        (
            "isolated_blocks",
            {
                "entity_groups": {
                    "some_block": {"path": ["my_dataset", "entity_group"], "geometry": "point"},
                },
                "blocks": {
                    "input": {
                        "type": "input",
                        "entity_group": "some_block",
                        "attribute": "some_attribute",
                    },
                    "func": {"type": "function", "expression": "input"},
                },
                "outputs": [
                    {"source": "input", "attribute": "some_attr"},
                ],
            },
        ),
    ]

    @pytest.mark.parametrize(
        "config", map(lambda i: i[1], invalid_graphs), ids=map(lambda i: i[0], invalid_graphs)
    )
    def test_graph_warns_about_noncritical_issues(self, config):
        graph = create_graph(config)
        graph.logger = Mock()

        graph.validate()
        assert graph.logger.warning.call_count > 0
