from collections import defaultdict

from swimlane.models import NodeShape, SwimlaneData

# ============================================================
#  Layout constants — vertical swimlane layout
#  Lanes are vertical columns, role labels on top,
#  process steps flow top-to-bottom within each column
# ============================================================

# Swimlane geometry
LANE_WIDTH = 2.08         # ~200px / 96 — width of each lane column
LANE_LABEL_HEIGHT = 0.42  # ~40px / 96 — height of the role label at top
MARGIN_LEFT = 0.625       # ~60px / 96
MARGIN_TOP = 0.625        # ~60px / 96
MARGIN_RIGHT = 0.625      # ~60px / 96
MARGIN_BOTTOM = 0.625     # ~60px / 96
NODE_MIN_SPACING_Y = 1.0  # min vertical center-to-center distance between nodes
NODE_START_MARGIN_Y = 0.5 # start node top margin below lane header
CROSS_LANE_GAP_Y = 0.3   # extra vertical gap for cross-lane edges

# Node sizes (standard per spec)
NODE_START_DIAMETER = 0.42    # ~40px diameter circle
NODE_ACTIVITY_W = 1.25        # ~120px
NODE_ACTIVITY_H = 0.625       # ~60px
NODE_DIAMOND_W = 1.04         # ~100px diagonal
NODE_DIAMOND_H = 0.625        # ~60px diagonal

# Lane background colors — blue/gray alternating
LANE_COLOR_EVEN = 14408667    # Light blue
LANE_COLOR_ODD = 15790320     # Light gray


def compute_layout(data: SwimlaneData) -> SwimlaneData:
    """Compute vertical swimlane layout.

    Lanes are vertical columns arranged left-to-right.
    Role labels sit on top of each column.
    Nodes flow top-to-bottom within their lane.
    """
    # Pre-compute node sizes based on shape type
    for node in data.nodes:
        node.width, node.height = _node_size(node.shape)

    if not data.lanes:
        return data

    # Assign lane x positions — columns left-to-right, 0 gap
    current_x = MARGIN_LEFT
    for lane in data.lanes:
        lane.x = current_x
        lane.width = LANE_WIDTH
        lane.y = 0.0
        lane.height = 0.0  # full page height, set by renderer
        current_x += LANE_WIDTH

    # Assign node x — center of their lane column
    for node in data.nodes:
        lane = data.get_lane(node.lane_id)
        if lane and lane.x is not None:
            node.x = lane.x + LANE_WIDTH / 2

    # Topological sort for node y positions (top-to-bottom flow)
    _assign_node_y(data)

    return data


def _node_size(shape: NodeShape) -> tuple[float, float]:
    """Return (width, height) for each node shape per spec."""
    if shape == NodeShape.STADIUM:
        return NODE_START_DIAMETER, NODE_START_DIAMETER
    if shape == NodeShape.DIAMOND:
        return NODE_DIAMOND_W, NODE_DIAMOND_H
    if shape == NodeShape.ROUNDED:
        return NODE_ACTIVITY_W, NODE_ACTIVITY_H
    return NODE_ACTIVITY_W, NODE_ACTIVITY_H


def _assign_node_y(data: SwimlaneData):
    """Assign y coordinates using topological ordering.

    Each node's y = max(predecessor_y + spacing) across all incoming edges.
    Cross-lane edges add extra vertical gap.
    """
    node_map = {n.id: n for n in data.nodes}

    # Find back-edges using DFS cycle detection
    back_edge_set = _find_back_edges(data)
    forward_edges = [e for e in data.edges if (e.source, e.target) not in back_edge_set]

    # Topological sort (Kahn's algorithm) on acyclic graph
    in_degree = defaultdict(int)
    for node in data.nodes:
        in_degree[node.id] = 0
    for edge in forward_edges:
        in_degree[edge.target] += 1

    queue = [n.id for n in data.nodes if in_degree[n.id] == 0]
    sorted_ids = []

    while queue:
        queue.sort(key=lambda nid: data.lanes.index(data.get_lane(node_map[nid].lane_id)) if data.get_lane(node_map[nid].lane_id) else 0)
        nid = queue.pop(0)
        sorted_ids.append(nid)

        for edge in forward_edges:
            if edge.source == nid:
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(edge.target)

    # Safety net for any remaining nodes
    for node in data.nodes:
        if node.id not in set(sorted_ids):
            sorted_ids.append(node.id)

    # Starting y: below the lane header + margin
    body_top = MARGIN_TOP + LANE_LABEL_HEIGHT + NODE_START_MARGIN_Y

    # Assign y using ALL edges (including back-edges for spacing)
    all_predecessors = defaultdict(list)
    for edge in data.edges:
        all_predecessors[edge.target].append(edge.source)

    for nid in sorted_ids:
        node = node_map[nid]
        preds = all_predecessors[nid]

        if not preds:
            node.y = body_top
        else:
            max_y = 0.0
            for pid in preds:
                pred_node = node_map.get(pid)
                if pred_node and pred_node.y is not None:
                    pred_h = pred_node.height or NODE_ACTIVITY_H
                    candidate_y = pred_node.y + pred_h / 2 + NODE_MIN_SPACING_Y
                    max_y = max(max_y, candidate_y)
            node.y = max(max_y, body_top)


def _find_back_edges(data: SwimlaneData) -> set[tuple[str, str]]:
    """Find back-edges that create cycles using DFS."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n.id: WHITE for n in data.nodes}
    adj = defaultdict(list)
    for edge in data.edges:
        adj[edge.source].append(edge.target)

    back_edges = set()

    def dfs(node_id):
        color[node_id] = GRAY
        for neighbor in adj[node_id]:
            if color[neighbor] == GRAY:
                back_edges.add((node_id, neighbor))
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        color[node_id] = BLACK

    for node in data.nodes:
        if color[node.id] == WHITE:
            dfs(node.id)

    return back_edges
