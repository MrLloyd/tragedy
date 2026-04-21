"""惨剧轮回 — 游戏控制器

调度中枢：协调状态机、阶段处理器、结算引擎。

核心循环：
  1. 状态机决定当前阶段
  2. 阶段处理器执行逻辑，返回信号
  3. 根据信号推进、挂起或跳转
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from engine.event_bus import EventBus, GameEvent, GameEventType
from engine.game_state import GameState
from engine.models.enums import GamePhase, Outcome
from engine.phases.phase_base import (
    ForceLoopEnd, PhaseComplete, PhaseHandler, PhaseSignal, WaitForInput,
    create_phase_handlers,
)
from engine.resolvers.atomic_resolver import AtomicResolver
from engine.resolvers.death_resolver import DeathResolver
from engine.state_machine import StateMachine
from engine.visibility import Visibility, VisibleGameState


# ---------------------------------------------------------------------------
# UI 回调接口
# ---------------------------------------------------------------------------
class UICallback:
    """UI 层需要实现的回调接口"""

    def on_phase_changed(self, phase: GamePhase, visible_state: VisibleGameState) -> None:
        """阶段切换通知"""
        pass

    def on_wait_for_input(self, wait: WaitForInput) -> None:
        """引擎挂起，等待玩家输入"""
        pass

    def on_announcement(self, text: str) -> None:
        """结算公告"""
        pass

    def on_game_over(self, outcome: Outcome) -> None:
        """游戏结束"""
        pass


# ---------------------------------------------------------------------------
# GameController — 游戏控制器
# ---------------------------------------------------------------------------
class GameController:

    def __init__(self, ui_callback: Optional[UICallback] = None) -> None:
        # 核心组件
        self.event_bus = EventBus()
        self.death_resolver = DeathResolver()
        self.atomic_resolver = AtomicResolver(self.event_bus, self.death_resolver)
        self.state_machine = StateMachine()
        self.state = GameState()
        self.visibility = Visibility()

        # 阶段处理器
        self.phase_handlers = create_phase_handlers(
            self.event_bus, self.atomic_resolver
        )

        # UI
        self.ui_callback = ui_callback or UICallback()

        # 当前挂起的回调
        self._pending_callback: Optional[Callable] = None

    # ==================================================================
    # 游戏生命周期
    # ==================================================================

    def start_game(
        self,
        module_id: str,
        *,
        loop_count: int | None = None,
        days_per_loop: int | None = None,
    ) -> None:
        """从 `data/modules/{module_id}.json` 加载并开局。"""
        from engine.rules.module_loader import build_game_state_from_module

        self.state = build_game_state_from_module(
            module_id,
            loop_count=loop_count,
            days_per_loop=days_per_loop,
        )
        self.state_machine.reset()
        self.state.current_phase = GamePhase.GAME_PREPARE
        self._run_phase()

    def provide_input(self, choice: Any) -> None:
        """
        玩家提供输入（响应 WaitForInput）。

        由 UI 层调用，将玩家选择传回引擎继续执行。
        """
        if self._pending_callback is None:
            raise RuntimeError("No pending input callback; engine is not waiting for input")

        callback = self._pending_callback
        self._pending_callback = None
        result = callback(choice)
        if result is not None:
            self._handle_signal(result)

    # ==================================================================
    # 核心调度循环
    # ==================================================================

    def _run_phase(self) -> None:
        """执行当前阶段并处理返回信号"""
        phase = self.state_machine.current_phase
        self.state.current_phase = phase

        # 通知 UI
        self._notify_phase_change()

        # 阶段变更事件
        self.event_bus.emit(GameEvent(GameEventType.PHASE_CHANGED, {"phase": phase.value}))

        # 游戏结束检查
        if phase == GamePhase.GAME_END:
            self._handle_game_end()
            return

        # NEXT_LOOP：重置状态后自动推进
        if phase == GamePhase.NEXT_LOOP:
            self.state.reset_for_new_loop()
            self.event_bus.emit(GameEvent(GameEventType.LOOP_STARTED, {"loop": self.state.current_loop}))
            self._advance_and_run()
            return

        # 获取阶段处理器
        handler = self.phase_handlers.get(phase)
        if handler is None:
            # 无处理器的阶段直接推进
            self._advance_and_run()
            return

        # 执行阶段逻辑
        signal = handler.execute(self.state)
        self._handle_signal(signal)

    def _handle_signal(self, signal: PhaseSignal) -> None:
        """处理阶段返回信号"""
        match signal:
            case PhaseComplete():
                self._advance_and_run()

            case WaitForInput() as wait:
                if wait.callback is None:
                    raise RuntimeError(
                        f"WaitForInput({wait.input_type}) missing callback"
                    )
                self._pending_callback = wait.callback
                self.ui_callback.on_wait_for_input(wait)

            case ForceLoopEnd() as fle:
                self.event_bus.emit(GameEvent(
                    GameEventType.LOOP_END_FORCED,
                    {"reason": fle.reason},
                ))
                self.state_machine.force_loop_end()
                self._advance_and_run()

    def _advance_and_run(self) -> None:
        """推进状态机并执行下一阶段"""
        prev_phase = self.state_machine.current_phase  # 保存推进前的阶段

        phase = self.state_machine.advance(
            is_final_day=(self.state.current_day >= self.state.script.days_per_loop),
            failure_reached=bool(self.state.failure_flags),
            is_last_loop=self.state.is_last_loop,
            protagonist_dead=self.state.protagonist_dead,
            has_final_guess=self.state.has_final_guess,
        )

        # 推进日期：从 TURN_END 推进到 TURN_START 时，说明开始新的一天
        if prev_phase == GamePhase.TURN_END and phase == GamePhase.TURN_START:
            self.state.advance_day()

        self._run_phase()

    # ==================================================================
    # 游戏结束
    # ==================================================================

    def _handle_game_end(self) -> None:
        """判定最终胜负"""
        if self.state.protagonist_dead:
            outcome = Outcome.MASTERMIND_WIN
        elif self.state.failure_flags:
            outcome = Outcome.MASTERMIND_WIN
        else:
            outcome = Outcome.PROTAGONIST_WIN

        self.event_bus.emit(GameEvent(GameEventType.GAME_ENDED, {"outcome": outcome.value}))
        self.ui_callback.on_game_over(outcome)

    # ==================================================================
    # UI 通知
    # ==================================================================

    def _notify_phase_change(self) -> None:
        """通知 UI 阶段变化"""
        # 默认使用主人公视角（热座模式下由 UI 层决定当前视角）
        from engine.models.enums import PlayerRole
        visible = self.visibility.filter_for_role(
            self.state, PlayerRole.PROTAGONIST_0
        )
        self.ui_callback.on_phase_changed(
            self.state_machine.current_phase, visible
        )

    def get_visible_state(self, role) -> VisibleGameState:
        """获取指定角色的可见状态"""
        return self.visibility.filter_for_role(self.state, role)
