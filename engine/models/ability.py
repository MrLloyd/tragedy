"""惨剧轮回 — 通用声明式能力模型"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.models.effects import Condition, Effect
from engine.models.enums import AbilityTiming, AbilityType


@dataclass
class Ability:
    """可由身份、规则或角色能力复用的通用能力声明。"""

    ability_id: str              # 唯一标识，如 "key_person_on_death"
    name: str                    # 显示名
    ability_type: AbilityType    # 强制 / 任意 / 失败条件
    timing: AbilityTiming        # 触发窗口
    description: str = ""        # 规则原文描述

    # 触发条件（可选）
    condition: Condition | None = None

    # 效果列表（按顺序执行，无"随后"则同时生效）
    effects: list[Effect] = field(default_factory=list)

    # 是否含有"随后"（sequential vs simultaneous）
    sequential: bool = False

    # 使用限制
    goodwill_cost: int = 0
    once_per_loop: bool = False
    once_per_day: bool = False

    # 是否可被拒绝（主人公友好能力默认可被拒绝）
    can_be_refused: bool = False
