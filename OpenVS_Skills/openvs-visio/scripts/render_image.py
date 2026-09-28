#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenVS Skill —— 图片分析 JSON 转 Visio（本地渲染，无任何联网）。

图片识别由调用方（用户自己的 Agent）看图完成，按 references/image-schema.md
产出结构化 JSON；本脚本负责: JSON -> 连接线坐标修正 -> Visio COM 渲染为 .vsdx。

用法:
    python render_image.py --json analysis.json -o 架构图.vsdx
    python render_image.py --json analysis.json --dry-run   # 只校验，不启 Visio

运行环境: Windows + 已安装 Microsoft Visio（--dry-run 除外）。
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

REQUIRED_SHAPE_FIELDS = ("id", "type", "x", "y", "width", "height", "text")
SHAPE_TYPES = {"rectangle", "rounded_rectangle", "diamond", "ellipse", "parallelogram",
               "document", "storage", "hexagon", "textbox"}
CONN_TYPES = {"straight", "elbow", "curved"}


class ValidationError(Exception):
    pass


def validate(analysis: dict) -> str:
    """校验分析 JSON，返回摘要描述；不合法则抛 ValidationError。"""
    if not isinstance(analysis, dict):
        raise ValidationError("JSON 根元素必须是对象 {…}")
    shapes = analysis.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        raise ValidationError("缺少非空的 shapes 数组（至少要识别出 1 个形状）")
    connections = analysis.get("connections", [])
    if not isinstance(connections, list):
        raise ValidationError("connections 必须是数组")

    ids = set()
    for s in shapes:
        for f in REQUIRED_SHAPE_FIELDS:
            if f not in s:
                raise ValidationError(f"shape 缺少必填字段 '{f}': {json.dumps(s, ensure_ascii=False)[:120]}")
        try:
            for f in ("x", "y", "width", "height"):
                float(s[f])
        except (TypeError, ValueError):
            raise ValidationError(f"shape id={s.get('id')}: x/y/width/height 必须是数字")
        if s["type"] not in SHAPE_TYPES:
            raise ValidationError(f"shape id={s['id']}: type '{s['type']}' 无效，可选: {sorted(SHAPE_TYPES)}")
        if s["id"] in ids:
            raise ValidationError(f"shape id 重复: {s['id']}")
        ids.add(s["id"])

    for c in connections:
        for f in ("from_shape_id", "to_shape_id", "type", "start_x", "start_y", "end_x", "end_y"):
            if f not in c:
                raise ValidationError(f"connection 缺少必填字段 '{f}': {json.dumps(c, ensure_ascii=False)[:120]}")
        if c["type"] not in CONN_TYPES:
            raise ValidationError(f"connection: type '{c['type']}' 无效，可选: {sorted(CONN_TYPES)}")
        if c["from_shape_id"] not in ids:
            raise ValidationError(f"connection from_shape_id '{c['from_shape_id']}' 在 shapes 中不存在")
        if c["to_shape_id"] not in ids:
            raise ValidationError(f"connection to_shape_id '{c['to_shape_id']}' 在 shapes 中不存在")

    floats = analysis.get("floating_texts", [])
    if not isinstance(floats, list):
        raise ValidationError("floating_texts 必须是数组")

    aspect = analysis.get("image_aspect")
    if aspect is not None and (not isinstance(aspect, (int, float)) or aspect <= 0):
        raise ValidationError("image_aspect（原图宽/高）必须是正数")
    if aspect:
        if aspect >= 1.15:
            orient = "横向页面 11x8.5"
        elif aspect <= 1 / 1.15:
            orient = "纵向页面 8.5x11"
        else:
            orient = "正方形页面 10x10"
    else:
        orient = "默认横向 11x8.5（未提供 image_aspect）"

    return (f"{len(shapes)} 个形状，{len(connections)} 条连接线，"
            f"{len(floats)} 个浮动文本；{orient}")


def run(json_path: str, output_path: str, dry_run: bool):
    import pythoncom
    from image2visio.image2visio import generate_visio, load_config

    with open(json_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    summary = validate(analysis)
    print(f"[1/2] 校验通过: {summary}")

    if dry_run:
        print("[dry-run] 校验通过，未调用 Visio，未生成文件")
        return

    print("[2/2] 调用 Visio 生成 .vsdx ...")
    pythoncom.CoInitialize()
    try:
        generate_visio(analysis, output_path, load_config())
    finally:
        pythoncom.CoUninitialize()
    print(f"完成: {os.path.abspath(output_path)}")


def main():
    parser = argparse.ArgumentParser(
        description="OpenVS —— 图片分析 JSON 渲染为 Visio 文件（.vsdx），纯本地执行")
    parser.add_argument("-j", "--json", required=True, help="图片分析 JSON 文件路径（UTF-8）")
    parser.add_argument("-o", "--output", default="output.vsdx", help="输出 .vsdx 路径")
    parser.add_argument("--dry-run", action="store_true", help="只校验 JSON，不启动 Visio")
    args = parser.parse_args()

    try:
        run(args.json, args.output, args.dry_run)
    except ValidationError as e:
        print(f"JSON 数据错误: {e}", file=sys.stderr)
        sys.exit(3)
    except json.JSONDecodeError as e:
        print(f"JSON 语法错误: {e}", file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"生成失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
