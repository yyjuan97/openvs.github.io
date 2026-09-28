from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeShape(Enum):
    RECTANGLE = "rectangle"
    DIAMOND = "diamond"
    ROUNDED = "rounded"
    STADIUM = "stadium"


@dataclass
class Lane:
    id: str
    label: str
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class SwimlaneNode:
    id: str
    label: str
    lane_id: str
    shape: NodeShape = NodeShape.RECTANGLE
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class SwimlaneEdge:
    source: str
    target: str
    label: str = ""


@dataclass
class SwimlaneData:
    lanes: list[Lane] = field(default_factory=list)
    nodes: list[SwimlaneNode] = field(default_factory=list)
    edges: list[SwimlaneEdge] = field(default_factory=list)

    def get_node(self, nid: str) -> Optional[SwimlaneNode]:
        for n in self.nodes:
            if n.id == nid:
                return n
        return None

    def get_lane(self, lid: str) -> Optional[Lane]:
        for l in self.lanes:
            if l.id == lid:
                return l
        return None

    def get_nodes_by_lane(self, lid: str) -> list[SwimlaneNode]:
        return [n for n in self.nodes if n.lane_id == lid]

    def validate(self) -> list[str]:
        errors = []
        lids = [l.id for l in self.lanes]
        nids = [n.id for n in self.nodes]

        if len(lids) < 2:
            errors.append("Must have at least 2 lanes")
        if len(lids) != len(set(lids)):
            errors.append("Duplicate lane IDs found")
        if len(nids) != len(set(nids)):
            errors.append("Duplicate node IDs found")

        for node in self.nodes:
            if node.lane_id not in lids:
                errors.append(f"Node '{node.id}' references non-existent lane_id '{node.lane_id}'")
        for edge in self.edges:
            if edge.source not in nids:
                errors.append(f"Edge source '{edge.source}' not found in nodes")
            if edge.target not in nids:
                errors.append(f"Edge target '{edge.target}' not found in nodes")

        return errors
