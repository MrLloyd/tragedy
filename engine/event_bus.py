"""惨剧轮回 — 游戏内事件总线

用于解耦触发链。角色死亡、身份公开等事件发生后，
通过事件总线通知所有订阅者（能力处理器、日志系统等）。

与 UI 事件无关——这是纯引擎内部的游戏逻辑事件。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# 事件类型
# ---------------------------------------------------------------------------
class GameEventType(Enum):
    # 角色相关
    CHARACTER_DEATH = auto()         # 角色死亡
    CHARACTER_REVIVED = auto()       # 角色复活
    CHARACTER_MOVED = auto()         # 角色移动
    CHARACTER_REMOVED = auto()       # 角色被移除

    # 指示物变化
    TOKEN_CHANGED = auto()           # 指示物增减

    # 终局
    PROTAGONIST_DEATH = auto()       # 主人公死亡
    PROTAGONIST_FAILURE = auto()     # 主人公失败
    LOOP_END_FORCED = auto()         # 强制结束轮回

    # 信息
    IDENTITY_REVEALED = auto()       # 身份公开
    INCIDENT_OCCURRED = auto()       # 事件发生

    # 阶段流转
    PHASE_CHANGED = auto()           # 阶段切换
    LOOP_STARTED = auto()            # 轮回开始
    LOOP_ENDED = auto()              # 轮回结束
    GAME_ENDED = auto()              # 游戏结束

    # 能力
    ABILITY_DECLARED = auto()        # 能力被声明
    ABILITY_REFUSED = auto()         # 能力被拒绝

    # EX（预留）
    EX_GAUGE_CHANGED = auto()        # EX 槽变化
    WORLD_MOVED = auto()             # 世界移动（AHR）


# ---------------------------------------------------------------------------
# GameEvent — 事件载体
# ---------------------------------------------------------------------------
@dataclass
class GameEvent:
    event_type: GameEventType
    data: dict[str, Any] = field(default_factory=dict)

    # 常用 data keys：
    # CHARACTER_DEATH:      {"character_id": str, "cause": str}
    # TOKEN_CHANGED:        {"target_id": str, "token_type": str, "delta": int}
    # PROTAGONIST_DEATH:    {"cause": str}
    # PROTAGONIST_FAILURE:  {"cause": str}
    # IDENTITY_REVEALED:    {"character_id": str, "identity_id": str}
    # INCIDENT_OCCURRED:    {"incident_id": str, "day": int}
    # ABILITY_REFUSED:      {"character_id": str, "ability_id": str}


# ---------------------------------------------------------------------------
# 订阅回调类型
# ---------------------------------------------------------------------------
EventHandler = Callable[[GameEvent], None]


# ---------------------------------------------------------------------------
# EventBus — 事件总线
# ---------------------------------------------------------------------------
class EventBus:
    """
    简单的发布-订阅事件总线。

    用法：
        bus = EventBus()
        bus.subscribe(GameEventType.CHARACTER_DEATH, my_handler)
        bus.emit(GameEvent(GameEventType.CHARACTER_DEATH, {"character_id": "A"}))
    """

    def __init__(self) -> None:
        self._handlers: dict[GameEventType, list[EventHandler]] = defaultdict(list)
        self._log: list[GameEvent] = []

    def subscribe(self, event_type: GameEventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: GameEventType, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def emit(self, event: GameEvent) -> None:
        """发布事件，同步调用所有订阅者"""
        self._log.append(event)
        for handler in self._handlers.get(event.event_type, []):
            handler(event)

    def clear_handlers(self) -> None:
        self._handlers.clear()

    @property
    def log(self) -> list[GameEvent]:
        """完整事件日志（裁定日志用）"""
        return self._log

    def clear_log(self) -> None:
        self._log.clear()
