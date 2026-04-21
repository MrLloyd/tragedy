"""惨剧轮回 — 游戏状态聚合根

单一权威数据源。提供：
- 状态读写
- 快照（原子结算用）
- 轮回重置
- LoopSnapshot（跨轮回记忆）
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from engine.models.enums import AreaId, GamePhase, TokenType
from engine.models.board import BoardState
from engine.models.cards import (
    CardHand, CardPlacement, PlayerRole,
    create_mastermind_hand, create_protagonist_hand,
)
from engine.models.character import CharacterEndState, CharacterState, TokenSet
from engine.models.identity import IdentityDef
from engine.models.incident import IncidentDef, IncidentPublicResult, IncidentSchedule
from engine.models.script import ModuleDef, Script


# ---------------------------------------------------------------------------
# LoopSnapshot — 跨轮回快照
# ---------------------------------------------------------------------------
@dataclass
class LoopSnapshot:
    loop_number: int
    ex_gauge: int
    incidents_occurred: list[str]
    character_snapshots: dict[str, CharacterEndState] = field(default_factory=dict)


@dataclass
class AbilityRuntimeState:
    """能力运行时状态：统一维护限次计数。"""

    usages_this_loop: dict[str, int] = field(default_factory=dict)
    usages_this_day: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# GameState — 聚合根
# ---------------------------------------------------------------------------
@dataclass
class GameState:

    # ---- 剧本 ----
    script: Script = field(default_factory=Script)

    # ---- 模组配置（由 module_loader + apply_loaded_module 填充；未开局时可为 None） ----
    module_def: Optional[ModuleDef] = None

    # ---- 轮回 / 天 / 阶段 ----
    current_loop: int = 1
    current_day: int = 1
    current_phase: GamePhase = GamePhase.GAME_PREPARE

    # ---- 队长 ----
    leader_index: int = 0                    # 0-2

    # ---- 角色 ----
    characters: dict[str, CharacterState] = field(default_factory=dict)

    # ---- 版图 ----
    board: BoardState = field(default_factory=BoardState)

    # ---- 手牌 ----
    mastermind_hand: CardHand = field(
        default_factory=lambda: create_mastermind_hand()
    )
    protagonist_hands: list[CardHand] = field(default_factory=list)

    # ---- 当日行动牌放置 ----
    placed_cards: list[CardPlacement] = field(default_factory=list)

    # ---- 失败 / 死亡 标记 ----
    failure_flags: set[str] = field(default_factory=set)
    protagonist_dead: bool = False

    # ---- 军人能力 ----
    soldier_protection_active: bool = False

    # ---- EX 槽（MC/WM/AHR/LL 预留） ----
    ex_gauge: int = 0
    ex_gauge_resets_per_loop: bool = True

    # ---- 世界线（AHR 预留） ----
    world_line: int = 0                      # 偶=表，奇=里
    world_moved_today: bool = False

    # ---- 标志（LL 预留） ----
    communicated_flags: int = 0
    death_flags: int = 0
    betrayer_map: dict[int, str] = field(default_factory=dict)

    # ---- 诅咒牌（HSA 预留） ----
    curse_cards_on_board: dict[str, list] = field(default_factory=dict)

    # ---- 事件追踪 ----
    incidents_occurred_this_loop: list[str] = field(default_factory=list)
    incident_results_this_loop: list[IncidentPublicResult] = field(default_factory=list)
    # Phase 2 module_loader 填充；为空时 IncidentHandler 仅做触发标记，跳过效果执行
    incident_defs: dict[str, IncidentDef] = field(default_factory=dict)
    # Phase 2 module_loader 填充；为空时 ON_DEATH 能力触发跳过（安全降级）
    identity_defs: dict[str, IdentityDef] = field(default_factory=dict)

    # ---- 能力运行时状态（统一限次，P4-2） ----
    ability_runtime: AbilityRuntimeState = field(default_factory=AbilityRuntimeState)

    # ---- 跨轮回历史 ----
    loop_history: list[LoopSnapshot] = field(default_factory=list)

    # ==================================================================
    # 初始化
    # ==================================================================

    def init_protagonist_hands(self) -> None:
        """创建 3 名主人公的手牌"""
        if not self.protagonist_hands:
            self.protagonist_hands = [
                create_protagonist_hand(PlayerRole.PROTAGONIST_0),
                create_protagonist_hand(PlayerRole.PROTAGONIST_1),
                create_protagonist_hand(PlayerRole.PROTAGONIST_2),
            ]

    @classmethod
    def create_minimal_test_state(cls, *,
                                   loop_count: int = 2,
                                   days_per_loop: int = 2) -> GameState:
        """
        创建最小游戏状态（用于测试）

        参数：
          loop_count: 最大轮回数（默认 2）
          days_per_loop: 每轮最大天数（默认 2）

        初始化：
          - Script(loop_count, days_per_loop)
          - 3 名主人公及其手牌
          - 1 个最小角色（用于事件当事人）
          - 当前轮 = 1, 当前天 = 1
        """
        script = Script(
            module_id="first_steps",
            loop_count=loop_count,
            days_per_loop=days_per_loop,
            incident_public=[],
            special_rules_text=[],
        )

        state = cls(
            script=script,
            module_def=ModuleDef(
                module_id="first_steps",
                name="minimal-test",
                has_final_guess=False,
            ),
            current_loop=1,
            current_day=1,
            leader_index=0,
        )

        # 初始化主人公手牌
        state.init_protagonist_hands()

        # 添加最小角色（防止空角色表）
        state.characters = {
            "test_character": CharacterState(
                character_id="test_character",
                name="测试角色",
                area=AreaId.SCHOOL,
                initial_area=AreaId.SCHOOL,
                identity_id="test_identity",
                original_identity_id="test_identity",
            )
        }

        return state

    # ==================================================================
    # 查询
    # ==================================================================

    @property
    def max_loops(self) -> int:
        return self.script.loop_count

    @property
    def max_days(self) -> int:
        return self.script.days_per_loop

    @property
    def is_final_day(self) -> bool:
        return self.current_day >= self.max_days

    @property
    def is_last_loop(self) -> bool:
        return self.current_loop >= self.max_loops

    @property
    def has_final_guess(self) -> bool:
        """模组是否包含最终决战阶段（未加载模组时默认 True，与旧硬编码行为一致）"""
        if self.module_def is not None:
            return self.module_def.has_final_guess
        return True

    def characters_in_area(self, area: AreaId, alive_only: bool = True
                           ) -> list[CharacterState]:
        """返回指定区域的角色列表"""
        result = []
        for ch in self.characters.values():
            if ch.area != area:
                continue
            if alive_only and not ch.is_alive:
                continue
            if ch.is_removed:
                continue
            result.append(ch)
        return result

    def alive_characters(self) -> list[CharacterState]:
        return [ch for ch in self.characters.values()
                if ch.is_alive and not ch.is_removed]

    def get_character(self, character_id: str) -> CharacterState:
        return self.characters[character_id]

    def get_incidents_for_day(self, day: int) -> list[IncidentSchedule]:
        return [inc for inc in self.script.incidents if inc.day == day]

    # ==================================================================
    # 快照（原子结算"读"阶段用）
    # ==================================================================

    def snapshot(self) -> GameState:
        """深拷贝当前状态，用于原子结算的读阶段"""
        return copy.deepcopy(self)

    # ==================================================================
    # 轮回重置
    # ==================================================================

    def save_loop_snapshot(self) -> None:
        """在 loop_end 阶段保存跨轮回快照"""
        char_snapshots = {}
        for cid, ch in self.characters.items():
            char_snapshots[cid] = CharacterEndState(
                character_id=cid,
                is_alive=ch.is_alive,
                is_removed=ch.is_removed,
                tokens=ch.tokens.snapshot(),
                identity_revealed=ch.revealed,
                area=ch.area,
            )
        snap = LoopSnapshot(
            loop_number=self.current_loop,
            ex_gauge=self.ex_gauge,
            incidents_occurred=list(self.incidents_occurred_this_loop),
            character_snapshots=char_snapshots,
        )
        self.loop_history.append(snap)

    def get_last_loop_snapshot(self) -> Optional[LoopSnapshot]:
        if self.loop_history:
            return self.loop_history[-1]
        return None

    def reset_for_new_loop(self) -> None:
        """
        轮回重置：
        - 角色复活、清指示物、回初始位置
        - 版图清指示物
        - 手牌回收
        - 清失败标记
        - 天数重置
        - EX 槽按模组规则处理
        """
        # 角色重置
        for ch in self.characters.values():
            ch.reset_for_new_loop()

        # 版图重置
        self.board.reset_for_new_loop()

        # 手牌重置
        self.mastermind_hand.reset_for_new_loop()
        for hand in self.protagonist_hands:
            hand.reset_for_new_loop()

        # 放置牌清空
        self.placed_cards.clear()

        # 失败标记清空
        self.failure_flags.clear()
        self.protagonist_dead = False
        self.soldier_protection_active = False

        # 天数重置
        self.current_day = 1
        self.leader_index = 0

        # 事件重置
        for inc in self.script.incidents:
            inc.occurred = False
        self.incidents_occurred_this_loop.clear()
        self.incident_results_this_loop.clear()
        self.ability_runtime.usages_this_loop.clear()
        self.ability_runtime.usages_this_day.clear()

        # EX 槽
        if self.ex_gauge_resets_per_loop:
            self.ex_gauge = 0

        # 世界线
        self.world_line = 0
        self.world_moved_today = False

        # 轮回计数推进
        self.current_loop += 1

    # ==================================================================
    # 天推进
    # ==================================================================

    def advance_day(self) -> None:
        """推进到下一天"""
        self.current_day += 1
        self.placed_cards.clear()
        self.world_moved_today = False
        self.ability_runtime.usages_this_day.clear()

    def rotate_leader(self) -> None:
        """队长轮换 1→2→3→1"""
        self.leader_index = (self.leader_index + 1) % 3
