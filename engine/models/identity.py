"""惨剧轮回 — 身份、能力、效果数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.models.enums import (
    AbilityTiming, AbilityType, EffectType, Trait, TokenType,
)


# ---------------------------------------------------------------------------
# Condition — 效果触发条件
# ---------------------------------------------------------------------------
@dataclass
class Condition:
    """声明式条件，由规则引擎在运行时求值"""

    condition_type: str
    # 常用条件类型：
    #   "token_check"           — 某角色/版图指示物数量 >= / <= value
    #   "same_area_count"       — 同区域角色数量 == / >= value
    #   "character_alive"       — 角色是否存活
    #   "is_final_day"          — 是否最终日
    #   "identity_is"           — 角色身份 == value
    #   "ex_gauge_check"        — EX 槽 >= / <= value
    #   "has_trait"             — 角色是否拥有某特性
    #   "area_is"               — 角色所在区域 == value
    #   "world_line_check"      — 表/里世界（AHR）
    #   "loop_number_check"     — 轮回编号
    #   "incident_occurred"     — 某事件是否发生过

    params: dict[str, Any] = field(default_factory=dict)
    # 例：{"target": "self", "token": "intrigue", "operator": ">=", "value": 2}


# ---------------------------------------------------------------------------
# Effect — 单个效果原语
# ---------------------------------------------------------------------------
@dataclass
class Effect:
    """声明式效果，由 AtomicResolver 在运行时执行"""

    effect_type: EffectType

    # 目标选择
    target: str = "self"
    # 常用 target：
    #   "self"              — 持有该能力的角色
    #   "same_area_other"   — 同区域其他角色（需选择）
    #   "same_area_any"   — 同区域任意角色（需选择）
    #   "same_area_all"     — 同区域全部角色
    #   "any_character"     — 任意角色（需选择）
    #   "any_board"         — 任意版图（需选择）
    #   "same_area_board"   — 该角色所在版图
    #   "condition_target"  — 条件判定中确定的目标
    #   "initial_area_board" — 初始区域版图
    #   具体 character_id   — 指定角色

    # 效果参数
    token_type: Optional[TokenType] = None
    amount: int = 0
    chooser: str = "mastermind"  # 谁做选择："mastermind" / "leader" / "owner"
    value: Any = None            # 通用值字段

    # 条件（可选，效果自身的额外条件）
    condition: Optional[Condition] = None


# ---------------------------------------------------------------------------
# Ability — 身份/规则能力
# ---------------------------------------------------------------------------
@dataclass
class Ability:
    ability_id: str              # 唯一标识，如 "key_person_on_death"
    name: str                    # 显示名
    ability_type: AbilityType    # 强制 / 任意 / 失败条件
    timing: AbilityTiming        # 触发窗口
    description: str = ""        # 规则原文描述

    # 触发条件（可选）
    condition: Optional[Condition] = None

    # 效果列表（按顺序执行，无"随后"则同时生效）
    effects: list[Effect] = field(default_factory=list)

    # 是否含有"随后"（sequential vs simultaneous）
    sequential: bool = False

    # 使用限制
    once_per_loop: bool = False
    once_per_day: bool = False

    # 是否可被拒绝（主人公友好能力默认可被拒绝）
    can_be_refused: bool = False


# ---------------------------------------------------------------------------
# IdentityDef — 身份定义
# ---------------------------------------------------------------------------
@dataclass
class IdentityDef:
    identity_id: str             # 如 "关键人物", "杀手"
    name: str
    module: str                  # 所属模组
    traits: set[Trait] = field(default_factory=set)
    max_count: Optional[int] = None  # 数量上限（None=无限制）
    abilities: list[Ability] = field(default_factory=list)
    description: str = ""
