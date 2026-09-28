# OpenVS

> One sentence, one diagram. Generate professional Visio charts from natural language descriptions or images.

[中文](README_CN.md) | [English](README.md)

---

## ✨ Overview

**OpenVS** is a natural language and image-driven Visio diagram generation tool. Simply input a natural language description, or upload a sketch, screenshot, or whiteboard photo, and AI will automatically understand the semantics, recognize the image content, and generate professional, editable `.vsdx` files.

No drawing skills required. No manual dragging. Just press Enter.

---

## 🚀 Features

| Feature | Description |
|---------|-------------|
| **Image to Visio** | Upload sketches, screenshots, or whiteboard photos; AI automatically recognizes and converts them into standard Visio diagrams |
| **Flowchart** | Break down workflows into clear steps and decision branches |
| **Sequence Diagram** | Show interactions and message exchanges between multiple roles over time |
| **Functional Decomposition** | Decompose system modules into hierarchical tree structures |
| **Relationship Diagram** | Describe interface provision and dependency relationships between components |
| **Architecture Diagram** | Present system layers and constituent modules in a layered structure |
| **Swimlane Diagram** | Organize cross-departmental collaboration by roles in swimlanes |

---

## 🛠️ Quick Start

1. Visit the website: https://yyjuan97.github.io/openvs.github.io/
2. Click "Download" to get the client
3. Double-click the exe to launch, input a natural language description, and press Enter to generate

### Requirements

- Windows 10 or later
- Microsoft Visio 2016 or later installed
- No Python installation required — the exe bundles its own runtime
- Supports both text description and image upload input methods
- Internet connection required for generating flowcharts / relationship diagrams / image-to-Visio (AI-powered)

---

## 🧩 OpenVS Skills (for Developers / AI Agents)

Besides the desktop client, the repository also ships a fully local **OpenVS Skills toolkit** (under `OpenVS_Skills/`). Pair it with your own AI Agent (Codex / Cursor / Claude, etc.): the Agent parses text or images into structured JSON, while local scripts validate it, lay it out automatically, and render an editable `.vsdx` file via the local Visio installation. **No internet or API Key required** — AI capability comes entirely from your own Agent.

**Requirements**: Windows + Microsoft Visio, Python 3.10+. From `OpenVS_Skills/openvs-visio/scripts`, run:

```bash
pip install -r requirements.txt
```

> Graphviz is bundled in `graphviz-bin/`, so no separate install is needed.

**Install into an Agent**: copy the `openvs-visio/` folder into your tool's skills directory (for Claude Code and other Agent-Skills-compliant tools, follow their convention), keeping the `openvs-visio/SKILL.md` structure intact.

**Command-line usage** (you can also prepare the JSON yourself, without an Agent):

```bash
# Text to diagram; --type: flowchart / sequence / composition / component / architecture / swimlane
python scripts/generate.py --type flowchart --json data.json -o flowchart.vsdx

# Image to diagram
python scripts/render_image.py --json analysis.json -o architecture.vsdx
```

JSON schemas live in `openvs-visio/references/`; add `--dry-run` to validate and lay out only, without launching Visio. Exit code 3 means a JSON data error; 1 means a render error.

**Limitations**: Windows + Microsoft Visio only; generates new `.vsdx` files but cannot edit existing ones and does not export png/pdf; image-parsing quality depends on the Agent's vision capability.

---

## 🎯 Target Users

- **Product Managers**: Quickly turn vague business requirements into flowcharts
- **Project Managers**: Use swimlane diagrams to clarify responsibilities across teams
- **System Architects**: Sketch system layers and component relationships in one sentence
- **Students / Researchers**: Visualize ideas and algorithm workflows from papers

---

<p align="center">© 2026 OpenVS · Natural Language & Image-Driven Visio Diagram Generation Tool</p>
