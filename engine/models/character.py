"""惨剧轮回 — 角色与指示物数据模型"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from engine.models.enums import AreaId, Attribute, TokenType, Trait


# ---------------------------------------------------------------------------
# TokenSet — 指示物集合（6 种，全模组通用）
# ---------------------------------------------------------------------------
@dataclass
class TokenSet:
    paranoia: int = 0    # 不安
    intrigue: int = 0    # 密谋
    goodwill: int = 0    # 友好
    hope: int = 0        # 希望（WM/AHR/LL）
    despair: int = 0     # 绝望（WM/AHR/LL）
    guard: int = 0       # 护卫

    def get(self, token_type: TokenType) -> int:
        return getattr(self, token_type.value)

    def set(self, token_type: TokenType, value: int) -> None:
        setattr(self, token_type.value, max(0, value))

    def add(self, token_type: TokenType, amount: int) -> None:
        current = self.get(token_type)
        self.set(token_type, current + amount)

    def remove(self, token_type: TokenType, amount: int) -> int:
        """移除指示物，返回实际移除数量（不足时按实际数量移除）"""
        current = self.get(token_type)
        actual = min(current, amount)
        self.set(token_type, current - actual)
        return actual

    def total(self) -> int:
        """全部指示物总数（临时工死亡判定用）"""
        return (self.paranoia + self.intrigue + self.goodwill
                + self.hope + self.despair + self.guard)

    def has_types_count(self) -> int:
        """拥有多少种不同指示物（AHR 童谣/次元旅者判定用）"""
        count = 0
        for t in TokenType:
            if self.get(t) > 0:
                count += 1
        return count

    def clear(self) -> None:
        for t in TokenType:
            self.set(t, 0)

    def snapshot(self) -> TokenSet:
        return copy.copy(self)


# ---------------------------------------------------------------------------
# CharacterState — 角色状态
# ---------------------------------------------------------------------------
@dataclass
class CharacterState:
    # --- 基础信息 ---
    character_id: str                       # 角色唯一标识（如 "女子学生"）
    name: str                               # 显示名
    area: AreaId = AreaId.CITY              # 当前所在区域
    initial_area: AreaId = AreaId.CITY      # 初始区域（剧本设定）
    tokens: TokenSet = field(default_factory=TokenSet)
    is_alive: bool = True
    is_removed: bool = False                # 是否被移除出游戏

    # --- 身份（非公开） ---
    identity_id: str = "平民"              # 当前生效身份
    original_identity_id: str = "平民"     # 非公开信息表配置的原始身份
    revealed: bool = False                  # 身份是否已公开

    # --- 特性与属性 ---
    base_traits: set[Trait] = field(default_factory=set)
    attributes: set[Attribute] = field(default_factory=set)
    paranoia_limit: int = 2                 # 不安限度

    # --- 区域限制 ---
    forbidden_areas: list[AreaId] = field(default_factory=list)

    # --- EX 牌（MZ/MC/HSA/AHR/LL 预留） ---
    ex_cards: list[str] = field(default_factory=list)

    # --- 诅咒牌状态（HSA 预留） ---
    curse_state: Optional[str] = None       # None / "on_character"

    # --- 双身份（AHR 表/里世界预留） ---
    surface_identity: Optional[str] = None
    inner_identity: Optional[str] = None

    # --- 行动牌限制 ---
    action_card_restricted: bool = False    # 狼人/预言家/幻想

    # --- 延迟登场（预留） ---
    entry_loop: Optional[int] = None        # 第几轮登场（神灵）
    entry_day: Optional[int] = None         # 第几天登场（转校生）

    # --- 运行时状态（不序列化到 JSON） ---
    goodwill_abilities_used: dict[str, int] = field(default_factory=dict)
    # ability_id -> 本轮回已使用次数

    def reset_for_new_loop(self) -> None:
        """轮回重置：复活、清指示物、回初始位置"""
        self.is_alive = True
        self.is_removed = False
        self.tokens.clear()
        self.area = self.initial_area
        self.goodwill_abilities_used.clear()
        self.ex_cards.clear()
        self.curse_state = None

    def snapshot(self) -> CharacterState:
        """深拷贝，用于原子结算的读阶段"""
        return copy.deepcopy(self)


# ---------------------------------------------------------------------------
# CharacterEndState — 轮回结束快照（LoopSnapshot 用）
# ---------------------------------------------------------------------------
@dataclass
class CharacterEndState:
    character_id: str
    is_alive: bool
    is_removed: bool
    tokens: TokenSet
    identity_revealed: bool
    area: AreaId
