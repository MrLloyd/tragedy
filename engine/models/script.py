"""惨剧轮回 — 剧本数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from engine.models.identity import Ability
from engine.models.incident import IncidentSchedule


# ---------------------------------------------------------------------------
# RuleDef — 规则 Y / 规则 X 定义
# ---------------------------------------------------------------------------
@dataclass
class RuleDef:
    rule_id: str                 # 如 "谋杀计划", "好友圈"
    name: str
    rule_type: str               # "Y" or "X"
    module: str                  # 所属模组

    # 该规则要求的身份及数量 {"关键人物": 1, "杀手": 1}
    identity_slots: dict[str, int] = field(default_factory=dict)

    # 追加规则带来的能力（失败条件、额外能力等）
    abilities: list[Ability] = field(default_factory=list)

    # 特殊胜利条件（LL 背叛者用）
    special_victory: Optional[dict[str, Any]] = None

    description: str = ""


# ---------------------------------------------------------------------------
# ModuleDef — 模组定义
# ---------------------------------------------------------------------------
@dataclass
class ModuleDef:
    module_id: str               # 如 "first_steps", "basic_tragedy_x"
    name: str                    # 显示名

    # 特殊规则文本
    special_rules: list[str] = field(default_factory=list)

    # 模组规定的规则 X 条数（First Steps=1, 其他一般=2）
    rule_x_count: int = 2

    # 是否有最终决战（First Steps 无）
    has_final_guess: bool = True

    # EX 槽配置
    has_ex_gauge: bool = False
    ex_gauge_resets_per_loop: bool = True

    # 可用规则
    rules_y: list[RuleDef] = field(default_factory=list)
    rules_x: list[RuleDef] = field(default_factory=list)

    # 模组身份池（identity_id 列表）
    identity_pool: list[str] = field(default_factory=list)

    # 模组事件池（incident_id 列表）
    incident_pool: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CharacterSetup — 剧本中单个角色的配置
# ---------------------------------------------------------------------------
@dataclass
class CharacterSetup:
    character_id: str            # 角色标识（引用 characters.json）
    identity_id: str = "平民"   # 分配的身份（非公开）
    is_incident_perpetrator: bool = False  # 是否为某事件当事人


# ---------------------------------------------------------------------------
# Script — 完整剧本（公开 + 非公开信息）
# ---------------------------------------------------------------------------
@dataclass
class Script:
    # --- 公开信息表 ---
    module_id: str = ""                     # 模组标识
    loop_count: int = 4                     # 轮回数
    days_per_loop: int = 4                  # 每轮回天数
    incident_public: list[dict] = field(default_factory=list)
    # [{"name": "谋杀", "day": 3}, ...]（不含当事人）
    special_rules_text: list[str] = field(default_factory=list)

    # --- 非公开信息表（仅剧作家） ---
    rule_y: Optional[RuleDef] = None
    rules_x: list[RuleDef] = field(default_factory=list)
    characters: list[CharacterSetup] = field(default_factory=list)
    incidents: list[IncidentSchedule] = field(default_factory=list)

    def get_public_info(self) -> dict:
        """返回主人公可见的公开信息"""
        return {
            "module_id": self.module_id,
            "loop_count": self.loop_count,
            "days_per_loop": self.days_per_loop,
            "incidents": self.incident_public,
            "special_rules": self.special_rules_text,
        }
