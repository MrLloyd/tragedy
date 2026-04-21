from __future__ import annotations

from engine.game_controller import GameController, UICallback
from engine.models.cards import PlacementIntent
from engine.models.enums import AreaId, CardType, GamePhase, Outcome
from engine.models.incident import IncidentSchedule
from engine.models.script import CharacterSetup
from engine.phases.phase_base import WaitForInput
from engine.rules.module_loader import build_game_state_from_module


class _ScenarioUI(UICallback):
    def __init__(self) -> None:
        self.waits: list[WaitForInput] = []
        self.phases: list[GamePhase] = []
        self.outcome: Outcome | None = None

    def on_phase_changed(self, phase: GamePhase, visible_state) -> None:
        self.phases.append(phase)

    def on_wait_for_input(self, wait: WaitForInput) -> None:
        self.waits.append(wait)

    def on_game_over(self, outcome: Outcome) -> None:
        self.outcome = outcome


def test_first_steps_three_loop_three_day_suicide_scenario_closes() -> None:
    state = build_game_state_from_module(
        "first_steps",
        loop_count=3,
        days_per_loop=3,
        rule_y_id="fs_murder_plan",
        rule_x_ids=["fs_ripper_shadow"],
        character_setups=[
            CharacterSetup("male_student", "mastermind"),
            CharacterSetup("female_student", "key_person"),
            CharacterSetup("idol", "rumormonger"),
            CharacterSetup("office_worker", "killer"),
            CharacterSetup("shrine_maiden", "serial_killer"),
        ],
        incidents=[
            IncidentSchedule("suicide", day=3, perpetrator_id="female_student"),
        ],
    )
    ui = _ScenarioUI()
    controller = GameController(ui_callback=ui)
    controller.state = state
    controller.state_machine.reset()
    controller._run_phase()

    for _ in range(200):
        if controller.state_machine.current_phase == GamePhase.GAME_END:
            break
        assert controller._pending_callback is not None
        wait = ui.waits[-1]
        controller.provide_input(_choice_for(wait))

    assert controller.state_machine.current_phase == GamePhase.GAME_END
    assert ui.outcome == Outcome.MASTERMIND_WIN
    assert len(controller.state.loop_history) == 3
    assert all(
        snapshot.incidents_occurred == ["suicide"]
        for snapshot in controller.state.loop_history
    )
    assert GamePhase.NEXT_LOOP in ui.phases
    assert GamePhase.INCIDENT in ui.phases


def _choice_for(wait: WaitForInput):
    if wait.input_type == "place_action_cards":
        paranoia_card = _card(wait.options, CardType.PARANOIA_PLUS_1)
        fillers = [card for card in wait.options if card is not paranoia_card][:2]
        return [
            PlacementIntent(
                card=paranoia_card,
                target_type="character",
                target_id="female_student",
            ),
            *[
                PlacementIntent(
                    card=card,
                    target_type="board",
                    target_id=AreaId.CITY.value,
                )
                for card in fillers
            ],
        ]
    if wait.input_type == "place_action_card":
        return PlacementIntent(
            card=wait.options[0],
            target_type="board",
            target_id=AreaId.CITY.value,
        )
    if "pass" in wait.options:
        return "pass"
    return wait.options[0]


def _card(cards: list, card_type: CardType):
    return next(card for card in cards if card.card_type == card_type)
