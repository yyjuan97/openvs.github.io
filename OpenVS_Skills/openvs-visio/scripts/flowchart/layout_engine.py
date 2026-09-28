import os
import tempfile

import graphviz

from flowchart.models import FlowchartData, NodeShape

# Graphviz shape mapping
SHAPE_MAP = {
    NodeShape.RECTANGLE: "box",
    NodeShape.DIAMOND: "diamond",
    NodeShape.ROUNDED: "oval",
    NodeShape.STADIUM: "oval",
}

# Add local Graphviz bin to PATH if not already present
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GRAPHVIZ_BIN = os.path.join(_PROJECT_ROOT, "Graphviz-15.0.0-win64", "bin")
if os.path.isdir(_GRAPHVIZ_BIN) and _GRAPHVIZ_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _GRAPHVIZ_BIN + os.pathsep + os.environ.get("PATH", "")


def compute_layout(data: FlowchartData, rankdir: str = "TB") -> FlowchartData:
    """Use graphviz to compute node positions and sizes, updating FlowchartData in place."""
    dot = _build_graphviz(data, rankdir)

    # Render to plain text format to get coordinates
    with tempfile.TemporaryDirectory() as tmpdir:
        plain_path = dot.render(format="plain", directory=tmpdir, cleanup=True)
        with open(plain_path, "r", encoding="utf-8") as f:
            plain_text = f.read()

    _parse_plain_output(plain_text, data)
    return data


def _build_graphviz(data: FlowchartData, rankdir: str) -> graphviz.Digraph:
    dot = graphviz.Digraph(format="plain")
    dot.attr(rankdir=rankdir, dpi="72", nodesep="1.2", ranksep="0.8")
    dot.attr("node", fontname="Microsoft YaHei", fontsize="10")
    dot.attr("edge", fontname="Microsoft YaHei", fontsize="9")

    for node in data.nodes:
        gviz_shape = SHAPE_MAP.get(node.shape, "box")
        dot.node(node.id, label=node.label, shape=gviz_shape, style="filled", fillcolor="white")

    for edge in data.edges:
        if edge.label:
            dot.edge(edge.source, edge.target, label=edge.label)
        else:
            dot.edge(edge.source, edge.target)

    return dot


def _parse_plain_output(plain_text: str, data: FlowchartData):
    """Parse graphviz plain text output and update node coordinates.

    Plain format lines:
      node  name  x  y  width  height  label
      edge  tail  head  npts  x1 y1 ... xn yn  label
    """
    for line in plain_text.strip().split("\n"):
        parts = line.split()
        if not parts:
            continue

        if parts[0] == "node":
            # node name x y width height label...
            node_id = parts[1]
            x = float(parts[2])
            y = float(parts[3])
            width = float(parts[4])
            height = float(parts[5])

            node = data.get_node(node_id)
            if node:
                node.x = x
                node.y = y
                node.width = width
                node.height = height
