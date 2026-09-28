from composition.models import CompositionData, FuncNode

# Layout constants (inches)
LEVEL_HEIGHT = 2.0       # minimum vertical distance between levels
LEVEL_GAP = 0.5          # gap between bottom of one level and top of next
SIBLING_SPACING = 0.3    # horizontal gap between sibling nodes
MARGIN_LEFT = 1.5
MARGIN_TOP = 1.0

# Node sizing
CHAR_WIDTH_IN = 0.18
LINE_HEIGHT_IN = 0.21
PADDING_X = 0.4
PADDING_Y = 0.24
PADDING_X_NARROW = 0.16  # narrow padding for vertical-text nodes
CHARS_PER_LINE = 10
MIN_NODE_WIDTH = 1.2
MIN_NODE_HEIGHT = 0.5
NARROW_NODE_WIDTH = 0.55  # single Chinese char width + narrow padding


def _estimate_node_size(label: str, is_root: bool) -> tuple[float, float]:
    """Estimate node width and height.

    Root node: horizontal text, normal width.
    Non-root nodes: vertical text (one char per line), narrow width.
    """
    if is_root:
        # Horizontal text layout
        lines = []
        for i in range(0, len(label), CHARS_PER_LINE):
            lines.append(label[i:i + CHARS_PER_LINE])

        text_width = max(len(line) for line in lines) * CHAR_WIDTH_IN
        text_height = len(lines) * LINE_HEIGHT_IN

        w = max(text_width + PADDING_X, MIN_NODE_WIDTH)
        h = max(text_height + PADDING_Y, MIN_NODE_HEIGHT)
        return w, h
    else:
        # Vertical text: one character per line, narrow width
        n_chars = len(label)
        h = max(n_chars * LINE_HEIGHT_IN + PADDING_Y, MIN_NODE_HEIGHT)
        w = NARROW_NODE_WIDTH
        return w, h


def _normalize_level_sizes(data: CompositionData):
    """Make all nodes at the same level share the same width and height (max of the level).
    Level is determined by tree depth from root, not the 'level' field.
    """
    from collections import defaultdict

    # Always recompute level from tree structure
    root = data.get_root()
    if root:
        _assign_levels(data, root, 0)

    level_nodes = defaultdict(list)
    for node in data.nodes:
        level_nodes[node.level].append(node)

    for level, nodes in level_nodes.items():
        max_w = max(n.width for n in nodes)
        max_h = max(n.height for n in nodes)
        for node in nodes:
            node.width = max_w
            node.height = max_h


def _assign_levels(data: CompositionData, node: FuncNode, level: int):
    """Recursively assign correct level values based on tree depth."""
    node.level = level
    for child in data.get_children(node.id):
        _assign_levels(data, child, level + 1)


def compute_layout(data: CompositionData) -> CompositionData:
    """Compute tree layout positions for all nodes.

    Two-pass algorithm:
    1. Bottom-up: calculate subtree width for each node
    2. Top-down: assign x,y coordinates based on subtree widths
    """
    # Pre-compute node sizes
    root = data.get_root()
    for node in data.nodes:
        is_root = node.parent_id is None
        w, h = _estimate_node_size(node.label, is_root)
        node.width = w
        node.height = h

    if not root:
        return data

    # Normalize sizes within each level (same width & height per level)
    _normalize_level_sizes(data)

    # Pass 1: bottom-up, compute subtree widths
    subtree_widths = {}
    _compute_subtree_widths(data, root, subtree_widths)

    # Pass 2: top-down, assign coordinates
    _assign_coordinates(data, root, MARGIN_LEFT, MARGIN_TOP, subtree_widths)

    return data


def _compute_subtree_widths(data: CompositionData, node: FuncNode, widths: dict) -> float:
    """Recursively compute the width each subtree occupies."""
    children = data.get_children(node.id)

    if not children:
        # Leaf node: width is just the node's own width
        widths[node.id] = node.width
        return node.width

    # Non-leaf: width = sum of children subtree widths + gaps between them
    total = 0.0
    for i, child in enumerate(children):
        child_w = _compute_subtree_widths(data, child, widths)
        total += child_w
        if i > 0:
            total += SIBLING_SPACING

    # Parent must be at least as wide as its own label
    widths[node.id] = max(total, node.width)
    return widths[node.id]


def _assign_coordinates(data: CompositionData, node: FuncNode, left: float, top: float, subtree_widths: dict):
    """Recursively assign x,y coordinates to nodes."""
    children = data.get_children(node.id)
    subtree_w = subtree_widths[node.id]

    # This node is centered over its subtree
    node.x = left + subtree_w / 2
    node.y = top

    if not children:
        return

    # Position children side by side under this node
    child_left = left
    # If subtree is wider than children total, center children under parent
    children_total = sum(subtree_widths[c.id] for c in children) + (len(children) - 1) * SIBLING_SPACING
    if children_total < subtree_w:
        child_left = left + (subtree_w - children_total) / 2

    # Dynamic level spacing: gap between this level bottom and next level top
    parent_half = node.height / 2
    child_half = max(c.height for c in children) / 2
    level_step = max(LEVEL_HEIGHT, parent_half + LEVEL_GAP + child_half)

    for child in children:
        _assign_coordinates(data, child, child_left, top + level_step, subtree_widths)
        child_left += subtree_widths[child.id] + SIBLING_SPACING
