"""惨剧轮回 — 身份定义模型（兼容导出 Ability/Condition/Effect）"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.models.ability import Ability
from engine.models.effects import Condition, Effect
from engine.models.enums import Trait


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
