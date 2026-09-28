#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenVS Skill —— 结构化 JSON 转 Visio（本地布局 + 渲染，无任何联网）。

AI 解析由调用方（用户自己的 Agent）按 references/parse-prompts/<type>.txt 完成，
本脚本只负责: JSON -> 数据模型 -> 校验 -> 布局 -> Visio COM 渲染为 .vsdx。

用法:
    python generate.py --type flowchart --json data.json -o 流程图.vsdx
    python generate.py --type flowchart --json data.json --dry-run   # 只校验+布局，不启 Visio

支持: flowchart / sequence / composition / component / architecture / swimlane
运行环境: Windows + 已安装 Microsoft Visio（--dry-run 除外）。
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config  # noqa: F401,E402  确保 graphviz-bin 进入 PATH


class ValidationError(Exception):
    pass


# ---------------- JSON -> 数据模型 ----------------

def _enum(enum_cls, value, field, item_id):
    try:
        return enum_cls(value)
    except ValueError:
        raise ValidationError(f"{item_id}: {field} 值 '{value}' 无效，可选: {[e.value for e in enum_cls]}")


def build_flowchart(d):
    from flowchart.models import Node, Edge, FlowchartData, NodeShape
    data = FlowchartData()
    for n in d.get("nodes", []):
        data.nodes.append(Node(
            id=n["id"], label=n.get("label", ""),
            shape=_enum(NodeShape, n.get("shape", "rectangle"), "shape", n["id"]),
        ))
    for e in d.get("edges", []):
        data.edges.append(Edge(source=e["source"], target=e["target"], label=e.get("label", "")))
    return data


def build_sequence(d):
    from sequence.models import Participant, Message, Fragment, SequenceData, MessageType, FragmentType
    data = SequenceData()
    for p in d.get("participants", []):
        data.participants.append(Participant(id=p["id"], label=p.get("label", "")))
    for m in d.get("messages", []):
        data.messages.append(Message(
            id=m["id"], from_id=m["from_id"], to_id=m["to_id"], label=m.get("label", ""),
            msg_type=_enum(MessageType, m.get("msg_type", "sync"), "msg_type", m["id"]),
            fragment_id=m.get("fragment_id", ""),
        ))
    for f in d.get("fragments", []):
        data.fragments.append(Fragment(
            id=f["id"],
            frag_type=_enum(FragmentType, f.get("frag_type", "opt"), "frag_type", f["id"]),
            label=f.get("label", ""),
            start_msg_id=f.get("start_msg_id", ""), end_msg_id=f.get("end_msg_id", ""),
            participant_ids=f.get("participant_ids", []),
        ))
    return data


def build_composition(d):
    from composition.models import FuncNode, CompositionData
    data = CompositionData()
    for n in d.get("nodes", []):
        data.nodes.append(FuncNode(
            id=n["id"], label=n.get("label", ""),
            parent_id=n.get("parent_id"), level=int(n.get("level", 0)),
        ))
    return data


def build_component(d):
    from component.models import Component, Interface, Dependency, ComponentData, InterfaceType
    data = ComponentData()
    for c in d.get("components", []):
        data.components.append(Component(id=c["id"], label=c.get("label", "")))
    for i in d.get("interfaces", []):
        data.interfaces.append(Interface(
            id=i["id"], label=i.get("label", ""),
            iface_type=_enum(InterfaceType, i.get("iface_type", "provided"), "iface_type", i["id"]),
            component_id=i.get("component_id", ""),
        ))
    for dep in d.get("dependencies", []):
        data.dependencies.append(Dependency(
            id=dep["id"], from_id=dep["from_id"], to_id=dep["to_id"], label=dep.get("label", ""),
        ))
    return data


def build_architecture(d):
    from architecture.models import Layer, ArchComponent, ArchConnection, ArchData
    data = ArchData()
    for l in d.get("layers", []):
        data.layers.append(Layer(id=l["id"], label=l.get("label", ""), level=int(l.get("level", 0))))
    for c in d.get("components", []):
        data.components.append(ArchComponent(id=c["id"], label=c.get("label", ""), layer_id=c.get("layer_id", "")))
    for cn in d.get("connections", []):
        data.connections.append(ArchConnection(
            from_id=cn["from_id"], to_id=cn["to_id"], label=cn.get("label", ""),
        ))
    return data


def build_swimlane(d):
    from swimlane.models import Lane, SwimlaneNode, SwimlaneEdge, SwimlaneData, NodeShape
    data = SwimlaneData()
    for l in d.get("lanes", []):
        data.lanes.append(Lane(id=l["id"], label=l.get("label", "")))
    for n in d.get("nodes", []):
        data.nodes.append(SwimlaneNode(
            id=n["id"], label=n.get("label", ""), lane_id=n.get("lane_id", ""),
            shape=_enum(NodeShape, n.get("shape", "rectangle"), "shape", n["id"]),
        ))
    for e in d.get("edges", []):
        data.edges.append(SwimlaneEdge(source=e["source"], target=e["target"], label=e.get("label", "")))
    return data


BUILDERS = {
    "flowchart": (build_flowchart, "flowchart.layout_engine", "flowchart.renderer"),
    "sequence": (build_sequence, "sequence.layout_engine", "sequence.renderer"),
    "composition": (build_composition, "composition.layout_engine", "composition.renderer"),
    "component": (build_component, "component.layout_engine", "component.renderer"),
    "architecture": (build_architecture, "architecture.layout_engine", "architecture.renderer"),
    "swimlane": (build_swimlane, "swimlane.layout_engine", "swimlane.renderer"),
}


def run(diagram_type: str, json_path: str, output_path: str, dry_run: bool, visible: bool):
    import importlib

    if diagram_type not in BUILDERS:
        raise ValidationError(f"未知图表类型: {diagram_type}，可选: {list(BUILDERS)}")

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValidationError("JSON 根元素必须是对象 {…}")

    builder, l_mod, r_mod = BUILDERS[diagram_type]
    try:
        data = builder(raw)
    except KeyError as e:
        raise ValidationError(f"缺少必填字段: {e}（参见 references/parse-prompts/{diagram_type}.txt）")

    errors = data.validate()
    if errors:
        raise ValidationError("数据校验失败:\n  - " + "\n  - ".join(errors))

    print(f"[1/2] 布局计算（{diagram_type}"
          + ("，Graphviz dot）" if diagram_type in ("flowchart", "component") else "）"))
    layout_mod = importlib.import_module(l_mod)
    data = layout_mod.compute_layout(data)

    if dry_run:
        print("[dry-run] 校验与布局通过，未调用 Visio，未生成文件")
        return

    print("[2/2] 调用 Visio 生成 .vsdx ...")
    render_mod = importlib.import_module(r_mod)
    render_mod.render_to_visio(data, output_path, visible=visible)
    print(f"完成: {os.path.abspath(output_path)}")


def main():
    parser = argparse.ArgumentParser(
        description="OpenVS —— 结构化 JSON 生成 Visio 图表（.vsdx），纯本地执行")
    parser.add_argument("-t", "--type", required=True,
                        choices=list(BUILDERS.keys()), help="图表类型")
    parser.add_argument("-j", "--json", required=True, help="结构化 JSON 文件路径（UTF-8）")
    parser.add_argument("-o", "--output", default="output.vsdx", help="输出 .vsdx 路径")
    parser.add_argument("-v", "--visible", action="store_true", help="保留 Visio 窗口可见")
    parser.add_argument("--dry-run", action="store_true", help="只校验 JSON 并计算布局，不启动 Visio")
    args = parser.parse_args()

    try:
        run(args.type, args.json, args.output, args.dry_run, args.visible)
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
