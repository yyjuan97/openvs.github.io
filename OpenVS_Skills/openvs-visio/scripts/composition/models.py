from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FuncNode:
    id: str
    label: str
    parent_id: Optional[str] = None
    level: int = 0
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class CompositionData:
    nodes: list[FuncNode] = field(default_factory=list)

    def get_node(self, nid: str) -> Optional[FuncNode]:
        for n in self.nodes:
            if n.id == nid:
                return n
        return None

    def get_children(self, parent_id: str) -> list[FuncNode]:
        return [n for n in self.nodes if n.parent_id == parent_id]

    def get_root(self) -> Optional[FuncNode]:
        for n in self.nodes:
            if n.parent_id is None:
                return n
        return None

    def validate(self) -> list[str]:
        errors = []
        nids = [n.id for n in self.nodes]

        # Must have exactly one root
        roots = [n for n in self.nodes if n.parent_id is None]
        if len(roots) == 0:
            errors.append("No root node found (parent_id=null)")
        elif len(roots) > 1:
            errors.append(f"Multiple root nodes found: {[r.id for r in roots]}")

        # All parent_id references must exist
        for n in self.nodes:
            if n.parent_id is not None and n.parent_id not in nids:
                errors.append(f"Node '{n.id}' references non-existent parent_id '{n.parent_id}'")

        # No duplicate IDs
        if len(nids) != len(set(nids)):
            errors.append("Duplicate node IDs found")

        return errors
