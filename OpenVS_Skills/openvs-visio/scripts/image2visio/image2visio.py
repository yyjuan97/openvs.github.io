"""Image analysis JSON -> Visio .vsdx renderer (pure local, no cloud).

输入是符合 OpenVS 图片分析 schema 的 JSON（diagram_type / background_color /
title / shapes / connections / floating_texts），本模块负责连接线坐标修正
与 Visio COM 渲染，不包含任何联网分析代码。
"""
import io
import json
import sys
import traceback
from pathlib import Path

# Windows 控制台默认使用 GBK，这里强制 UTF-8 输出中文
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

try:
    import win32com.client
except ImportError:
    print("[ERROR] missing pywin32, run: pip install pywin32")
    sys.exit(1)

# ============================================================
#  配置管理
# ============================================================

DEFAULT_CONFIG = {
    "page_width": 11.0,
    "page_height": 8.5,
}


def load_config(config_path: str | None = None) -> dict:
    """加载配置文件，与默认配置合并"""
    config = DEFAULT_CONFIG.copy()
    if config_path and Path(config_path).exists():
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
    return config



# ============================================================
#  连接线修正
# ============================================================

def _is_container(shape: dict, all_shapes: list) -> bool:
    """判断 shape 是否是容器（完整包含其他形状）"""
    sx = shape.get("x", 0)
    sy = shape.get("y", 0)
    sw = shape.get("width", 0)
    sh = shape.get("height", 0)
    for other in all_shapes:
        if other is shape:
            continue
        ox = other.get("x", 0)
        oy = other.get("y", 0)
        ow = other.get("width", 0)
        oh = other.get("height", 0)
        if sx < ox and sx + sw > ox + ow and sy < oy and sy + sh > oy + oh:
            return True
    return False


def correct_connection_shape_ids(shapes: list, connections: list, threshold: float = 0.08) -> list:
    """
    根据连接线的几何端点与方向，校正 from_shape_id / to_shape_id。

    核心改进：
    - 使用点到形状边缘线段的完整二维距离。
    - 对水平/垂直线，用源形状中心作为线坐标（垂直方向投影）替换 AI 可能偏差
      的端点坐标，使目标搜索真正基于"同一直线"进行。
    - 容器惩罚：包含其他形状的矩形被当作端点时会增加惩罚，避免线条被吸附到容器。
    - 优先选择面积更小的形状，解决同一直线上容器与子形状竞争的问题。
    """
    if not shapes or not connections:
        return connections

    def shape_area(shape: dict) -> float:
        return shape.get("width", 0) * shape.get("height", 0)

    def point_in_shape(px: float, py: float, shape: dict) -> bool:
        sx = shape.get("x", 0)
        sy = shape.get("y", 0)
        sw = shape.get("width", 0)
        sh = shape.get("height", 0)
        return sx <= px <= sx + sw and sy <= py <= sy + sh

    def is_container(shape: dict) -> bool:
        return _is_container(shape, shapes)

    def dist_to_edge_segment(px: float, py: float, shape: dict, edge: str) -> float:
        """点 (px,py) 到形状指定边缘线段的最短距离"""
        sx = shape.get("x", 0)
        sy = shape.get("y", 0)
        sw = shape.get("width", 0)
        sh = shape.get("height", 0)
        if edge == "top":
            x1, y1, x2, y2 = sx, sy, sx + sw, sy
        elif edge == "bottom":
            x1, y1, x2, y2 = sx, sy + sh, sx + sw, sy + sh
        elif edge == "left":
            x1, y1, x2, y2 = sx, sy, sx, sy + sh
        elif edge == "right":
            x1, y1, x2, y2 = sx + sw, sy, sx + sw, sy + sh
        else:
            return float("inf")

        if x1 == x2 and y1 == y2:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

        if x1 == x2:  # 垂直线段
            t = (py - y1) / (y2 - y1) if (y2 - y1) != 0 else 0
            t = max(0.0, min(1.0, t))
            cx = x1
            cy = y1 + t * (y2 - y1)
        else:  # 水平线段
            t = (px - x1) / (x2 - x1) if (x2 - x1) != 0 else 0
            t = max(0.0, min(1.0, t))
            cx = x1 + t * (x2 - x1)
            cy = y1

        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def overall_dist(px: float, py: float, shape: dict) -> float:
        sx = shape.get("x", 0)
        sy = shape.get("y", 0)
        sw = shape.get("width", 0)
        sh = shape.get("height", 0)
        cx = max(sx, min(px, sx + sw))
        cy = max(sy, min(py, sy + sh))
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

    def pick_shape(px: float, py: float, dx: float, dy: float, endpoint: str,
                   guide_x: float | None = None, guide_y: float | None = None,
                   exclude_id: int | None = None) -> dict | None:
        # 根据线段方向，确定应匹配的形状边缘
        if endpoint == "start":
            if abs(dx) >= abs(dy):
                edge = "right" if dx >= 0 else "left"
            else:
                edge = "bottom" if dy >= 0 else "top"
        else:
            if abs(dx) >= abs(dy):
                edge = "left" if dx >= 0 else "right"
            else:
                edge = "top" if dy >= 0 else "bottom"

        candidates = []
        for shape in shapes:
            sid = shape.get("id")
            if sid == exclude_id:
                continue

            sx = shape.get("x", 0)
            sy = shape.get("y", 0)
            sw = shape.get("width", 0)
            sh = shape.get("height", 0)

            # 将引导坐标钳位到候选形状的对应维度范围内，确保搜索点真正落在
            # 该形状可能连接的直线位置上。钳位距离作为附加惩罚。
            clamp_dist = 0.0
            search_px, search_py = px, py
            if abs(dx) >= abs(dy):
                # 水平线：y 由 guide_y 决定
                if guide_y is not None:
                    clamped = max(sy, min(guide_y, sy + sh))
                    search_py = clamped
                    clamp_dist = abs(guide_y - clamped)
            else:
                # 垂直线：x 由 guide_x 决定
                if guide_x is not None:
                    clamped = max(sx, min(guide_x, sx + sw))
                    search_px = clamped
                    clamp_dist = abs(guide_x - clamped)

            ed = dist_to_edge_segment(search_px, search_py, shape, edge)
            # 候选条件：边缘距离足够近，或者点落在形状内部
            if ed > threshold and not point_in_shape(search_px, search_py, shape):
                continue

            # 容器惩罚：当点不在边缘上时，包含其他形状的矩形视为容器而非真实端点
            container_penalty = 0.15 if (is_container(shape) and ed > 0.001) else 0.0

            od = overall_dist(search_px, search_py, shape)
            area = shape_area(shape)
            candidates.append((ed + clamp_dist + container_penalty, area, od, shape))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][3]

    corrected = []
    for conn in connections:
        sx = conn.get("start_x", conn.get("startX"))
        sy = conn.get("start_y", conn.get("startY"))
        ex = conn.get("end_x", conn.get("endX"))
        ey = conn.get("end_y", conn.get("endY"))

        from_id = conn.get("from_shape_id")
        to_id = conn.get("to_shape_id")

        valid_coords = all(v is not None for v in (sx, sy, ex, ey))
        dx = (ex - sx) if valid_coords else 0.0
        dy = (ey - sy) if valid_coords else 0.0

        # 估算引导坐标：垂直线取 x 平均，水平线取 y 平均，
        # 用于起点校正时弥补 AI 单端坐标偏差。
        guide_x = (sx + ex) / 2 if valid_coords else None
        guide_y = (sy + ey) / 2 if valid_coords else None

        # 起点校正
        source = None
        if sx is not None and sy is not None:
            source = pick_shape(sx, sy, dx, dy, endpoint="start",
                                guide_x=guide_x, guide_y=guide_y)
            if source is not None:
                from_id = source.get("id")

        # 终点校正：使用源形状中心作为更稳定的引导坐标
        if ex is not None and ey is not None and from_id is not None:
            source_shape = source if (source is not None and source.get("id") == from_id) else None
            if source_shape is None:
                source_shape = next((s for s in shapes if s.get("id") == from_id), None)

            if source_shape is not None:
                if abs(dx) >= abs(dy):
                    guide_y = source_shape.get("y", 0) + source_shape.get("height", 0) / 2
                    guide_x = None
                else:
                    guide_x = source_shape.get("x", 0) + source_shape.get("width", 0) / 2
                    guide_y = None
            else:
                guide_x = sx
                guide_y = sy

            target = pick_shape(ex, ey, dx, dy, endpoint="end",
                                guide_x=guide_x, guide_y=guide_y, exclude_id=from_id)
            if target is not None:
                to_id = target.get("id")

        if from_id is None or to_id is None or from_id == to_id:
            continue

        new_conn = dict(conn)
        new_conn["from_shape_id"] = from_id
        new_conn["to_shape_id"] = to_id
        corrected.append(new_conn)

    # 去重：同一条线在正反向重复出现只保留一条
    def conn_key(conn):
        a = conn.get("from_shape_id")
        b = conn.get("to_shape_id")
        sx = conn.get("start_x", 0)
        sy = conn.get("start_y", 0)
        ex = conn.get("end_x", 0)
        ey = conn.get("end_y", 0)
        cx = (sx + ex) / 2
        cy = (sy + ey) / 2
        return (min(a, b), max(a, b), round(cx / 0.05), round(cy / 0.05))

    seen = set()
    deduped = []
    for conn in corrected:
        key = conn_key(conn)
        if key not in seen:
            seen.add(key)
            deduped.append(conn)

    return deduped


def refine_connections(shapes: list, connections: list, axis_tol: float = 0.06) -> list:
    """
    对 correct_connection_shape_ids 后的连接做几何层面的二次修正。

    核心规则：
    1. 删除起点/终点明显不在 from/to 形状上的无效连接（AI 坐标跑偏或幻觉）。
    2. 对近似垂直/水平的连线，将 target 修正为沿该直线方向第一个真正相交的形状，
       防止 AI 把本应终止在中间层的长线误指到最远处形状。
    """
    if not shapes or not connections:
        return connections

    shape_map = {s["id"]: s for s in shapes}

    def bounds(s):
        return (s["x"], s["y"], s["x"] + s["width"], s["y"] + s["height"])

    def area(s):
        return s.get("width", 0) * s.get("height", 0)

    def point_on_shape(px, py, s, tol=0.08):
        """点是否落在形状边缘附近或形状内部"""
        x1, y1, x2, y2 = bounds(s)
        # 内部
        if x1 <= px <= x2 and y1 <= py <= y2:
            return True
        # 到矩形最近点距离
        cx = max(x1, min(px, x2))
        cy = max(y1, min(py, y2))
        return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 <= tol

    def first_shape_on_vertical_line(line_x, y_start, y_end, source, target):
        """从 source 出发沿垂直方向，返回第一个与 line_x 相交的非容器形状"""
        direction = 1 if y_end >= y_start else -1
        candidates = []
        for s in shapes:
            if s is source:
                continue
            x1, y1, x2, y2 = bounds(s)
            if x1 - axis_tol <= line_x <= x2 + axis_tol:
                if direction > 0 and y2 >= y_start:
                    candidates.append((y1, s))
                elif direction < 0 and y1 <= y_start:
                    candidates.append((-y2, s))
        if not candidates:
            return target
        candidates.sort(key=lambda item: item[0])
        for _, s in candidates:
            if s is target:
                return target
            if not _is_container(s, shapes):
                return s
        return target

    def first_shape_on_horizontal_line(line_y, x_start, x_end, source, target):
        """从 source 出发沿水平方向，返回第一个与 line_y 相交的非容器形状"""
        direction = 1 if x_end >= x_start else -1
        candidates = []
        for s in shapes:
            if s is source:
                continue
            x1, y1, x2, y2 = bounds(s)
            if y1 - axis_tol <= line_y <= y2 + axis_tol:
                if direction > 0 and x2 >= x_start:
                    candidates.append((x1, s))
                elif direction < 0 and x1 <= x_start:
                    candidates.append((-x2, s))
        if not candidates:
            return target
        candidates.sort(key=lambda item: item[0])
        for _, s in candidates:
            if s is target:
                return target
            if not _is_container(s, shapes):
                return s
        return target

    refined = []
    for conn in connections:
        sx = conn.get("start_x", conn.get("startX"))
        sy = conn.get("start_y", conn.get("startY"))
        ex = conn.get("end_x", conn.get("endX"))
        ey = conn.get("end_y", conn.get("endY"))
        from_id = conn.get("from_shape_id")
        to_id = conn.get("to_shape_id")

        if None in (sx, sy, ex, ey) or from_id is None or to_id is None:
            continue

        source = shape_map.get(from_id)
        target = shape_map.get(to_id)
        if source is None or target is None:
            continue

        # 1. 有效性过滤：起点/终点必须落在对应形状上
        if not point_on_shape(sx, sy, source):
            print(f"  [WARN] 连接 {from_id}->{to_id} 起点({sx:.3f},{sy:.3f})不在源形状上，忽略")
            continue
        if not point_on_shape(ex, ey, target):
            print(f"  [WARN] 连接 {from_id}->{to_id} 终点({ex:.3f},{ey:.3f})不在目标形状上，忽略")
            continue

        dx = ex - sx
        dy = ey - sy
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            continue

        new_conn = dict(conn)

        # 2. 对垂直/水平线应用 first-shape 规则
        if abs(dy) > abs(dx) * 1.5:  # 近似垂直线
            line_x = (sx + ex) / 2
            new_target = first_shape_on_vertical_line(line_x, sy, ey, source, target)
            if new_target is not target:
                print(f"  [INFO] 连接 {from_id}->{to_id} 目标修正为 {from_id}->{new_target['id']}（沿线首个相交形状）")
                new_conn["to_shape_id"] = new_target["id"]
                new_conn["end_x"] = new_target["x"] + new_target["width"] / 2
                new_conn["end_y"] = new_target["y"] if ey >= sy else new_target["y"] + new_target["height"]
                target = new_target
                to_id = new_target["id"]

        elif abs(dx) > abs(dy) * 1.5:  # 近似水平线
            line_y = (sy + ey) / 2
            new_target = first_shape_on_horizontal_line(line_y, sx, ex, source, target)
            if new_target is not target:
                print(f"  [INFO] 连接 {from_id}->{to_id} 目标修正为 {from_id}->{new_target['id']}（沿线首个相交形状）")
                new_conn["to_shape_id"] = new_target["id"]
                new_conn["end_x"] = new_target["x"] if ex >= sx else new_target["x"] + new_target["width"]
                new_conn["end_y"] = new_target["y"] + new_target["height"] / 2
                target = new_target
                to_id = new_target["id"]

        # 3. 再次修正 source（防止 AI 把端点误分配到容器内部的子形状上）
        # 垂直/水平线也应把 source 设为沿该方向第一个相交形状
        if abs(dy) > abs(dx) * 1.5:
            line_x = (sx + ex) / 2
            new_source = first_shape_on_vertical_line(line_x, ey, sy, target, source)
            if new_source is not source and new_source is not target:
                print(f"  [INFO] 连接 {from_id}->{to_id} 源修正为 {new_source['id']}->{to_id}（沿线首个相交形状）")
                new_conn["from_shape_id"] = new_source["id"]
                new_conn["start_x"] = new_source["x"] + new_source["width"] / 2
                new_conn["start_y"] = new_source["y"] + new_source["height"] if sy >= ey else new_source["y"]

        elif abs(dx) > abs(dy) * 1.5:
            line_y = (sy + ey) / 2
            new_source = first_shape_on_horizontal_line(line_y, ex, sx, target, source)
            if new_source is not source and new_source is not target:
                print(f"  [INFO] 连接 {from_id}->{to_id} 源修正为 {new_source['id']}->{to_id}（沿线首个相交形状）")
                new_conn["from_shape_id"] = new_source["id"]
                new_conn["start_x"] = new_source["x"] + new_source["width"] if sx >= ex else new_source["x"]
                new_conn["start_y"] = new_source["y"] + new_source["height"] / 2

        refined.append(new_conn)

    return refined



# ============================================================
#  Visio 渲染
# ============================================================

def hex_to_rgb_visio(hex_str: str) -> str:
    """将十六进制颜色字符串转为 Visio RGB(r,g,b) 格式"""
    if not hex_str:
        return "RGB(0,0,0)"

    # 处理 rgb(r,g,b) 格式
    if hex_str.lower().startswith("rgb("):
        return hex_str.replace(" ", "")

    # 处理颜色名称
    color_map = {
        "black": "#000000", "white": "#FFFFFF", "red": "#FF0000",
        "green": "#00FF00", "blue": "#0000FF", "yellow": "#FFFF00",
        "cyan": "#00FFFF", "magenta": "#FF00FF", "gray": "#808080",
        "grey": "#808080", "orange": "#FFA500", "purple": "#800080",
        "pink": "#FFC0CB", "brown": "#A52A2A", "silver": "#C0C0C0",
        "gold": "#FFD700", "navy": "#000080", "teal": "#008080",
        "lime": "#00FF00", "maroon": "#800000", "olive": "#808000",
        "coral": "#FF7F50", "salmon": "#FA8072", "turquoise": "#40E0D0",
        "violet": "#EE82EE", "indigo": "#4B0082", "beige": "#F5F5DC",
        "ivory": "#FFFFF0", "khaki": "#F0E68C", "plum": "#DDA0DD",
        "orchid": "#DA70D6", "tan": "#D2B48C", "peru": "#CD853F",
    }

    hex_str_lower = hex_str.lower().strip()
    if hex_str_lower in color_map:
        hex_str = color_map[hex_str_lower]

    if not hex_str.startswith("#"):
        return "RGB(0,0,0)"

    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    try:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return f"RGB({r},{g},{b})"
    except (ValueError, IndexError):
        return "RGB(0,0,0)"


# AI 识别的形状类型 -> Visio「基本流程图形状」模具中的 Master 名称
VISIO_SHAPE_MAP = {
    "rectangle": "Process",
    "process": "Process",
    "rounded_rectangle": "Start/End",
    "terminator": "Start/End",
    "ellipse": "Start/End",
    "oval": "Start/End",
    "circle": "Start/End",
    "diamond": "Decision",
    "decision": "Decision",
    "parallelogram": "Data",
    "document": "Document",
    "storage": "Magnetic Disk",
    "hexagon": "Process",  # 基本流程图没有六边形，降级到 Process
    "cylinder": "Process",
    "can": "Process",
    "cloud": "Process",
    "trapezoid": "Process",
    "triangle": "Process",
    "isosceles_triangle": "Process",
    "right_triangle": "Process",
    "pentagon": "Process",
    "octagon": "Process",
    "star": "Process",
    "arrow_left": "Process",
    "arrow_right": "Process",
    "arrow_up": "Process",
    "arrow_down": "Process",
    "double_arrow": "Process",
    "callout": "Process",
    "none": "Process",
    "textbox": "Process",  # 文本框用 Process 然后去掉填充和边框
}


def get_visio_master_name(shape_type_str: str) -> str:
    """将 AI 类型字符串映射为 Visio 基本流程图模具中的 Master 名称"""
    shape_type_str = shape_type_str.lower().strip()
    return VISIO_SHAPE_MAP.get(shape_type_str, "Process")


def generate_visio(analysis: dict, output_path: str, config: dict):
    """
    根据分析结果生成可编辑 Visio 文件
    """
    page_width = config.get("page_width", 11.0)
    page_height = config.get("page_height", 8.5)

    # Validate analysis structure
    if not isinstance(analysis, dict):
        raise ValueError(f"analysis 必须是 dict，实际为 {type(analysis).__name__}")

    shapes_data = analysis.get("shapes", [])
    if not isinstance(shapes_data, list):
        raise ValueError(f"shapes 必须是 list，实际为 {type(shapes_data).__name__}")

    connections_data = analysis.get("connections", [])
    if not isinstance(connections_data, list):
        raise ValueError(f"connections 必须是 list，实际为 {type(connections_data).__name__}")

    print(f"[INFO] 分析结果: {len(shapes_data)} 个形状, {len(connections_data)} 个连接")

    # 可选：按原图宽高比自动选择页面方向，避免纵向图被横向画布拉伸变形
    # image_aspect = 原图宽/高；缺省（旧版 JSON）保持横向 11x8.5
    image_aspect = analysis.get("image_aspect")
    orientation = "横向（默认）"
    if isinstance(image_aspect, (int, float)) and image_aspect > 0:
        if image_aspect >= 1.15:
            page_width, page_height = 11.0, 8.5    # 横向图
            orientation = "横向"
        elif image_aspect <= 1 / 1.15:
            page_width, page_height = 8.5, 11.0    # 纵向图
            orientation = "纵向"
        else:
            page_width, page_height = 10.0, 10.0   # 近正方形
            orientation = "正方形"
    print(f"[INFO] 创建 Visio 页面: {page_width}\" x {page_height}\"（{orientation}）")

    # 启动 Visio

    # 启动 Visio
    try:
        visio = win32com.client.Dispatch("Visio.Application")
    except Exception as e:
        print(f"[ERROR] 无法启动 Visio: {e}")
        print("[ERROR] 请确保已安装 Microsoft Visio 并正确配置 COM 接口。")
        sys.exit(1)

    visio.Visible = True

    # 创建新文档（使用基本流程图模板）
    try:
        # 尝试使用基本流程图模板
        doc = visio.Documents.Add("Basic Flowchart.vst")
    except Exception:
        # 如果模板不可用，创建空白文档
        doc = visio.Documents.Add("")

    page = visio.ActivePage

    # 设置页面大小
    try:
        page.PageSheet.Cells("PageWidth").ResultIU = page_width
        page.PageSheet.Cells("PageHeight").ResultIU = page_height
    except Exception:
        pass  # 忽略页面大小设置失败

    # 获取基本流程图模具
    try:
        # 尝试获取基本流程图模具
        stencil = None
        for doc_item in visio.Documents:
            if "BASFLO" in doc_item.Name.upper() or "Basic Flowchart" in doc_item.Name:
                stencil = doc_item
                break

        if not stencil:
            # 尝试打开基本流程图模具
            try:
                stencil = visio.Documents.Open("BASFLO_U.VSS")
            except Exception:
                stencil = None
    except Exception:
        stencil = None

    # 获取 Connector Master
    connector_master = None
    if stencil:
        try:
            connector_master = stencil.Masters("Connector")
        except Exception:
            pass

    # 1. 创建所有形状
    shapes_data = analysis.get("shapes", [])
    shape_map = {}  # id -> Visio shape object

    print(f"[INFO] 创建 {len(shapes_data)} 个形状...")

    for shape_data in shapes_data:
        sid = shape_data.get("id")
        if sid is None:
            print(f"  [WARN] 形状缺少 id，跳过: {shape_data}")
            continue

        shape_type_str = shape_data.get("type", "rectangle")
        x = shape_data.get("x", 0.1)
        y = shape_data.get("y", 0.1)
        w = shape_data.get("width", 0.1)
        h = shape_data.get("height", 0.1)

        # 验证坐标值
        if not all(isinstance(v, (int, float)) for v in [x, y, w, h]):
            print(f"  [WARN] 形状 #{sid} 坐标值无效，跳过: x={x}, y={y}, w={w}, h={h}")
            continue

        # 将分数坐标转为英寸（Visio 默认单位）
        # Visio 的坐标系：原点 (0,0) 在左下角，Y 轴向上
        # AI 返回的坐标：原点 (0,0) 在左上角，Y 轴向下
        # 需要翻转 Y 轴
        left = x * page_width
        bottom = (1 - y - h) * page_height  # 翻转 Y 轴后计算底部位置
        width = max(w * page_width, 0.5)   # 最小宽度 0.5 英寸
        height = max(h * page_height, 0.3)  # 最小高度 0.3 英寸

        # 获取 Master 名称
        master_name = get_visio_master_name(shape_type_str)

        try:
            # 从模具获取 Master
            master = None
            if stencil:
                try:
                    master = stencil.Masters(master_name)
                except Exception:
                    # 如果找不到对应的 Master，使用 Process
                    try:
                        master = stencil.Masters("Process")
                    except Exception:
                        master = None

            if master:
                # 从模具放置形状（中心点坐标）
                shape = page.Drop(master, left + width / 2, bottom + height / 2)
            else:
                # 如果没有模具，使用 DrawRectangle 创建矩形
                shape = page.DrawRectangle(left, bottom, left + width, bottom + height)

            # 设置大小和位置
            shape.Cells("Width").ResultIU = width
            shape.Cells("Height").ResultIU = height
            shape.Cells("PinX").ResultIU = left + width / 2
            shape.Cells("PinY").ResultIU = bottom + height / 2

            # 设置填充色
            fill_color = shape_data.get("fill_color", "#FFFFFF")
            try:
                if fill_color and fill_color.lower() not in ("none", "transparent", "#ffffff", "#fff"):
                    shape.Cells("FillForegnd").FormulaU = hex_to_rgb_visio(fill_color)
                    shape.Cells("FillPattern").ResultIU = 1  # 实心填充
                elif fill_color and fill_color.lower() in ("none", "transparent"):
                    shape.Cells("FillPattern").ResultIU = 0  # 无填充
                else:
                    # 白色或默认情况：设置无填充，让形状透明
                    shape.Cells("FillPattern").ResultIU = 0  # 无填充
            except Exception as e:
                print(f"  [WARN] 形状 #{sid} 填充色设置失败: {e}")

            # 设置边框
            border_color = shape_data.get("border_color", "#000000")
            border_width = shape_data.get("border_width", 1.0)
            border_style = shape_data.get("border_style", "solid")

            if border_color and border_color.lower() not in ("none", "transparent"):
                shape.Cells("LineColor").FormulaU = hex_to_rgb_visio(border_color)
                shape.Cells("LineWeight").ResultIU = max(0.01, border_width / 72)  # pt 转为英寸

            # 设置边框样式
            if border_style == "dashed":
                shape.Cells("LinePattern").ResultIU = 2  # 虚线
            elif border_style == "dotted":
                shape.Cells("LinePattern").ResultIU = 3  # 点线
            else:
                shape.Cells("LinePattern").ResultIU = 1  # 实线

            # 设置文本
            text = shape_data.get("text", "")
            if text:
                shape.Text = text

                # 设置文字颜色
                text_color = shape_data.get("text_color", "#000000")
                if text_color:
                    shape.Cells("Char.Color").FormulaU = hex_to_rgb_visio(text_color)

                # 设置字体大小：缺省时按形状高度自动估算（文字约占形状高 45%），
                # 避免不同 Agent 目测 pt 值造成字号混乱
                font_size = shape_data.get("font_size")
                if not isinstance(font_size, (int, float)) or font_size <= 0:
                    font_size = round(max(8, min(24, height * 72 * 0.45)))
                shape.Cells("Char.Size").FormulaU = f"{font_size} pt"

                # 设置粗体
                font_bold = shape_data.get("font_bold", False)
                if font_bold:
                    shape.Cells("Char.Style").ResultIU = 1  # 粗体

                # 设置对齐方式
                text_alignment = shape_data.get("text_alignment", "center")
                if text_alignment == "left":
                    shape.Cells("Para.HorzAlign").ResultIU = 0
                elif text_alignment == "right":
                    shape.Cells("Para.HorzAlign").ResultIU = 2
                else:
                    shape.Cells("Para.HorzAlign").ResultIU = 1  # 居中

            # 如果是文本框类型，去掉填充和边框
            if shape_type_str.lower() == "textbox":
                shape.Cells("FillPattern").ResultIU = 0  # 无填充
                shape.Cells("LinePattern").ResultIU = 0  # 无边框

            shape_map[sid] = shape
            print(f"  [OK] 形状 #{sid}: {shape_type_str} \"{shape_data.get('text', '')[:30]}\"")

        except Exception as e:
            print(f"  [ERROR] 创建形状 #{sid} 失败: {e}")

    # 2. 创建连接
    connections_data = analysis.get("connections", [])
    print(f"[INFO] 创建 {len(connections_data)} 个连接...")

    for i, conn in enumerate(connections_data):
        try:
            from_id = conn.get("from_shape_id")
            to_id = conn.get("to_shape_id")

            if from_id is None or to_id is None:
                print(f"  [WARN] 连接 #{i} 缺少 from_shape_id 或 to_shape_id，跳过")
                continue

            if from_id not in shape_map or to_id not in shape_map:
                print(f"  [WARN] 连接 {from_id}->{to_id} 引用了不存在的形状，跳过")
                continue

            from_shape = shape_map[from_id]
            to_shape = shape_map[to_id]

            # 创建连接线：使用 DrawLine 精确控制起点/终点，避免 GlueTo 自动重路由
            connector = page.DrawLine(0, 0, 0, 0)

            try:
                # 读取页面尺寸（用于相对坐标 -> 绝对坐标）
                page_width = page.PageSheet.Cells("PageWidth").ResultIU
                page_height = page.PageSheet.Cells("PageHeight").ResultIU

                # AI 给出的坐标是相对图片的 0-1 分数；Visio 使用英寸，且 y 轴向上
                def rel_to_abs(x, y):
                    if x is None or y is None:
                        return None
                    return x * page_width, page_height - y * page_height

                # 获取形状在图像坐标系中的边界（来自 Visio 的绝对坐标反推）
                def visio_shape_bounds(shape):
                    px = shape.Cells("PinX").ResultIU / page_width
                    py = (page_height - shape.Cells("PinY").ResultIU) / page_height
                    w = shape.Cells("Width").ResultIU / page_width
                    h = shape.Cells("Height").ResultIU / page_height
                    return px - w / 2, py - h / 2, w, h

                fx, fy, fw, fh = visio_shape_bounds(from_shape)
                tx, ty, tw, th = visio_shape_bounds(to_shape)

                sx_rel = conn.get("start_x")
                sy_rel = conn.get("start_y")
                ex_rel = conn.get("end_x")
                ey_rel = conn.get("end_y")

                # 缺失坐标时退回到形状中心
                if sx_rel is None or sy_rel is None:
                    sx_rel = fx + fw / 2
                    sy_rel = fy + fh / 2
                if ex_rel is None or ey_rel is None:
                    ex_rel = tx + tw / 2
                    ey_rel = ty + th / 2

                dx_rel = ex_rel - sx_rel
                dy_rel = ey_rel - sy_rel

                # 根据实际画图思路：线条应精确连接两个形状的对应边缘。
                # 水平线：y 保持统一，x 从源左右边缘到目标左右边缘；
                # 垂直线：x 保持统一，y 从源顶底边缘到目标顶底边缘。
                # 固定坐标取源/目标形状边缘，浮动坐标钳位到两形状的重叠区间，
                # 最大限度复用 AI 给出的位置信息，同时保证直线与原始图一致。
                if abs(dx_rel) >= abs(dy_rel):
                    # 水平线
                    if dx_rel >= 0:
                        sx_rel = fx + fw
                        ex_rel = tx
                    else:
                        sx_rel = fx
                        ex_rel = tx + tw
                    y_overlap_low = max(fy, ty)
                    y_overlap_high = min(fy + fh, ty + th)
                    if y_overlap_low <= y_overlap_high:
                        if y_overlap_low <= sy_rel <= y_overlap_high:
                            mid_y = sy_rel
                        else:
                            mid_y = (y_overlap_low + y_overlap_high) / 2
                    else:
                        mid_y = ((fy + fh / 2) + (ty + th / 2)) / 2
                    sy_rel = ey_rel = mid_y
                else:
                    # 垂直线
                    if dy_rel >= 0:
                        sy_rel = fy + fh
                        ey_rel = ty
                    else:
                        sy_rel = fy
                        ey_rel = ty + th
                    x_overlap_low = max(fx, tx)
                    x_overlap_high = min(fx + fw, tx + tw)
                    if x_overlap_low <= x_overlap_high:
                        if x_overlap_low <= sx_rel <= x_overlap_high:
                            mid_x = sx_rel
                        else:
                            mid_x = (x_overlap_low + x_overlap_high) / 2
                    else:
                        mid_x = ((fx + fw / 2) + (tx + tw / 2)) / 2
                    sx_rel = ex_rel = mid_x

                # 转换回 Visio 绝对坐标并设置
                sx, sy = rel_to_abs(sx_rel, sy_rel)
                ex, ey = rel_to_abs(ex_rel, ey_rel)

                connector.Cells("BeginX").ResultIU = sx
                connector.Cells("BeginY").ResultIU = sy
                connector.Cells("EndX").ResultIU = ex
                connector.Cells("EndY").ResultIU = ey

            except Exception as e:
                print(f"  [WARN] 连接 {from_id}->{to_id} 坐标计算失败，使用中心点回退: {e}")
                sx = from_shape.Cells("PinX").ResultIU
                sy = from_shape.Cells("PinY").ResultIU
                ex = to_shape.Cells("PinX").ResultIU
                ey = to_shape.Cells("PinY").ResultIU
                connector.Cells("BeginX").ResultIU = sx
                connector.Cells("BeginY").ResultIU = sy
                connector.Cells("EndX").ResultIU = ex
                connector.Cells("EndY").ResultIU = ey

            # 设置线条样式
            line_color = conn.get("line_color", "#000000")
            line_width = conn.get("line_width", 1.0)
            line_style = conn.get("line_style", "solid")

            if line_color and line_color.lower() not in ("none", "transparent"):
                connector.Cells("LineColor").FormulaU = hex_to_rgb_visio(line_color)
            connector.Cells("LineWeight").ResultIU = max(0.01, line_width / 72)

            # 设置线条样式
            if line_style == "dashed":
                connector.Cells("LinePattern").ResultIU = 2
            elif line_style == "dotted":
                connector.Cells("LinePattern").ResultIU = 3
            else:
                connector.Cells("LinePattern").ResultIU = 1

            # 箭头
            has_arrow = conn.get("has_arrow", True)
            if has_arrow:
                connector.Cells("EndArrow").ResultIU = 1  # 箭头

            # 连接标签
            label = conn.get("label", "")
            if label:
                # 在连接线中点添加文本框
                from_x = from_shape.Cells("PinX").ResultIU
                from_y = from_shape.Cells("PinY").ResultIU
                to_x = to_shape.Cells("PinX").ResultIU
                to_y = to_shape.Cells("PinY").ResultIU
                mid_x = (from_x + to_x) / 2
                mid_y = (from_y + to_y) / 2

                label_shape = page.DrawRectangle(mid_x - 0.5, mid_y - 0.15, mid_x + 0.5, mid_y + 0.15)
                label_shape.Text = label
                label_shape.Cells("FillPattern").ResultIU = 0  # 无填充
                label_shape.Cells("LinePattern").ResultIU = 0  # 无边框
                label_shape.Cells("Char.Size").FormulaU = "10 pt"

            label_text = conn.get("label", "")
            if label_text:
                print(f"  [OK] 连接 #{i+1}: {from_id} -> {to_id} (标签: \"{label_text}\")")
            else:
                print(f"  [OK] 连接 #{i+1}: {from_id} -> {to_id}")

        except Exception as e:
            print(f"  [ERROR] 创建连接 #{i+1} 失败: {e}")

    # 3. 创建浮动文本
    floating_texts = analysis.get("floating_texts", [])
    print(f"[INFO] 创建 {len(floating_texts)} 个浮动文本...")

    for i, ft in enumerate(floating_texts):
        try:
            x = ft.get("x", 0.1)
            y = ft.get("y", 0.1)
            w = ft.get("width", 0.2)
            h = ft.get("height", 0.05)

            # 转换为英寸坐标
            left = x * page_width
            bottom = (1 - y - h) * page_height
            width = max(w * page_width, 0.5)
            height = max(h * page_height, 0.2)

            # 创建文本框
            text_shape = page.DrawRectangle(left, bottom, left + width, bottom + height)
            text_shape.Text = ft.get("text", "")

            # 无填充无边框
            text_shape.Cells("FillPattern").ResultIU = 0
            text_shape.Cells("LinePattern").ResultIU = 0

            # 设置文字样式
            color = ft.get("color", "#000000")
            if color:
                text_shape.Cells("Char.Color").FormulaU = hex_to_rgb_visio(color)

            font_size = ft.get("font_size")
            if not isinstance(font_size, (int, float)) or font_size <= 0:
                font_size = round(max(8, min(32, height * 72 * 0.6)))
            text_shape.Cells("Char.Size").FormulaU = f"{font_size} pt"

            font_bold = ft.get("font_bold", False)
            if font_bold:
                text_shape.Cells("Char.Style").ResultIU = 1

            # 设置对齐方式
            text_alignment = ft.get("text_alignment", "left")
            if text_alignment == "left":
                text_shape.Cells("Para.HorzAlign").ResultIU = 0
            elif text_alignment == "right":
                text_shape.Cells("Para.HorzAlign").ResultIU = 2
            else:
                text_shape.Cells("Para.HorzAlign").ResultIU = 1

            print(f"  [OK] 浮动文本 #{i+1}: \"{ft.get('text', '')[:30]}\"")

        except Exception as e:
            print(f"  [ERROR] 创建浮动文本 #{i+1} 失败: {e}")

    # 4. 添加标题
    title = analysis.get("title", "")
    if title:
        try:
            title_left = page_width * 0.1
            title_bottom = page_height * 0.95 - 0.5
            title_width = page_width * 0.8
            title_height = 0.5

            title_shape = page.DrawRectangle(title_left, title_bottom,
                                             title_left + title_width, title_bottom + title_height)
            title_shape.Text = title
            title_shape.Cells("FillPattern").ResultIU = 0
            title_shape.Cells("LinePattern").ResultIU = 0
            title_shape.Cells("Char.Size").FormulaU = "24 pt"
            title_shape.Cells("Char.Style").ResultIU = 1  # 粗体
            title_shape.Cells("Para.HorzAlign").ResultIU = 1  # 居中
        except Exception as e:
            print(f"  [WARN] 添加标题失败: {e}")

    # 保存文件
    try:
        # 确保输出路径以 .vsdx 结尾
        if not output_path.lower().endswith(".vsdx"):
            output_path = output_path.rsplit(".", 1)[0] + ".vsdx"

        # 使用绝对路径
        import os
        output_path = os.path.abspath(output_path)
        print(f"[INFO] 保存路径: {output_path}")

        doc.SaveAs(output_path)
        print(f"\n[SUCCESS] Visio 文件已保存: {output_path}")
        print(f"  形状: {len(shape_map)}/{len(shapes_data)}")
        print(f"  连接: {len(connections_data)}")
        print(f"  浮动文本: {len(floating_texts)}")
    except Exception as e:
        print(f"[ERROR] 保存 Visio 文件失败: {e}")
        traceback.print_exc()
        raise  # 重新抛出异常，让上层知道保存失败
    finally:
        # 关闭文档
        try:
            doc.Close()
        except Exception:
            pass
        # 退出 Visio
        try:
            visio.Quit()
        except Exception:
            pass


# ============================================================
#  JSON 导出（用于调试和半自动模式）
# ============================================================

def save_analysis_json(analysis: dict, output_path: str):
    """将分析结果保存为 JSON 文件（便于调试和手动编辑）"""
    json_path = output_path.rsplit(".", 1)[0] + "_analysis.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 分析结果已保存: {json_path}")


def load_analysis_json(json_path: str) -> dict:
    """从 JSON 文件加载分析结果（用于从 JSON 直接生成 Visio）"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
#  CLI 主入口
# ============================================================

