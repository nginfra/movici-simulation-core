from __future__ import annotations

import dataclasses
import typing as t


@dataclasses.dataclass
class Nodes:
    id: t.Sequence[int]
    x: t.Sequence[float]
    y: t.Sequence[float]

    @classmethod
    def create(cls, nodes: t.List[t.Tuple[float, float]], id_offset=0):
        return Nodes(
            id=list(range(id_offset, len(nodes) + id_offset)),
            x=[node[0] for node in nodes],
            y=[node[1] for node in nodes],
        )

    def duplicate(self, id_offset):
        return Nodes(
            id=list(range(id_offset, len(self) + id_offset)),
            x=self.x,
            y=self.y,
        )

    def __add__(self, other):
        if isinstance(other, Nodes):
            return Nodes(id=[*self.id, *other.id], x=[*self.x, *other.x], y=[*self.y, *other.y])
        return NotImplemented

    def __len__(self):
        return len(self.id)


@dataclasses.dataclass
class Links:
    id: t.Sequence[int]
    from_idx: t.Sequence[int]
    to_idx: t.Sequence[int]

    @classmethod
    def create(cls, links: t.List[t.Tuple[int, int]], id_offset=0, node_idx_offset=0):
        return Links(
            id=list(range(id_offset, len(links) + id_offset)),
            from_idx=[link[0] + node_idx_offset for link in links],
            to_idx=[link[1] + node_idx_offset for link in links],
        )

    def __len__(self):
        return len(self.id)


class RoadNetworkGenerator:
    def __init__(
        self,
        nodes: t.List[t.Tuple[float, float]],
        links: t.List[t.Tuple[int, int]],
        geom_offset=(155000, 463000),
        max_speed=1,
        lanes=1,
        capacity=10,
    ):
        self.nodes = Nodes.create(nodes)
        self.links = Links.create(links, id_offset=3000)
        self.geom_offset = geom_offset
        self.max_speed = max_speed
        self.lanes = lanes
        self.capacity = capacity

    def generate(self):
        transport_nodes = self.nodes.duplicate(id_offset=1000)
        virtual_links = Links.create(
            [(i, i + len(self.nodes)) for i in range(len(self.nodes))], id_offset=2000
        )
        return {
            "virtual_node_entities": self.generate_virtual_nodes(self.nodes),
            "virtual_link_entities": self.generate_virtual_links(
                virtual_links, self.nodes, transport_nodes
            ),
            "transport_node_entities": self.generate_transport_nodes(transport_nodes),
            "road_segment_entities": self.generate_road_segments(self.links, transport_nodes),
        }

    def generate_virtual_nodes(self, nodes: Nodes):
        return self.generate_node_entities(nodes, ref_prefix="VN")

    def generate_transport_nodes(self, nodes: Nodes):
        return self.generate_node_entities(nodes, ref_prefix="TN")

    def generate_virtual_links(self, links: Links, virtual_nodes: Nodes, transport_nodes: Nodes):
        return self.generate_link_entities(links, virtual_nodes + transport_nodes, ref_prefix="VL")

    def generate_road_segments(self, links: Links, transport_nodes: Nodes):
        entities = self.generate_link_entities(links, nodes=transport_nodes, ref_prefix="RS")
        entities["transport.layout"] = [[self.lanes, 0, 0, 0]] * len(links)
        entities["transport.max_speed"] = [self.max_speed] * len(links)
        entities["transport.capacity.hours"] = [self.capacity] * len(links)
        return entities

    @staticmethod
    def generate_node_entities(nodes: Nodes, ref_prefix=""):
        return {
            "id": nodes.id,
            "reference": [ref_prefix + str(n) for n in range(len(nodes))],
            "geometry.x": nodes.x,
            "geometry.y": nodes.y,
        }

    @staticmethod
    def generate_link_entities(links: Links, nodes: Nodes, ref_prefix="") -> dict:
        count = len(links)
        return {
            "id": links.id,
            "reference": [ref_prefix + str(n) for n in range(count)],
            "topology.from_node_id": [nodes.id[links.from_idx[i]] for i in range(count)],
            "topology.to_node_id": [nodes.id[links.to_idx[i]] for i in range(count)],
            "geometry.linestring_2d": [
                [
                    [nodes.x[links.from_idx[i]], nodes.y[links.from_idx[i]]],
                    [nodes.x[links.to_idx[i]], nodes.y[links.to_idx[i]]],
                ]
                for i in range(count)
            ],
        }


def generate_road_network(
    nodes, links, geom_offset=(155000, 463000), max_speed=1, lanes=1, capacity=10
):
    return RoadNetworkGenerator(nodes, links, geom_offset, max_speed, lanes, capacity).generate()
