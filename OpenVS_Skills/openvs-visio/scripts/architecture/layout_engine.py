from architecture.models import ArchData

# Layout constants (inches)
LAYER_GAP = 0.15              # 层带之间的间距
COMPONENT_HEIGHT = 0.6        # 组件框高度
COMPONENT_MIN_WIDTH = 1.2     # 组件框最小宽度
COMPONENT_PADDING_X = 0.4     # 组件框水平内边距
CHAR_WIDTH_IN = 0.18          # 单字宽度
COMPONENT_SPACING = 0.3       # 同层组件之间的间距
COMPONENT_GAP = 0.1           # 组件与边框、组件行之间的间距
MAX_SINGLE_ROW = 5            # 单行最大组件数，超过则分两行
MARGIN_TOP = 0.5              # 顶部边距
MARGIN_BOTTOM = 0.5           # 底部边距
MARGIN_LEFT = 0.5             # 左边距
MARGIN_RIGHT = 0.5            # 右边距
LAYER_LABEL_WIDTH = 2.2       # 层标签区域宽度（预留10个字）
COMPONENT_EDGE_GAP = 0.3     # 最左/最右节点到边界的空白


def _estimate_component_width(label: str) -> float:
    """Estimate component box width based on text length."""
    text_width = len(label) * CHAR_WIDTH_IN + COMPONENT_PADDING_X
    return max(text_width, COMPONENT_MIN_WIDTH)


def compute_layout(data: ArchData) -> ArchData:
    """Compute layered layout: wide band-style layers with components centered inside."""
    if not data.layers:
        return data

    data.layers.sort(key=lambda l: l.level)

    # Pre-compute component sizes
    for comp in data.components:
        comp.width = _estimate_component_width(comp.label)
        comp.height = COMPONENT_HEIGHT

    # Compute page width from max layer content
    page_width = _compute_page_width(data)

    # Assign layer and component positions
    current_y = MARGIN_TOP
    for layer in data.layers:
        layer_comps = data.get_components_by_layer(layer.id)

        # Decide single or double row
        n = len(layer_comps)
        is_double_row = n > MAX_SINGLE_ROW

        if is_double_row:
            # gap top + comp + gap + comp + gap bottom
            layer.height = 3 * COMPONENT_GAP + 2 * COMPONENT_HEIGHT
        else:
            # gap top + comp + gap bottom
            layer.height = 2 * COMPONENT_GAP + COMPONENT_HEIGHT

        layer.y = current_y

        # Content area
        content_left = LAYER_LABEL_WIDTH
        content_right = page_width - MARGIN_RIGHT
        content_width = content_right - content_left

        if layer_comps:
            if is_double_row:
                mid = (n + 1) // 2
                row1 = layer_comps[:mid]
                row2 = layer_comps[mid:]

                # Row 1 center: gap + comp_h/2 from top
                row1_y = current_y + COMPONENT_GAP + COMPONENT_HEIGHT / 2
                # Row 2 center: gap + comp_h + gap + comp_h/2 from top
                row2_y = current_y + 2 * COMPONENT_GAP + COMPONENT_HEIGHT + COMPONENT_HEIGHT / 2

                _position_row(row1, content_left, content_width, row1_y)
                _position_row(row2, content_left, content_width, row2_y)
            else:
                center_y = current_y + COMPONENT_GAP + COMPONENT_HEIGHT / 2
                _position_row(layer_comps, content_left, content_width, center_y)

        current_y += layer.height + LAYER_GAP

    return data


def _position_row(comps: list, content_left: float, content_width: float, center_y: float):
    """Position a row of components, stretching widths to fill the row evenly."""
    n = len(comps)
    if n == 0:
        return

    # Available width for components (minus edge gaps and spacing)
    usable = content_width - 2 * COMPONENT_EDGE_GAP
    total_spacing = (n - 1) * COMPONENT_SPACING if n > 1 else 0
    total_comp_width = usable - total_spacing

    # Distribute width proportionally
    min_total = sum(c.width for c in comps)
    if total_comp_width < min_total:
        total_comp_width = min_total

    ratio = total_comp_width / min_total if min_total > 0 else 1
    actual_widths = [c.width * ratio for c in comps]
    actual_total = sum(actual_widths) + total_spacing

    start_x = content_left + COMPONENT_EDGE_GAP + (usable - actual_total) / 2

    for i, comp in enumerate(comps):
        comp.width = actual_widths[i]
        comp.x = start_x + comp.width / 2
        comp.y = center_y
        start_x += comp.width + COMPONENT_SPACING


def _compute_page_width(data: ArchData) -> float:
    """Compute page width — fixed reasonable width for architecture diagrams."""
    # With auto-stretching components, use a reasonable fixed width
    # Ensure at least enough for label + a few components
    max_comps = max((len(data.get_components_by_layer(l.id)) for l in data.layers), default=0)
    if max_comps > MAX_SINGLE_ROW:
        width = 14.0
    elif max_comps > 3:
        width = 12.0
    else:
        width = 11.0
    return min(width, 50)
