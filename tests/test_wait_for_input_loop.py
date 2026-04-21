from __future__ import annotations

import pytest

from engine.game_controller import GameController, UICallback
from engine.models.cards import PlacementIntent
from engine.models.enums import AreaId, GamePhase
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
    controller.start_game("first_steps", loop_count=1, days_per_loop=1)

    # 进入第一处输入阶段（剧作家行动）
    assert controller.state_machine.current_phase == GamePhase.MASTERMIND_ACTION
    assert ui.waits, "expected at least one wait request"
    first_wait = ui.waits[-1]
    assert first_wait.callback is not None
    assert first_wait.options, "expected non-empty options for action cards"

    # 回填输入：提交 3 张 PlacementIntent（剧作家放牌需要恰好 3 张）
    cards = first_wait.options[:3]
    intents = [
        PlacementIntent(card=cards[0], target_type="board", target_id=AreaId.SCHOOL.value),
        PlacementIntent(card=cards[1], target_type="board", target_id=AreaId.HOSPITAL.value),
        PlacementIntent(card=cards[2], target_type="board", target_id=AreaId.SHRINE.value),
    ]
    controller.provide_input(intents)
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
    controller.start_game(
        "first_steps",
        loop_count=1,      # 1 个轮回（不触发 NEXT_LOOP）
        days_per_loop=1,   # 1 天（直接到最终日）
    )

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

            # 根据输入类型生成不同的输入
            if last_wait.input_type == "place_action_cards":
                # 剧作家放牌：需要提交 3 张 PlacementIntent
                cards = last_wait.options[:3]
                intents = [
                    PlacementIntent(card=cards[0], target_type="board", target_id=AreaId.SCHOOL.value),
                    PlacementIntent(card=cards[1], target_type="board", target_id=AreaId.HOSPITAL.value),
                    PlacementIntent(card=cards[2], target_type="board", target_id=AreaId.SHRINE.value),
                ]
                controller.provide_input(intents)
            elif last_wait.input_type == "place_action_card":
                # 主人公放牌：提交 1 张 PlacementIntent
                intent = PlacementIntent(
                    card=last_wait.options[0],
                    target_type="board",
                    target_id=AreaId.SCHOOL.value,
                )
                controller.provide_input(intent)
            else:
                # 其他输入类型（final_guess）：直接提交第一个选项
                controller.provide_input(last_wait.options[0])

        iteration += 1

    # LOOP_END_CHECK 可能在一次 provide_input 的同步递归里立即推进到 GAME_END，
    # 因此 current_phase 常为 GAME_END；以 phase 通知历史为准。
    phases_visited = ui.phases
    assert GamePhase.LOOP_END_CHECK in phases_visited, (
        f"Expected LOOP_END_CHECK in phase history, got phases={phases_visited}, "
        f"current_phase={controller.state_machine.current_phase} after {iteration} iterations"
    )
    assert controller.state_machine.current_phase in (
        GamePhase.LOOP_END_CHECK,
        GamePhase.GAME_END,
    )

    # 额外验证：确保经过了 Stub 处理器
    assert GamePhase.ACTION_RESOLVE in phases_visited, "Should have visited ACTION_RESOLVE"
    assert GamePhase.INCIDENT in phases_visited, "Should have visited INCIDENT"
