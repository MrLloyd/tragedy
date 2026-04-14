"""惨剧轮回 — 版图数据模型"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from engine.models.enums import AreaId, TokenType
from engine.models.character import TokenSet


# ---------------------------------------------------------------------------
# BoardArea — 单个版图区域
# ---------------------------------------------------------------------------
@dataclass
class BoardArea:
    area_id: AreaId
    row: int                    # 0 or 1（2x2 网格行）
    col: int                    # 0 or 1（2x2 网格列）
    tokens: TokenSet = field(default_factory=TokenSet)

    # 诅咒牌（HSA 预留）
    curse_cards: list[str] = field(default_factory=list)

    # 封锁状态（MC 预留）
    lockdown_until_day: Optional[int] = None

    def reset_for_new_loop(self) -> None:
        self.tokens.clear()
        self.curse_cards.clear()
        self.lockdown_until_day = None


# ---------------------------------------------------------------------------
# 版图布局
#
#   col 0     col 1
#  ┌────────┬────────┐
#  │ 医院   │ 学校   │  row 0
#  ├────────┼────────┤
#  │ 神社   │ 都市   │  row 1
#  └────────┴────────┘
#
#  远方不属于网格，单独管理
# ---------------------------------------------------------------------------

# 默认版图定义
DEFAULT_LAYOUT: dict[AreaId, tuple[int, int]] = {
    AreaId.HOSPITAL: (0, 0),
    AreaId.SCHOOL:   (0, 1),
    AreaId.SHRINE:   (1, 0),
    AreaId.CITY:     (1, 1),
}


@dataclass
class BoardState:
    areas: dict[AreaId, BoardArea] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.areas:
            for area_id, (r, c) in DEFAULT_LAYOUT.items():
                self.areas[area_id] = BoardArea(area_id=area_id, row=r, col=c)

    # ---- 相邻判定 ----

    def get_horizontal_adjacent(self, area_id: AreaId) -> Optional[AreaId]:
        """横向相邻（同行，不同列）"""
        if area_id == AreaId.FARAWAY:
            return None
        area = self.areas[area_id]
        target_col = 1 - area.col
        for aid, a in self.areas.items():
            if a.row == area.row and a.col == target_col:
                return aid
        return None

    def get_vertical_adjacent(self, area_id: AreaId) -> Optional[AreaId]:
        """竖向相邻（同列，不同行）"""
        if area_id == AreaId.FARAWAY:
            return None
        area = self.areas[area_id]
        target_row = 1 - area.row
        for aid, a in self.areas.items():
            if a.col == area.col and a.row == target_row:
                return aid
        return None

    def get_diagonal_adjacent(self, area_id: AreaId) -> Optional[AreaId]:
        """对角相邻"""
        if area_id == AreaId.FARAWAY:
            return None
        area = self.areas[area_id]
        target_row = 1 - area.row
        target_col = 1 - area.col
        for aid, a in self.areas.items():
            if a.row == target_row and a.col == target_col:
                return aid
        return None

    def get_all_adjacent(self, area_id: AreaId) -> list[AreaId]:
        """所有相邻区域（横+竖，不含对角，不含远方）"""
        result = []
        h = self.get_horizontal_adjacent(area_id)
        v = self.get_vertical_adjacent(area_id)
        if h:
            result.append(h)
        if v:
            result.append(v)
        return result

    def is_adjacent(self, a: AreaId, b: AreaId) -> bool:
        """判断两个区域是否相邻（横或竖）"""
        return b in self.get_all_adjacent(a)

    # ---- 状态操作 ----

    def reset_for_new_loop(self) -> None:
        for area in self.areas.values():
            area.reset_for_new_loop()

    def snapshot(self) -> BoardState:
        return copy.deepcopy(self)
