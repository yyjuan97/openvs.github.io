---
name: openvs-visio
description: Create editable Visio .vsdx diagrams locally from text or images. Use when the user asks to generate a Visio flowchart, sequence, composition, component, architecture, or swimlane diagram, or to convert a diagram screenshot into an editable Visio file. Windows with Microsoft Visio only.
---

# OpenVS —— 文本/图片转 Visio（纯本地，一步直出）

你负责解析（文本理解/看图）产出 JSON；脚本负责校验、布局、调用本机 Visio 生成 .vsdx。**全程一次命令完成，不要分步确认。**

## 环境假设

默认环境就绪（Windows + Visio + 依赖已装）。**不要预先检查、不要询问环境、不要先跑 pip**，直接执行命令；只有命令因缺依赖/缺 Visio 报错时，才按报错处理一次。

## 流程 A：文本 → Visio（一条命令）

1. 根据描述选类型：`flowchart` / `sequence` / `composition` / `component` / `architecture` / `swimlane`（默认 flowchart，拿不准才读 [references/diagram-types.md](references/diagram-types.md)）。
2. 读**对应那一个**规范文件 `references/parse-prompts/<类型>.txt`，按其中格式生成 JSON。
3. JSON 写入系统临时目录的文件（如 `%TEMP%\openvs_<类型>.json`），然后**直接执行正式渲染**——脚本内部会先校验再开 Visio，JSON 不合法会以退出码 3 失败且不会启动 Visio：

```
python <skill路径>/scripts/generate.py --type flowchart --json <临时json> -o <用户的输出路径>.vsdx
```

4. 成功后**删除临时 JSON**，只把 .vsdx 交付用户。
5. 仅当退出码 3（JSON 错误）：读 stderr 的字段/ID 提示，修正 JSON 重跑，最多 2 次；仍失败再报告。`--dry-run` 只用于调试，正常流程不要用。

## 流程 B：图片 → Visio（一条命令）

1. 看图，按 [references/image-schema.md](references/image-schema.md) 产出 JSON，写入临时文件。关键纪律：
   - 先确定图片像素宽高，顶层必带 `image_aspect`（宽/高），渲染器据此自动选横向/纵向/正方形页面，防止图形被拉扁
   - 坐标以**图片左上角为原点、y 向下**，`x/y` 是形状**左上角**（不是中心），直接按「像素位置 ÷ 图片总宽/高」换算
   - **只填看得清的内容**：形状、文字、连接关系必填；颜色类看不清一律省略（禁止猜颜色）；`font_size` 一律省略（渲染器按形状高度自动估算）
2. 直接渲染：

```
python <skill路径>/scripts/render_image.py --json <临时json> -o <用户的输出路径>.vsdx
```

3. 成功后删除临时 JSON。退出码 3 时按 stderr 修正，最多 2 次。

## 行为准则（重要）

- **不要向用户提问确认**：图表类型、措辞、节点命名由你按常识直接决定，一次做完。只有用户连要画什么都没说时才追问。
- **忠实转换，保持精简**：只画原文/原图里有的内容，绝不添加原文没有的节点、分组、备注、装饰；能合并的细碎步骤合并，单图节点一般 ≤20 个。
- 输出路径默认放用户当前工作目录，文件名按图表内容自取中文名；用户指定了路径就用指定的。
- 一次生成结束前不要启动第二个渲染（Visio COM 单实例）。
- 除临时 JSON 和最终 .vsdx 外，不创建任何文件（不写 README、日志、说明文档）。

## 退出码

- 0 成功 → 报告 .vsdx 绝对路径和节点数
- 3 JSON 数据/语法错误 → 自行修正重试，不打扰用户（≤2 次）
- 1 其他错误（Visio/COM/dot）→ 把 stderr 关键行报告用户；若是 Visio 僵尸进程导致，结束 Visio 进程后重试一次

## 边界

纯本地执行，无网络/无 Key；只生成新 .vsdx，不编辑已有文件，不输出其他格式；仅 Windows + Visio。
