"""OpenVS Skill 本地配置 —— 纯离线工具，无云端、无账号、无密钥。

只包含 Visio 样式与布局参数，可按需修改。
"""
import os

# ---- 将随包携带的 Graphviz 布局引擎加入 PATH（flowchart / component 布局需要 dot.exe）----
_GV_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graphviz-bin")
if os.path.isdir(_GV_BIN):
    os.environ["PATH"] = _GV_BIN + os.pathsep + os.environ.get("PATH", "")

# Visio 样式（全局共享）
VISIO_FONT = "Microsoft YaHei"
VISIO_FONT_SIZE = 10      # pt
VISIO_EDGE_FONT_SIZE = 8  # pt

# 流程图布局
LAYOUT_DIRECTION = "TB"   # TB=自上而下, LR=自左而右
LAYOUT_SCALE = 1.0

# 时序图布局
SEQ_PARTICIPANT_SPACING = 2.5  # 参与者间距（英寸）
SEQ_MESSAGE_SPACING = 0.6      # 消息间距（英寸）

# 组成图布局
COMP_LEVEL_HEIGHT = 1.2        # 层级间距（英寸）
COMP_SIBLING_SPACING = 0.3     # 同级节点间距（英寸）
