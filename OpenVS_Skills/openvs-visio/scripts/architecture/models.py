from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Layer:
    id: str
    label: str
    level: int = 0
    y: Optional[float] = None
    height: Optional[float] = None


@dataclass
class ArchComponent:
    id: str
    label: str
    layer_id: str = ""
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class ArchConnection:
    from_id: str
    to_id: str
    label: str = ""


@dataclass
class ArchData:
    layers: list[Layer] = field(default_factory=list)
    components: list[ArchComponent] = field(default_factory=list)
    connections: list[ArchConnection] = field(default_factory=list)

    def get_layer(self, lid: str) -> Optional[Layer]:
        for l in self.layers:
            if l.id == lid:
                return l
        return None

    def get_components_by_layer(self, layer_id: str) -> list[ArchComponent]:
        return [c for c in self.components if c.layer_id == layer_id]

    def get_component(self, cid: str) -> Optional[ArchComponent]:
        for c in self.components:
            if c.id == cid:
                return c
        return None

    def validate(self) -> list[str]:
        errors = []
        lids = [l.id for l in self.layers]
        cids = [c.id for c in self.components]

        if len(lids) < 2:
            errors.append("Must have at least 2 layers")
        if len(lids) != len(set(lids)):
            errors.append("Duplicate layer IDs found")
        if len(cids) != len(set(cids)):
            errors.append("Duplicate component IDs found")

        for comp in self.components:
            if comp.layer_id not in lids:
                errors.append(f"Component '{comp.id}' references non-existent layer_id '{comp.layer_id}'")

        for conn in self.connections:
            if conn.from_id not in cids:
                errors.append(f"Connection from_id '{conn.from_id}' not found in components")
            if conn.to_id not in cids:
                errors.append(f"Connection to_id '{conn.to_id}' not found in components")

        return errors
