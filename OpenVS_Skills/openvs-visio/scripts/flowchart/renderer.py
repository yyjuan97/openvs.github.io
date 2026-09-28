import math
import os

from common.visio_utils import start_visio, open_stencils, close_visio, rgb_to_visio
from flowchart.models import FlowchartData, NodeShape

# Default style settings
DEFAULT_FONT = "Microsoft YaHei"
DEFAULT_FONT_SIZE = 10  # pt
DEFAULT_FILL_COLOR = 16777215  # White
DEFAULT_LINE_COLOR = 0  # Black
DIAMOND_FILL_COLOR = 15790320  # Light gray
STADIUM_FILL_COLOR = 14408667  # Light blue

SCALE = 1.0

# Master shape NameU in basic_u.vss
MASTER_MAP = {
    NodeShape.RECTANGLE: "Rectangle",
    NodeShape.DIAMOND: "Diamond",
    NodeShape.ROUNDED: "Rounded Rectangle",
    NodeShape.STADIUM: "Ellipse",
}

# Chinese character sizing
CHAR_WIDTH_IN = 0.18
LINE_HEIGHT_IN = 0.32
PADDING_X = 0.4
PADDING_Y = 0.24
CHARS_PER_LINE = 10


def _estimate_node_size(label: str, shape: NodeShape) -> tuple[float, float]:
    """Estimate node width and height based on Chinese text length."""
    lines = []
    for i in range(0, len(label), CHARS_PER_LINE):
        lines.append(label[i:i + CHARS_PER_LINE])

    text_width = max(len(line) for line in lines) * CHAR_WIDTH_IN
    text_height = len(lines) * LINE_HEIGHT_IN

    w = text_width + PADDING_X
    h = text_height + PADDING_Y

    min_w, min_h = 1.0, 0.5
    if shape == NodeShape.DIAMOND:
        min_w, min_h = 1.4, 0.8
    if shape in (NodeShape.ROUNDED, NodeShape.STADIUM):
        min_w, min_h = 1.0, 0.5

    w = max(w, min_w)
    h = max(h, min_h)
    return w, h


def render_to_visio(data: FlowchartData, output_path: str, visible: bool = False):
    """Render FlowchartData to a Visio document and save to output_path."""
    visio = start_visio()
    basic_stencil, connector_stencil, stencil_masters, conn_master = open_stencils(visio)

    try:
        # Map NodeShape to stencil masters
        masters = {}
        for shape_type, master_name in MASTER_MAP.items():
            masters[shape_type] = stencil_masters.get(master_name)

        # Pre-compute actual node sizes
        node_sizes = {}
        for node in data.nodes:
            w, h = _estimate_node_size(node.label, node.shape)
            node_sizes[node.id] = (w, h)

        doc = visio.Documents.Add("")
        page = doc.Pages(1)

        _setup_page(page, data, node_sizes)

        # Draw nodes
        shapes = {}
        for node in data.nodes:
            if node.x is None or node.y is None:
                continue
            shape = _draw_node(page, node, masters, node_sizes[node.id])
            shapes[node.id] = shape

        # Draw edges
        for edge in data.edges:
            src_shape = shapes.get(edge.source)
            tgt_shape = shapes.get(edge.target)
            if src_shape and tgt_shape:
                _draw_edge(page, src_shape, tgt_shape, edge.label, conn_master)

        abs_path = os.path.abspath(output_path)
        doc.SaveAs(abs_path)
    finally:
        close_visio(visio, doc, [basic_stencil, connector_stencil], visible)


def _setup_page(page, data: FlowchartData, node_sizes: dict):
    """Adjust page size based on layout coordinates and actual node sizes."""
    if not data.nodes or all(n.x is None for n in data.nodes):
        return

    margin = 1.5
    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    for node in data.nodes:
        if node.x is None or node.y is None:
            continue
        w, h = node_sizes.get(node.id, (1.5, 0.75))
        min_x = min(min_x, node.x - w / 2)
        max_x = max(max_x, node.x + w / 2)
        min_y = min(min_y, node.y - h / 2)
        max_y = max(max_y, node.y + h / 2)

    page_width = (max_x - min_x) + 2 * margin
    page_height = (max_y - min_y) + 2 * margin

    page_width = min(page_width, 50)
    page_height = min(page_height, 50)

    page.PageSheet.Cells("PageWidth").FormulaU = f"{page_width:.2f} in"
    page.PageSheet.Cells("PageHeight").FormulaU = f"{page_height:.2f} in"


def _draw_node(page, node, masters: dict, size: tuple[float, float]):
    """Draw a node using cached Visio stencil masters."""
    master = masters.get(node.shape) or masters.get(NodeShape.RECTANGLE)

    x = node.x * SCALE
    y = node.y * SCALE
    shape = page.Drop(master, x, y)

    w, h = size
    shape.Cells("Width").FormulaU = f"{w:.4f} in"
    shape.Cells("Height").FormulaU = f"{h:.4f} in"

    shape.Text = node.label
    shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
    shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE} pt"

    fill_color = _get_fill_color(node.shape)
    shape.Cells("FillForegnd").FormulaU = rgb_to_visio(fill_color)
    shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)
    shape.Cells("Para.HorzAlign").FormulaU = "1"

    return shape


def _draw_edge(page, src_shape, tgt_shape, label: str, conn_master):
    """Draw a dynamic connector between two shapes."""
    connector = page.Drop(conn_master, 0, 0)

    try:
        connector.Cells("BeginX").GlueTo(src_shape.Cells("PinX"))
        connector.Cells("EndX").GlueTo(tgt_shape.Cells("PinX"))
    except Exception:
        src_x = src_shape.Cells("PinX").Result("")
        src_y = src_shape.Cells("PinY").Result("")
        tgt_x = tgt_shape.Cells("PinX").Result("")
        tgt_y = tgt_shape.Cells("PinY").Result("")
        connector.Cells("BeginX").FormulaU = f"{src_x}"
        connector.Cells("BeginY").FormulaU = f"{src_y}"
        connector.Cells("EndX").FormulaU = f"{tgt_x}"
        connector.Cells("EndY").FormulaU = f"{tgt_y}"

    connector.Cells("EndArrow").FormulaU = "4"

    if label:
        connector.Text = label
        connector.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
        connector.Cells("Char.Size").FormulaU = "8 pt"
        connector.Cells("Para.HorzAlign").FormulaU = "1"


def _get_fill_color(shape: NodeShape) -> int:
    if shape == NodeShape.DIAMOND:
        return DIAMOND_FILL_COLOR
    if shape in (NodeShape.ROUNDED, NodeShape.STADIUM):
        return STADIUM_FILL_COLOR
    return DEFAULT_FILL_COLOR
