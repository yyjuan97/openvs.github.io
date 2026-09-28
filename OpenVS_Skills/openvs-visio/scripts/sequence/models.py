from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MessageType(Enum):
    SYNC = "sync"           # 同步消息（实线实心箭头）
    ASYNC = "async"         # 异步消息（实线开放箭头）
    RETURN = "return"       # 返回消息（虚线开放箭头）
    SELF = "self"           # 自调用消息


class FragmentType(Enum):
    ALT = "alt"             # 条件分支
    OPT = "opt"             # 可选
    LOOP = "loop"           # 循环
    PAR = "par"             # 并行


@dataclass
class Participant:
    id: str
    label: str              # 参与方名称
    x: Optional[float] = None   # 水平位置（布局引擎填充）


@dataclass
class Message:
    id: str
    from_id: str            # 发送方 Participant.id
    to_id: str              # 接收方 Participant.id
    label: str              # 消息内容
    msg_type: MessageType = MessageType.SYNC
    y: Optional[float] = None   # 垂直位置（布局引擎填充）
    fragment_id: str = ""   # 所属片段 ID，空表示不属于任何片段


@dataclass
class Fragment:
    id: str
    frag_type: FragmentType # 片段类型
    label: str              # 片段标签
    start_msg_id: str = ""  # 起始消息 ID
    end_msg_id: str = ""    # 结束消息 ID
    participant_ids: list[str] = field(default_factory=list)
    start_y: Optional[float] = None  # 布局引擎填充
    end_y: Optional[float] = None    # 布局引擎填充


@dataclass
class SequenceData:
    participants: list[Participant] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    fragments: list[Fragment] = field(default_factory=list)

    def get_participant(self, pid: str) -> Optional[Participant]:
        for p in self.participants:
            if p.id == pid:
                return p
        return None

    def get_message(self, mid: str) -> Optional[Message]:
        for m in self.messages:
            if m.id == mid:
                return m
        return None

    def validate(self) -> list[str]:
        errors = []
        pids = [p.id for p in self.participants]
        if len(pids) != len(set(pids)):
            errors.append("Duplicate participant IDs found")
        for msg in self.messages:
            if msg.from_id not in pids:
                errors.append(f"Message from_id '{msg.from_id}' not found in participants")
            if msg.to_id not in pids:
                errors.append(f"Message to_id '{msg.to_id}' not found in participants")
        return errors
