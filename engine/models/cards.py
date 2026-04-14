"""惨剧轮回 — 行动牌数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from engine.models.enums import AreaId, CardType, PlayerRole


# ---------------------------------------------------------------------------
# ActionCard — 单张行动牌
# ---------------------------------------------------------------------------
@dataclass
class ActionCard:
    card_type: CardType
    owner: PlayerRole           # 归属（剧作家 or 主人公 0/1/2）
    once_per_loop: bool = False  # 是否每轮回限 1 次
    is_used_this_loop: bool = False  # 本轮回是否已使用
    is_extension: bool = False  # 是否为扩展牌（绝望+1/希望+1 等）

    @property
    def is_movement(self) -> bool:
        return self.card_type in {
            CardType.MOVE_HORIZONTAL, CardType.MOVE_VERTICAL,
            CardType.MOVE_DIAGONAL,
            CardType.MOVE_HORIZONTAL_P, CardType.MOVE_VERTICAL_P,
        }

    @property
    def is_forbid(self) -> bool:
        return self.card_type in {
            CardType.FORBID_GOODWILL, CardType.FORBID_PARANOIA,
            CardType.FORBID_INTRIGUE, CardType.FORBID_MOVEMENT,
        }

    def reset_for_new_loop(self) -> None:
        self.is_used_this_loop = False


# ---------------------------------------------------------------------------
# CardPlacement — 一张牌的放置信息
# ---------------------------------------------------------------------------
@dataclass
class CardPlacement:
    card: ActionCard
    owner: PlayerRole
    target_type: str            # "character" | "board"
    target_id: str              # character_id 或 AreaId.value
    face_down: bool = True      # 暗置状态
    nullified: bool = False     # 是否被无效化


# ---------------------------------------------------------------------------
# CardHand — 一位玩家的手牌
# ---------------------------------------------------------------------------
@dataclass
class CardHand:
    owner: PlayerRole
    cards: list[ActionCard] = field(default_factory=list)

    def get_available(self) -> list[ActionCard]:
        """返回当前可用手牌（未使用的每轮一次牌 + 普通牌）"""
        return [c for c in self.cards
                if not (c.once_per_loop and c.is_used_this_loop)]

    def reset_for_new_loop(self) -> None:
        for card in self.cards:
            card.reset_for_new_loop()


# ---------------------------------------------------------------------------
# 默认手牌工厂
# ---------------------------------------------------------------------------
def create_mastermind_hand() -> CardHand:
    """创建剧作家默认手牌（9 张基础牌）"""
    cards = [
        ActionCard(CardType.INTRIGUE_PLUS_2, PlayerRole.MASTERMIND, once_per_loop=True),
        ActionCard(CardType.INTRIGUE_PLUS_1, PlayerRole.MASTERMIND),
        ActionCard(CardType.PARANOIA_PLUS_1, PlayerRole.MASTERMIND),
        ActionCard(CardType.PARANOIA_PLUS_1, PlayerRole.MASTERMIND),
        ActionCard(CardType.PARANOIA_MINUS_1, PlayerRole.MASTERMIND),
        ActionCard(CardType.MOVE_HORIZONTAL, PlayerRole.MASTERMIND),
        ActionCard(CardType.MOVE_VERTICAL, PlayerRole.MASTERMIND),
        ActionCard(CardType.MOVE_DIAGONAL, PlayerRole.MASTERMIND, once_per_loop=True),
        ActionCard(CardType.FORBID_GOODWILL, PlayerRole.MASTERMIND),
        ActionCard(CardType.FORBID_PARANOIA, PlayerRole.MASTERMIND),
    ]
    return CardHand(owner=PlayerRole.MASTERMIND, cards=cards)


def create_protagonist_hand(role: PlayerRole) -> CardHand:
    """创建主人公默认手牌（8 张基础牌）"""
    cards = [
        ActionCard(CardType.GOODWILL_PLUS_1, role),
        ActionCard(CardType.GOODWILL_PLUS_2, role, once_per_loop=True),
        ActionCard(CardType.PARANOIA_PLUS_1_P, role),
        ActionCard(CardType.PARANOIA_MINUS_1_P, role, once_per_loop=True),
        ActionCard(CardType.MOVE_HORIZONTAL_P, role),
        ActionCard(CardType.MOVE_VERTICAL_P, role),
        ActionCard(CardType.FORBID_INTRIGUE, role),
        ActionCard(CardType.FORBID_MOVEMENT, role, once_per_loop=True),
    ]
    return CardHand(owner=role, cards=cards)
