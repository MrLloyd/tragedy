"""惨剧轮回 — 状态机引擎

纯流程控制，不含业务逻辑。负责：
1. 线性阶段推进（15 个节点）
2. 条件分支（TURN_END / LOOP_END_CHECK）
3. 虚线跳转（force_loop_end）
"""

from __future__ import annotations

from engine.models.enums import GamePhase


# ---------------------------------------------------------------------------
# 线性转换表（无条件分支的阶段）
# ---------------------------------------------------------------------------
_LINEAR_TRANSITIONS: dict[GamePhase, GamePhase] = {
    GamePhase.GAME_PREPARE:       GamePhase.LOOP_START,
    GamePhase.LOOP_START:         GamePhase.TURN_START,
    GamePhase.TURN_START:         GamePhase.MASTERMIND_ACTION,
    GamePhase.MASTERMIND_ACTION:  GamePhase.PROTAGONIST_ACTION,
    GamePhase.PROTAGONIST_ACTION: GamePhase.ACTION_RESOLVE,
    GamePhase.ACTION_RESOLVE:     GamePhase.PLAYWRIGHT_ABILITY,
    GamePhase.PLAYWRIGHT_ABILITY: GamePhase.PROTAGONIST_ABILITY,
    GamePhase.PROTAGONIST_ABILITY:GamePhase.INCIDENT,
    GamePhase.INCIDENT:           GamePhase.LEADER_ROTATE,
    GamePhase.LEADER_ROTATE:      GamePhase.TURN_END,
    # TURN_END → 条件分支，不在此表
    GamePhase.LOOP_END:           GamePhase.LOOP_END_CHECK,
    # LOOP_END_CHECK → 条件分支，不在此表
    GamePhase.NEXT_LOOP:          GamePhase.LOOP_START,
    GamePhase.FINAL_GUESS:        GamePhase.GAME_END,
}


class StateMachine:
    """
    状态机：决定"下一步该做什么"。

    调用 advance() 获取下一阶段，调用 force_loop_end() 插入虚线跳转。
    """

    def __init__(self) -> None:
        self.current_phase: GamePhase = GamePhase.GAME_PREPARE
        self._pending_loop_end: bool = False

    # ---- 核心接口 ----

    def advance(self, *, is_final_day: bool = False,
                failure_reached: bool = False,
                is_last_loop: bool = False,
                protagonist_dead: bool = False,
                has_final_guess: bool = True) -> GamePhase:
        """
        推进到下一阶段并返回新阶段。

        参数仅在条件分支节点使用：
          - is_final_day: TURN_END 分支用
          - failure_reached / protagonist_dead: LOOP_END_CHECK 分支用
          - is_last_loop: LOOP_END_CHECK 分支用
          - has_final_guess: 模组是否有最终决战（First Steps 无）
        """
        # ① 虚线跳转优先：任何阶段 → LOOP_END
        if self._pending_loop_end:
            self._pending_loop_end = False
            self.current_phase = GamePhase.LOOP_END
            return self.current_phase

        # ② 条件分支节点
        if self.current_phase == GamePhase.TURN_END:
            self.current_phase = self._branch_turn_end(is_final_day)
            return self.current_phase

        if self.current_phase == GamePhase.LOOP_END_CHECK:
            self.current_phase = self._branch_loop_end_check(
                failure_reached=failure_reached,
                protagonist_dead=protagonist_dead,
                is_last_loop=is_last_loop,
                has_final_guess=has_final_guess,
            )
            return self.current_phase

        # ③ 线性推进
        next_phase = _LINEAR_TRANSITIONS.get(self.current_phase)
        if next_phase is None:
            raise RuntimeError(
                f"No transition defined for phase {self.current_phase}"
            )
        self.current_phase = next_phase
        return self.current_phase

    def force_loop_end(self) -> None:
        """
        标记虚线跳转：当前阶段结算完毕后，下一次 advance() 直接跳到 LOOP_END。

        触发场景：关键人物死亡、时间旅者最终日能力等。
        """
        self._pending_loop_end = True

    def reset(self) -> None:
        """完全重置（新游戏）"""
        self.current_phase = GamePhase.GAME_PREPARE
        self._pending_loop_end = False

    @property
    def is_game_over(self) -> bool:
        return self.current_phase == GamePhase.GAME_END

    # ---- 条件分支 ----

    @staticmethod
    def _branch_turn_end(is_final_day: bool) -> GamePhase:
        """
        TURN_END 分支：
          最终日 → LOOP_END（进入轮回结束阶段）
          否则   → TURN_START（下一天）
        """
        if is_final_day:
            return GamePhase.LOOP_END
        return GamePhase.TURN_START

    @staticmethod
    def _branch_loop_end_check(
        *,
        failure_reached: bool,
        protagonist_dead: bool,
        is_last_loop: bool,
        has_final_guess: bool,
    ) -> GamePhase:
        """
        LOOP_END_CHECK 三路分支：
          1. 未达失败条件且主人公未死 → GAME_END（主人公胜利条件A）
          2. 达失败条件且非最后轮回   → NEXT_LOOP
          3. 达失败条件且最后轮回     → FINAL_GUESS（若模组有）/ GAME_END
        """
        has_failed = failure_reached or protagonist_dead

        if not has_failed:
            # 主人公胜利（条件 A）
            return GamePhase.GAME_END

        if not is_last_loop:
            # 还有轮回，继续
            return GamePhase.NEXT_LOOP

        # 最后轮回且失败
        if has_final_guess:
            return GamePhase.FINAL_GUESS
        else:
            # First Steps 无最终决战 → 剧作家直接胜利
            return GamePhase.GAME_END
