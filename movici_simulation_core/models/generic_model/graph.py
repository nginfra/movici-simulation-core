from __future__ import annotations

import logging
import typing as t

from movici_simulation_core.models.generic_model.common import IncompleteSource
from movici_simulation_core.models.udf_model.compiler import compile_func, get_vars, parse

from .blocks import (
    Block,
    EntityGroupBlock,
    FunctionBlock,
    GeoMapBlock,
    GeoReduceBlock,
    InputBlock,
    OutputBlock,
)


def create_graph(config):
    return GraphFactory(config).create_graph()


class GraphFactory:
    def __init__(self, config):
        self.config = config

        self.blocks_by_name: t.Dict[str, Block] = {}
        self.pending_blocks: t.Dict[str, t.Dict[str, dict]] = {}
        self.blocks_list: t.List[Block] = []

    def create_graph(self):
        self.create_blocks(self.config["entity_groups"], block_type="entity_group")
        self.create_blocks(self.config["blocks"])
        self.create_output_blocks(self.config["outputs"])

        if self.pending_blocks:
            raise ValueError(
                f"Blocks missing or cycle detected for blocks: {', '.join(self.pending_blocks)}"
            )
        return GenericModelGraph(self.blocks_list)

    def create_blocks(self, blocks_config: dict, block_type=None):
        for name, conf in blocks_config.items():
            self.maybe_create_block(name, {**conf, "type": block_type or conf["type"]})

    def create_output_blocks(self, blocks_config: dict):
        for conf in blocks_config:
            name = f"output:{conf['source']}:{conf['attribute']}"
            self.maybe_create_block(name, {**conf, "type": "output"})

    def maybe_create_block(self, name, block_config):
        try:
            block = self.create_block(block_config)
        except IncompleteSource as e:
            for missing_block in e.missing:
                if missing_block not in self.pending_blocks:
                    self.pending_blocks[missing_block] = {}
                self.pending_blocks[missing_block][name] = block_config
            return
        self.add_block(name, block)
        self.create_pending_blocks(name)

    def create_block(self, block_config):
        block_type = block_config["type"]
        if block_type == "entity_group":
            return self.create_entity_group_block(block_config)
        if block_type == "input":
            return self.create_input_block(block_config)
        if block_type == "geomap":
            return self.create_geomap_block(block_config)
        if block_type == "georeduce":
            return self.create_georeduce_block(block_config)
        if block_type == "function":
            return self.create_function_block(block_config)
        if block_type == "output":
            return self.create_output_block(block_config)
        else:
            raise ValueError(f"unknown block type '{block_type}'")

    def create_entity_group_block(self, config):
        dataset, eg_name = config["path"]
        return EntityGroupBlock(dataset=dataset, entity_name=eg_name, geometry=config["geometry"])

    def create_input_block(self, config):
        eg = self.get_block_by_name(config["entity_group"])
        return InputBlock(eg, attribute_name=config["attribute"])

    def create_geomap_block(self, config):
        source = self.get_block_by_name(config["source"])
        target = self.get_block_by_name(config["target"])
        return GeoMapBlock(source=source, target=target, function=config["function"])

    def create_georeduce_block(self, config):
        source = self.get_block_by_name(config["source"])
        target = self.get_block_by_name(config["target"])
        return GeoReduceBlock(source=source, target=target, function=config["function"])

    def create_function_block(self, config):
        ast = parse(config["expression"])
        source_names = get_vars(ast)
        sources = self.get_blocks_by_name(source_names)
        func = compile_func(ast)
        return FunctionBlock(sources=sources, expression=config["expression"], function=func)

    def create_output_block(self, config):
        source = self.get_block_by_name(config["source"])
        return OutputBlock(source, attribute_name=config["attribute"])

    def create_pending_blocks(self, name):
        if not (pending := self.pending_blocks.pop(name, None)):
            return
        for pending_block_name, pending_conf in pending.items():
            self.maybe_create_block(pending_block_name, pending_conf)

    def add_block(self, name: str, block: Block):
        if name in self.blocks_by_name:
            raise ValueError(f"Duplicate block name detected: {name}")
        self.blocks_by_name[name] = block
        self.blocks_list.append(block)

    def get_block_by_name(self, name: str) -> Block:
        try:
            return self.blocks_by_name[name]
        except KeyError:
            raise IncompleteSource([name])

    def get_blocks_by_name(self, blocks: t.Sequence[str]) -> t.Dict[str, Block]:
        result: t.Dict[str, Block] = {}
        missing: t.List[str] = []
        for name in blocks:
            try:
                result[name] = self.blocks_by_name[name]
            except KeyError:
                missing.append(name)
        if missing:
            raise IncompleteSource(missing)
        return result


class GenericModelGraph:
    def __init__(self, blocks: t.Sequence[Block], logger: logging.Logger = None) -> None:
        self.blocks = blocks
        self.logger = logger
        self.outputs = [b for b in blocks if isinstance(b, OutputBlock)]

    def setup(self, **kwargs):
        for block in self.blocks:
            block.setup(**kwargs)

    def initialize(self, **kwargs):
        for output in self.outputs:
            output.initialize(**kwargs)

    def update(self, **kwargs):
        self.reset()
        for output in self.outputs:
            output.update(**kwargs)

    def reset(self):
        for block in self.blocks:
            block.reset()

    def validate(self):
        for block in self.blocks:
            block.validate()

        self.detect_unconnected_blocks()
        self.detect_duplicate_outputs()

    def detect_unconnected_blocks(self):
        dangling_blocks = set(self.blocks)
        all_outputs = (block for block in self.blocks if isinstance(block, OutputBlock))
        for output in all_outputs:
            dangling_blocks -= {output}
            dangling_blocks -= self.get_sources_for_block(output)
            if not dangling_blocks:
                break
        if self.logger and dangling_blocks:
            self.logger.warning("detected blocks that are not connected to any output")

    def detect_duplicate_outputs(self):
        all_outputs = [block for block in self.blocks if isinstance(block, OutputBlock)]
        unique_outputs = {(o.entity_group.entity_group, o.attribute_name) for o in all_outputs}
        if self.logger and len(all_outputs) > len(unique_outputs):
            self.logger.warning("duplicate outputs detected")

    @staticmethod
    def get_sources_for_block(
        block: OutputBlock,
        block_type: t.Optional[t.Union[t.Tuple[t.Type[Block], ...], t.Type[Block]]] = None,
    ) -> t.Set[Block]:
        sources = block.get_sources()
        rv: t.Set[Block] = set()
        for source in sources:
            rv.add(source)
            rv.update(GenericModelGraph.get_sources_for_block(source, block_type=block_type))
        return rv
