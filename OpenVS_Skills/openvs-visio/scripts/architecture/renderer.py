import os

from common.visio_utils import start_visio, open_stencils, close_visio, rgb_to_visio
from architecture.models import ArchData
from architecture.layout_engine import LAYER_LABEL_WIDTH, MARGIN_LEFT

DEFAULT_FONT = "Microsoft YaHei"
DEFAULT_FONT_SIZE = 14  # pt — layer labels
DEFAULT_FONT_SIZE_SMALL = 12  # pt — component labels
DEFAULT_LINE_COLOR = 0  # Black
LAYER_BORDER_COLOR = 6710886  # #666666
LABEL_TEXT_COLOR = 0  # Black


def render_to_visio(data: ArchData, output_path: str, visible: bool = False):
    """Render ArchData to a Visio document as a layered architecture diagram."""
    visio = start_visio()
    basic_stencil, connector_stencil, stencil_masters, conn_master = open_stencils(visio)

    try:
        rect_master = stencil_masters.get("Rectangle")

        doc = visio.Documents.Add("")
        page = doc.Pages(1)

        # Compute page dimensions
        if data.layers:
            last_layer = data.layers[-1]
            page_height = last_layer.y + last_layer.height + 1.0
            from architecture.layout_engine import _compute_page_width
            page_width = _compute_page_width(data)
        else:
            page_width = 11.0
            page_height = 8.5

        page.PageSheet.Cells("PageWidth").FormulaU = f"{page_width:.2f} in"
        page.PageSheet.Cells("PageHeight").FormulaU = f"{page_height:.2f} in"

        def vy(layout_y: float) -> float:
            return page_height - layout_y

        # Draw layer bands (no fill, just border)
        for i, layer in enumerate(data.layers):
            layer_shape = page.DrawRectangle(
                MARGIN_LEFT, vy(layer.y + layer.height),
                page_width - 0.3, vy(layer.y)
            )
            layer_shape.Cells("FillPattern").FormulaU = "0"  # No fill
            layer_shape.Cells("LineColor").FormulaU = rgb_to_visio(LAYER_BORDER_COLOR)
            layer_shape.Cells("LineWeight").FormulaU = "1 pt"

            # Layer label — centered vertically, no background
            label_y = vy(layer.y + layer.height / 2)

            label_shape = page.DrawRectangle(
                MARGIN_LEFT + 0.1, label_y + 0.22,
                MARGIN_LEFT + LAYER_LABEL_WIDTH - 0.1, label_y - 0.22
            )
            label_shape.Text = layer.label
            label_shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
            label_shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE} pt"
            label_shape.Cells("Char.Color").FormulaU = rgb_to_visio(LABEL_TEXT_COLOR)
            label_shape.Cells("FillPattern").FormulaU = "0"  # No fill
            label_shape.Cells("LinePattern").FormulaU = "0"  # No border
            label_shape.Cells("Para.HorzAlign").FormulaU = "1"

        # Draw components
        for comp in data.components:
            if comp.x is None or comp.y is None:
                continue

            shape = page.Drop(rect_master, comp.x, vy(comp.y))
            shape.Cells("Width").FormulaU = f"{comp.width:.4f} in"
            shape.Cells("Height").FormulaU = f"{comp.height:.4f} in"

            shape.Text = comp.label
            shape.Cells("Char.Font").FormulaU = f'"{DEFAULT_FONT}"'
            shape.Cells("Char.Size").FormulaU = f"{DEFAULT_FONT_SIZE_SMALL} pt"
            shape.Cells("Para.HorzAlign").FormulaU = "1"
            shape.Cells("FillPattern").FormulaU = "0"  # No fill
            shape.Cells("LineColor").FormulaU = rgb_to_visio(DEFAULT_LINE_COLOR)

        abs_path = os.path.abspath(output_path)
        doc.SaveAs(abs_path)
    finally:
        close_visio(visio, doc, [basic_stencil, connector_stencil], visible)
