from __future__ import annotations

import pytest

from engine.game_controller import GameController, UICallback
from engine.game_state import GameState
from engine.models.enums import GamePhase
from engine.phases.phase_base import WaitForInput


class _StubUI(UICallback):
    def __init__(self) -> None:
        self.waits: list[WaitForInput] = []
        self.phases: list[GamePhase] = []

    def on_phase_changed(self, phase: GamePhase, visible_state) -> None:
        self.phases.append(phase)

    def on_wait_for_input(self, wait: WaitForInput) -> None:
        self.waits.append(wait)


def test_wait_for_input_resume_advances_flow() -> None:
    ui = _StubUI()
    controller = GameController(ui_callback=ui)
    state = GameState()

    controller.start_game(state)

    # 进入第一处输入阶段（剧作家行动）
    assert controller.state_machine.current_phase == GamePhase.MASTERMIND_ACTION
    assert ui.waits, "expected at least one wait request"
    first_wait = ui.waits[-1]
    assert first_wait.callback is not None
    assert first_wait.options, "expected non-empty options for action cards"

    # 回填输入后应继续执行并进入下一处输入阶段（主人公行动）
    controller.provide_input(first_wait.options[0])
    assert controller.state_machine.current_phase == GamePhase.PROTAGONIST_ACTION
    assert len(ui.waits) >= 2
    assert ui.waits[-1].callback is not None


def test_provide_input_raises_without_pending_callback() -> None:
    controller = GameController()
    with pytest.raises(RuntimeError, match="No pending input callback"):
        controller.provide_input("anything")


def test_wait_for_input_without_callback_raises() -> None:
    controller = GameController()
    with pytest.raises(RuntimeError, match="missing callback"):
        controller._handle_signal(WaitForInput(input_type="broken"))


def test_game_loop_completes_game_prepare_to_loop_end_check() -> None:
    """
    验证完整游戏循环：
    1. 从 GAME_PREPARE 开始
    2. 自动回填所有 WaitForInput
    3. 推进到 LOOP_END_CHECK

    流程：
      GAME_PREPARE
      → LOOP_START, TURN_START
      → [天数循环] MASTERMIND_ACTION(等) → PROTAGONIST_ACTION(等)
      → ACTION_RESOLVE → PLAYWRIGHT_ABILITY → PROTAGONIST_ABILITY
      → INCIDENT → LEADER_ROTATE → TURN_END
      → (如非最终日则重复，否则进入 LOOP_END)
      → LOOP_END
      → LOOP_END_CHECK ✓
    """
    ui = _StubUI()
    controller = GameController(ui_callback=ui)
    state = GameState.create_minimal_test_state(
        loop_count=1,      # 1 个轮回（不触发 NEXT_LOOP）
        days_per_loop=1,   # 1 天（直接到最终日）
    )

    controller.start_game(state)

    # 循环回填所有 WaitForInput 直到游戏到达目标阶段或结束
    max_iterations = 50  # 防止无限循环
    iteration = 0

    while (controller.state_machine.current_phase != GamePhase.LOOP_END_CHECK
           and controller.state_machine.current_phase != GamePhase.GAME_END
           and iteration < max_iterations):

        # 如果有待处理的等待，回填输入
        if controller._pending_callback is not None:
            last_wait = ui.waits[-1]
            assert last_wait.options, f"No options for {last_wait.input_type}"
            controller.provide_input(last_wait.options[0])

        iteration += 1

    # 验证到达目标阶段
    assert controller.state_machine.current_phase == GamePhase.LOOP_END_CHECK, \
        f"Expected LOOP_END_CHECK but got {controller.state_machine.current_phase} after {iteration} iterations"

    # 额外验证：确保经过了 Stub 处理器
    phases_visited = ui.phases
    assert GamePhase.ACTION_RESOLVE in phases_visited, "Should have visited ACTION_RESOLVE"
    assert GamePhase.INCIDENT in phases_visited, "Should have visited INCIDENT"
