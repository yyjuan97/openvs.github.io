import os

from common.visio_utils import start_visio, open_stencils, close_visio, rgb_to_visio
from component.models import ComponentData, InterfaceType

DEFAULT_FONT = "Microsoft YaHei"
DEFAULT_FONT_SIZE = 10  # pt
DEFAULT_FONT_SIZE_SMALL = 8  # pt for interfaces and tag
DEFAULT_LINE_COLOR = 0  # Black
TAG_COLOR = 8421504  # Gray RGB(128,128,128)
PROVIDED_COLOR = 32768  # Green RGB(0,128,0)
REQUIRED_COLOR = 8388608  # Dark red RGB(0,0,128)
DEP_LINE_COLOR = 8421504  # Gray for dependency lines


def render_to_visio(data: ComponentData, output_path: str, visible: bool = False):
    """Render ComponentData to a Visio document as a component diagram."""
    visio = start_visio()
    basic_stencil, connector_stencil, stencil_masters, conn_master = open_stencils(visio)

    try:
        rect_master = stencil_masters.get("Rectangle")

        doc = visio.Documents.Add("")
        page = doc.Pages(1)

        # Setup page dimensions
        _setup_page(page, data)

        # Draw dependency connectors first (behind components)
        shapes = {}
        for dep in data.dependencies:
            src = data.get_component(dep.from_id)
            tgt = data.get_component(dep.to_id)
            if not src or not tgt or src.x is None or tgt.x is None:
                continue
            # We need shapes for glue, so draw components first then connectors
            # Actually, let's draw components first, then connectors with glue

        # Draw component boxes
        for comp in data.components:
            if comp.x is None or comp.y is None:
                continue
            shape = _draw_component(page, comp, data, rect_master)
            shapes[comp.id] = shape

        # Draw dependency connectors
        for dep in data.dependencies:
            src_shape = shapes.get(dep.from_id)
            tgt_shape = shapes.get(dep.to_id)
            if src_shape and tgt_shape:
                _draw_dependency(page, src_shape, tgt_shape, dep.label, conn_master)

        abs_path = os.path.abspath(output_path)
        doc.SaveAs(abs_path)
    finally:
        close_visio(visio, doc, [basic_stencil, connector_stencil], visible)


def _setup_page(page, data: ComponentData):
    """Adjust page size based on component positions."""
    valid = [c for c in data.components if c.x is not None and c.y is not None]
    if not valid:
        page.PageSheet.Cells("PageWidth").FormulaU = "11 in"
        page.PageSheet.Cells("PageHeight").FormulaU = "8.5 in"
        return

    margin = 2.0
    min_x = min(c.x - c.width / 2 for c in valid)
    max_x = max(c.x + c.width / 2 for c in valid)
    min_y = min(c.y - c.height / 2 for c in valid)
    max_y = max(c.y + c.height / 2 for c in valid)

    page_width = min((max_x - min_x) + 2 * margin, 50)
    page_height = min((max_y - min_y) + 2 * margin, 50)

    page.PageSheet.Cells("PageWidth").FormulaU = f"{page_width:.2f} in"
    page.PageSheet.Cells("PageHeight").FormulaU = f"{page_height:.2f} in"


def _draw_component(page, comp, data: ComponentData, master) -> object:
    """Draw a component box with name, tag, and interface lists."""
    shape = page.Drop(master, comp.x, comp.y)
    shape.Cells("Width").FormulaU = f"{comp.width:.4f} in"
    shape.Cells("Height").FormulaU = f"{comp.height:.4f} in"

    # Build text content
    text_parts = [f"«component»", comp.label]

    provided = data.get_provided_interfaces(comp.id)
    required = data.get_required_interfaces(comp.id)

    if required:
        text_parts.append("──需求──")
        for iface in required:
            text_parts.append(iface.label)

    if provided:
        text_parts.append("──提供──")
        for iface in provided:
            text_parts.append(iface.label)

    shape.Text = "\n".join(text_parts)
    shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
    shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE} pt"
    shape.Cells("FillForegnd").FormulaU = rgb_to_visio(16777215)  # White
    shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)
    shape.Cells("Para.HorzAlign").FormulaU = "1"

    return shape


def _draw_dependency(page, src_shape, tgt_shape, label: str, conn_master):
    """Draw a dashed dependency arrow between two components."""
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

    connector.Cells("LinePattern").FormulaU = "2"  # Dashed
    connector.Cells("EndArrow").FormulaU = "2"  # Open arrow
    connector.Cells("LineColor").FormulaU = rgb_to_visio(DEP_LINE_COLOR)

    if label:
        connector.Text = label
        connector.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
        connector.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE_SMALL} pt"
        connector.Cells("Para.HorzAlign").FormulaU = "1"
