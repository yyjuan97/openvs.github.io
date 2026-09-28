import os

from common.visio_utils import start_visio, open_stencils, close_visio, rgb_to_visio
from composition.layout_engine import MARGIN_LEFT, MARGIN_TOP, LEVEL_HEIGHT
from composition.models import CompositionData

DEFAULT_FONT = "Microsoft YaHei"
DEFAULT_FONT_SIZE = 10  # pt
DEFAULT_FONT_SIZE_SMALL = 9  # pt for non-root nodes
DEFAULT_LINE_COLOR = 0  # Black
NODE_FILL_COLOR = 16777215  # White


def render_to_visio(data: CompositionData, output_path: str, visible: bool = False):
    """Render CompositionData to a Visio document as a tree-structured composition diagram."""
    visio = start_visio()
    basic_stencil, connector_stencil, stencil_masters, conn_master = open_stencils(visio)

    try:
        rect_master = stencil_masters.get("Rectangle")

        doc = visio.Documents.Add("")
        page = doc.Pages(1)

        # Compute page dimensions
        if data.nodes and any(n.x is not None for n in data.nodes):
            valid = [n for n in data.nodes if n.x is not None and n.y is not None]
            max_x = max(n.x + n.width / 2 for n in valid)
            min_x = min(n.x - n.width / 2 for n in valid)
            max_y = max(n.y for n in valid)
            page_width = min((max_x - min_x) + 3.0, 50)
            page_height = min(max_y + 2.0, 50)
        else:
            page_width = 11.0
            page_height = 8.5

        page.PageSheet.Cells("PageWidth").FormulaU = f"{page_width:.2f} in"
        page.PageSheet.Cells("PageHeight").FormulaU = f"{page_height:.2f} in"

        # Y-flip function
        def vy(layout_y: float) -> float:
            return page_height - layout_y

        # Draw nodes first
        shapes = {}
        for node in data.nodes:
            if node.x is None or node.y is None:
                continue

            is_root = node.parent_id is None

            visio_x = node.x
            visio_y = vy(node.y)

            shape = page.Drop(rect_master, visio_x, visio_y)
            shape.Cells("Width").FormulaU = f"{node.width:.4f} in"
            shape.Cells("Height").FormulaU = f"{node.height:.4f} in"

            if is_root:
                # Root: horizontal text
                shape.Text = node.label
                shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
                shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE} pt"
            else:
                # Non-root: vertical text (one char per line via line breaks)
                shape.Text = "\n".join(node.label)
                shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
                shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE_SMALL} pt"

            shape.Cells("Para.HorzAlign").FormulaU = "1"
            shape.Cells("FillForegnd").FormulaU = rgb_to_visio(NODE_FILL_COLOR)
            shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)

            shapes[node.id] = shape

        # Draw connectors between parent and child nodes
        _draw_connectors_with_shapes(data, shapes, conn_master, page)

        abs_path = os.path.abspath(output_path)
        doc.SaveAs(abs_path)
    finally:
        close_visio(visio, doc, [basic_stencil, connector_stencil], visible)


def _draw_connectors_with_shapes(data: CompositionData, shapes: dict, conn_master, page):
    """Draw dynamic connectors glued between parent and child node shapes."""
    for node in data.nodes:
        if node.parent_id is None:
            continue
        child_shape = shapes.get(node.id)
        parent_shape = shapes.get(node.parent_id)
        if not child_shape or not parent_shape:
            continue

        connector = page.Drop(conn_master, 0, 0)

        try:
            # Glue to connection points: parent bottom (X1/Y1) -> child top (X3/Y3)
            connector.Cells("BeginX").GlueTo(parent_shape.Cells("Connections.X1"))
            connector.Cells("BeginY").GlueTo(parent_shape.Cells("Connections.Y1"))
            connector.Cells("EndX").GlueTo(child_shape.Cells("Connections.X3"))
            connector.Cells("EndY").GlueTo(child_shape.Cells("Connections.Y3"))
        except Exception:
            try:
                # Fallback: glue to PinX/PinY (1D glue, won't follow drag perfectly)
                connector.Cells("BeginX").GlueTo(parent_shape.Cells("PinX"))
                connector.Cells("EndX").GlueTo(child_shape.Cells("PinX"))
            except Exception:
                # Last resort: manual positioning
                src_x = parent_shape.Cells("PinX").Result("")
                src_y = parent_shape.Cells("PinY").Result("")
                tgt_x = child_shape.Cells("PinX").Result("")
                tgt_y = child_shape.Cells("PinY").Result("")
                connector.Cells("BeginX").FormulaU = f"{src_x}"
                connector.Cells("BeginY").FormulaU = f"{src_y}"
                connector.Cells("EndX").FormulaU = f"{tgt_x}"
                connector.Cells("EndY").FormulaU = f"{tgt_y}"

        connector.Cells("EndArrow").FormulaU = "0"
