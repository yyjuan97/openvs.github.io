from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class InterfaceType(Enum):
    PROVIDED = "provided"
    REQUIRED = "required"


@dataclass
class Component:
    id: str
    label: str
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class Interface:
    id: str
    label: str
    iface_type: InterfaceType = InterfaceType.PROVIDED
    component_id: str = ""


@dataclass
class Dependency:
    id: str
    from_id: str
    to_id: str
    label: str = ""


@dataclass
class ComponentData:
    components: list[Component] = field(default_factory=list)
    interfaces: list[Interface] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)

    def get_component(self, cid: str) -> Optional[Component]:
        for c in self.components:
            if c.id == cid:
                return c
        return None

    def get_provided_interfaces(self, cid: str) -> list[Interface]:
        return [i for i in self.interfaces if i.component_id == cid and i.iface_type == InterfaceType.PROVIDED]

    def get_required_interfaces(self, cid: str) -> list[Interface]:
        return [i for i in self.interfaces if i.component_id == cid and i.iface_type == InterfaceType.REQUIRED]

    def validate(self) -> list[str]:
        errors = []
        cids = [c.id for c in self.components]

        if len(cids) != len(set(cids)):
            errors.append("Duplicate component IDs found")
        if len(cids) < 2:
            errors.append("Must have at least 2 components")

        for dep in self.dependencies:
            if dep.from_id not in cids:
                errors.append(f"Dependency from_id '{dep.from_id}' not found in components")
            if dep.to_id not in cids:
                errors.append(f"Dependency to_id '{dep.to_id}' not found in components")

        for iface in self.interfaces:
            if iface.component_id not in cids:
                errors.append(f"Interface component_id '{iface.component_id}' not found in components")

        return errors
