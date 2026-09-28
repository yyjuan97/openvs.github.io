from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class NodeShape(Enum):
    RECTANGLE = "rectangle"
    DIAMOND = "diamond"
    ROUNDED = "rounded"
    STADIUM = "stadium"


@dataclass
class Node:
    id: str
    label: str
    shape: NodeShape = NodeShape.RECTANGLE
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass
class FlowchartData:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def get_node(self, node_id: str) -> Optional[Node]:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def validate(self) -> list[str]:
        errors = []
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate node IDs found")
        for edge in self.edges:
            if edge.source not in ids:
                errors.append(f"Edge source '{edge.source}' not found in nodes")
            if edge.target not in ids:
                errors.append(f"Edge target '{edge.target}' not found in nodes")
        return errors
