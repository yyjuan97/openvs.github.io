import os
import tempfile

import graphviz

from component.models import ComponentData

# Add local Graphviz bin to PATH
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GRAPHVIZ_BIN = os.path.join(_PROJECT_ROOT, "Graphviz-15.0.0-win64", "bin")
if os.path.isdir(_GRAPHVIZ_BIN) and _GRAPHVIZ_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _GRAPHVIZ_BIN + os.pathsep + os.environ.get("PATH", "")

# Node sizing
CHAR_WIDTH_IN = 0.18
LINE_HEIGHT_IN = 0.32
PADDING_X = 0.6
PADDING_Y = 0.4
CHARS_PER_LINE = 12
MIN_NODE_WIDTH = 2.0
MIN_NODE_HEIGHT = 1.0


def _estimate_component_size(label: str, n_provided: int, n_required: int) -> tuple[float, float]:
    """Estimate component box size based on name and interface counts.

    Box layout:
    - «component» tag line
    - Component name
    - Separator line
    - Required interfaces (if any)
    - Provided interfaces (if any)
    """
    # Count lines of text
    lines = 2  # tag + name
    if n_required > 0:
        lines += 1 + n_required  # header + each required
    if n_provided > 0:
        lines += 1 + n_provided  # header + each provided

    # Width: longest line
    max_len = len(label)
    for n in range(max(n_provided, n_required)):
        iface_len = 8  # rough estimate for interface name
        max_len = max(max_len, iface_len)

    text_width = max_len * CHAR_WIDTH_IN
    w = max(text_width + PADDING_X, MIN_NODE_WIDTH)
    h = max(lines * LINE_HEIGHT_IN + PADDING_Y, MIN_NODE_HEIGHT)
    return w, h


def compute_layout(data: ComponentData) -> ComponentData:
    """Use Graphviz to compute component positions."""
    # Pre-compute component sizes
    for comp in data.components:
        n_provided = len(data.get_provided_interfaces(comp.id))
        n_required = len(data.get_required_interfaces(comp.id))
        w, h = _estimate_component_size(comp.label, n_provided, n_required)
        comp.width = w
        comp.height = h

    dot = _build_graphviz(data)

    with tempfile.TemporaryDirectory() as tmpdir:
        plain_path = dot.render(format="plain", directory=tmpdir, cleanup=True)
        with open(plain_path, "r", encoding="utf-8") as f:
            plain_text = f.read()

    _parse_plain_output(plain_text, data)
    return data


def _build_graphviz(data: ComponentData) -> graphviz.Digraph:
    dot = graphviz.Digraph(format="plain")
    dot.attr(rankdir="TB", dpi="72", nodesep="2.0", ranksep="2.0", newrank="true")
    dot.attr("node", fontname="Microsoft YaHei", fontsize="10", shape="box", style="filled", fillcolor="white", margin="0.3,0.15")
    dot.attr("edge", fontname="Microsoft YaHei", fontsize="9", style="dashed")

    for comp in data.components:
        dot.node(comp.id, label=comp.label)

    for dep in data.dependencies:
        if dep.label:
            dot.edge(dep.from_id, dep.to_id, label=dep.label)
        else:
            dot.edge(dep.from_id, dep.to_id)

    return dot


def _parse_plain_output(plain_text: str, data: ComponentData):
    """Parse graphviz plain text output and update component coordinates."""
    for line in plain_text.strip().split("\n"):
        parts = line.split()
        if not parts:
            continue

        if parts[0] == "node":
            comp_id = parts[1]
            x = float(parts[2])
            y = float(parts[3])
            width = float(parts[4])
            height = float(parts[5])

            comp = data.get_component(comp_id)
            if comp:
                comp.x = x
                comp.y = y
                # Keep our pre-computed sizes (Graphviz gives uniform sizes)
