"""惨剧轮回 — 事件数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.models.effects import Condition, Effect


@dataclass
class IncidentPublicResult:
    """事件结算后的公开记录；不包含当事人或隐藏目标。"""

    incident_id: str
    day: int
    occurred: bool = False
    has_phenomenon: bool = False
    result_tags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# IncidentDef — 事件定义（模组级）
# ---------------------------------------------------------------------------
@dataclass
class IncidentDef:
    incident_id: str             # 如 "谋杀", "医院事故"
    name: str
    module: str                  # 所属模组

    # 事件效果（可有多条，按顺序结算；含"随后"则 sequential=True）
    effects: list[Effect] = field(default_factory=list)
    sequential: bool = False

    # 额外触发条件（普通事件：当事人存活+不安>=限度，部分事件有额外条件）
    extra_condition: Optional[Condition] = None

    # 事件特殊标签
    is_crowd_event: bool = False        # 群众事件（HSA）
    required_corpse_count: int = 0      # 群众事件所需尸体数
    modifies_paranoia_limit: int = 0    # 修改当事人不安限度（如猎奇杀人+1、送葬-1）
    no_ex_gauge_increment: bool = False  # 不增加 EX 槽（银色子弹）
    ex_gauge_increment: int = 0         # 额外 EX 槽增量（猎奇杀人+2）

    description: str = ""


# ---------------------------------------------------------------------------
# IncidentSchedule — 剧本中的事件日程
# ---------------------------------------------------------------------------
@dataclass
class IncidentSchedule:
    incident_id: str             # 引用 IncidentDef.incident_id
    day: int                     # 发生在第几天
    perpetrator_id: str          # 当事人角色 ID（非公开）
    perpetrator_area: Optional[str] = None  # 群众事件指定版图
    target_character_ids: list[str] = field(default_factory=list)  # 非公开预设角色目标
    target_area_ids: list[str] = field(default_factory=list)       # 非公开预设版图目标
    chosen_token_types: list[str] = field(default_factory=list)    # 非公开预设指示物类型

    # 运行时状态
    occurred: bool = False       # 本轮回是否已发生
