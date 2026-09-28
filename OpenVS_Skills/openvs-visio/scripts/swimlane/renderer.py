import os

from common.visio_utils import start_visio, open_stencils, close_visio, rgb_to_visio
from swimlane.layout_engine import (
    LANE_WIDTH, LANE_LABEL_HEIGHT,
    MARGIN_TOP, MARGIN_RIGHT, MARGIN_BOTTOM, MARGIN_LEFT,
    NODE_ACTIVITY_H,
)
from swimlane.models import NodeShape, SwimlaneData

DEFAULT_FONT = "Microsoft YaHei"
FONT_SIZE_TITLE = 10       # lane label
FONT_SIZE_NODE = 9         # node text
FONT_SIZE_LABEL = 7        # edge label
DEFAULT_LINE_COLOR = 0     # Black
START_END_COLOR = 4980736  # #4CAF50 green for start/end nodes
DIAMOND_COLOR = 16763904   # #FFC107 yellow for decision nodes
HEADER_BG_COLOR = 5973191  # deep blue for lane header
HEADER_TEXT_COLOR = 16777215  # white

MASTER_MAP = {
    NodeShape.RECTANGLE: "Rectangle",
    NodeShape.DIAMOND: "Diamond",
    NodeShape.ROUNDED: "Rounded Rectangle",
    NodeShape.STADIUM: "Ellipse",
}


def render_to_visio(data: SwimlaneData, output_path: str, visible: bool = False):
    visio = start_visio()
    basic_stencil, connector_stencil, stencil_masters, conn_master = open_stencils(visio)

    try:
        rect_master = stencil_masters.get("Rectangle")
        masters = {}
        for shape_type, master_name in MASTER_MAP.items():
            masters[shape_type] = stencil_masters.get(master_name)

        doc = visio.Documents.Add("")
        page = doc.Pages(1)

        _setup_page(page, data)
        page_height = page.PageSheet.Cells("PageHeight").Result("")

        def vy(layout_y: float) -> float:
            return page_height - layout_y

        # 1. Lane header boxes (role names at top of each column)
        for lane in data.lanes:
            if lane.x is None:
                continue
            _draw_lane_header(page, lane, rect_master, vy)

        # 2. Lane borders (vertical separators, no fill)
        if data.lanes:
            _draw_lane_borders(page, data, page_height, vy)

        # 3. Nodes
        shapes = {}
        for node in data.nodes:
            if node.x is None or node.y is None:
                continue
            shape = _draw_node(page, node, masters, vy)
            shapes[node.id] = shape

        # 4. Edges
        for edge in data.edges:
            src_shape = shapes.get(edge.source)
            tgt_shape = shapes.get(edge.target)
            if src_shape and tgt_shape:
                _draw_edge(page, src_shape, tgt_shape, edge.label, conn_master)

        abs_path = os.path.abspath(output_path)
        doc.SaveAs(abs_path)
    finally:
        close_visio(visio, doc, [basic_stencil, connector_stencil], visible)


def _setup_page(page, data: SwimlaneData):
    if not data.lanes:
        page.PageSheet.Cells("PageWidth").FormulaU = "11 in"
        page.PageSheet.Cells("PageHeight").FormulaU = "8.5 in"
        return

    n_lanes = len(data.lanes)
    # Page width from lanes
    page_width = MARGIN_LEFT + n_lanes * LANE_WIDTH + MARGIN_RIGHT

    # Page height from bottommost node
    valid_nodes = [n for n in data.nodes if n.y is not None and n.height]
    if valid_nodes:
        max_y = max(n.y + n.height / 2 for n in valid_nodes)
        page_height = max_y + MARGIN_BOTTOM
    else:
        page_height = MARGIN_TOP + LANE_LABEL_HEIGHT + 4.0

    page_width = min(page_width, 50)
    page_height = min(page_height, 50)

    page.PageSheet.Cells("PageWidth").FormulaU = f"{page_width:.2f} in"
    page.PageSheet.Cells("PageHeight").FormulaU = f"{page_height:.2f} in"


def _draw_lane_borders(page, data: SwimlaneData, page_height: float, vy):
    """Draw lane column borders — no fill, just vertical separators."""
    top = 0.3
    bottom = page_height - 0.3

    first_lane = data.lanes[0]
    last_lane = data.lanes[-1]
    left = first_lane.x or 0
    right = (last_lane.x or 0) + LANE_WIDTH

    # Draw left and right outer borders
    page.DrawLine(left, vy(top), left, vy(bottom))
    page.DrawLine(right, vy(top), right, vy(bottom))

    # Draw horizontal borders at top and bottom of header area
    header_bottom = MARGIN_TOP + LANE_LABEL_HEIGHT
    page.DrawLine(left, vy(top), right, vy(top))
    page.DrawLine(left, vy(header_bottom), right, vy(header_bottom))

    # Draw vertical separators between lanes
    for i in range(1, len(data.lanes)):
        lane = data.lanes[i]
        sep_x = lane.x or 0
        line = page.DrawLine(sep_x, vy(header_bottom), sep_x, vy(bottom))
        # Dashed separator between lanes
        line.Cells("LinePattern").FormulaU = "2"


def _draw_lane_header(page, lane, master, vy):
    """Draw role name header at the top of each lane column."""
    x = lane.x + LANE_WIDTH / 2
    y = MARGIN_TOP + LANE_LABEL_HEIGHT / 2

    shape = page.Drop(master, x, vy(y))
    shape.Cells("Width").FormulaU = f"{LANE_WIDTH:.4f} in"
    shape.Cells("Height").FormulaU = f"{LANE_LABEL_HEIGHT:.4f} in"
    shape.Text = lane.label
    shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
    shape.Cells("Char.Size").FormulaU = f"{FONT_SIZE_TITLE} pt"
    shape.Cells("Char.Color").FormulaU = rgb_to_visio(HEADER_TEXT_COLOR)
    shape.Cells("Para.HorzAlign").FormulaU = "1"
    shape.Cells("FillForegnd").FormulaU = rgb_to_visio(HEADER_BG_COLOR)
    shape.Cells("LineColor").FormulaU = rgb_to_visio(10066329)  # #999999


def _draw_node(page, node, masters: dict, vy):
    master = masters.get(node.shape) or masters.get(NodeShape.ROUNDED)

    shape = page.Drop(master, node.x, vy(node.y))
    if node.width:
        shape.Cells("Width").FormulaU = f"{node.width:.4f} in"
    if node.height:
        shape.Cells("Height").FormulaU = f"{node.height:.4f} in"

    shape.Text = node.label
    shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
    shape.Cells("Char.Size").FormulaU = f"{FONT_SIZE_NODE} pt"
    shape.Cells("Para.HorzAlign").FormulaU = "1"

    fill_color, text_color = _node_colors(node.shape)
    shape.Cells("FillForegnd").FormulaU = rgb_to_visio(fill_color)
    shape.Cells("Char.Color").FormulaU = rgb_to_visio(text_color)

    if node.shape == NodeShape.STADIUM:
        shape.Cells("LineColor").FormulaU = rgb_to_visio(START_END_COLOR)
        shape.Cells("LineWeight").FormulaU = "0 pt"
    elif node.shape == NodeShape.DIAMOND:
        shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)
    else:
        shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)

    return shape


def _node_colors(shape: NodeShape) -> tuple[int, int]:
    if shape == NodeShape.STADIUM:
        return START_END_COLOR, 16777215  # Green fill, white text
    if shape == NodeShape.DIAMOND:
        return DIAMOND_COLOR, 0  # Yellow fill, black text
    return 16777215, 0  # White fill, black text


def _draw_edge(page, src_shape, tgt_shape, label: str, conn_master):
    connector = page.Drop(conn_master, 0, 0)

    try:
        # Glue to connection points: source bottom (X1/Y1) -> target top (X3/Y3)
        connector.Cells("BeginX").GlueTo(src_shape.Cells("Connections.X1"))
        connector.Cells("BeginY").GlueTo(src_shape.Cells("Connections.Y1"))
        connector.Cells("EndX").GlueTo(tgt_shape.Cells("Connections.X3"))
        connector.Cells("EndY").GlueTo(tgt_shape.Cells("Connections.Y3"))
    except Exception:
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

    connector.Cells("LinePattern").FormulaU = "1"
    connector.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)
    connector.Cells("EndArrow").FormulaU = "4"

    connector.Cells("LineWeight").FormulaU = "1.5 pt"

    if label:
        connector.Text = label
        connector.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
        connector.Cells("Char.Size").FormulaU = f"{FONT_SIZE_LABEL} pt"
        connector.Cells("Char.Color").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)
        connector.Cells("Para.HorzAlign").FormulaU = "1"
