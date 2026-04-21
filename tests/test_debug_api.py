from __future__ import annotations

from engine.debug import (
    DebugCharacterSetup,
    DebugSetup,
    apply_debug_setup,
    build_debug_state,
    get_debug_snapshot,
    list_debug_abilities,
    trigger_debug_ability,
    trigger_debug_incident,
)
from engine.models.enums import AbilityTiming, AbilityType, AreaId, GamePhase, TokenType
from engine.models.incident import IncidentSchedule
from engine.models.script import CharacterSetup


def test_debug_build_setup_and_snapshot() -> None:
    session = build_debug_state(
        "first_steps",
        rule_y_id="fs_murder_plan",
        rule_x_ids=["fs_ripper_shadow"],
        character_setups=[
            CharacterSetup("ai", "平民"),
            CharacterSetup("office_worker", "mastermind"),
        ],
        incidents=[IncidentSchedule("murder", day=1, perpetrator_id="ai")],
    )

    apply_debug_setup(
        session,
        DebugSetup(
            current_day=2,
            current_phase=GamePhase.PLAYWRIGHT_ABILITY,
            characters=[
                DebugCharacterSetup(
                    "office_worker",
                    area="school",
                    tokens={"intrigue": 1},
                    revealed=True,
                )
            ],
        ),
    )
    snapshot = get_debug_snapshot(session)

    assert snapshot["current_day"] == 2
    assert snapshot["current_phase"] == "playwright_ability"
    assert snapshot["characters"]["office_worker"]["area"] == "school"
    assert snapshot["characters"]["office_worker"]["tokens"]["intrigue"] == 1
    assert snapshot["characters"]["office_worker"]["revealed"] is True
    assert snapshot["debug_log"][0]["action"] == "apply_debug_setup"


def test_debug_list_and_trigger_ability_uses_official_resolvers() -> None:
    session = build_debug_state(
        "first_steps",
        rule_y_id="fs_murder_plan",
        rule_x_ids=["fs_ripper_shadow"],
        character_setups=[
            CharacterSetup("office_worker", "mastermind"),
            CharacterSetup("ai", "平民"),
        ],
        incidents=[IncidentSchedule("murder", day=1, perpetrator_id="ai")],
    )
    apply_debug_setup(
        session,
        DebugSetup(
            characters=[
                DebugCharacterSetup("office_worker", area="school"),
                DebugCharacterSetup("ai", area="school"),
            ],
        ),
    )

    abilities = list_debug_abilities(
        session,
        actor_id="office_worker",
        timing=AbilityTiming.PLAYWRIGHT_ABILITY,
        ability_type=AbilityType.OPTIONAL,
    )
    assert any(item.ability.ability_id == "mastermind_playwright_place_intrigue_character" for item in abilities)

    result = trigger_debug_ability(
        session,
        actor_id="office_worker",
        ability_id="mastermind_playwright_place_intrigue_character",
        timing="playwright_ability",
        ability_type="optional",
        target_choices=["ai"],
    )

    assert result.resolution.mutations[0].mutation_type == "token_change"
    assert session.state.characters["ai"].tokens.get(TokenType.INTRIGUE) == 1
    assert any(event.data.get("ability_id") == "mastermind_playwright_place_intrigue_character" for event in session.event_bus.log)


def test_debug_trigger_incident_records_public_result() -> None:
    session = build_debug_state(
        "basic_tragedy_x",
        rule_y_id="btx_murder_plan",
        rule_x_ids=["btx_rumors", "btx_latent_serial_killer"],
        character_setups=[
            CharacterSetup("ai", "平民"),
            CharacterSetup("office_worker", "平民"),
        ],
        incidents=[IncidentSchedule("murder", day=1, perpetrator_id="ai")],
    )
    apply_debug_setup(
        session,
        DebugSetup(
            characters=[
                DebugCharacterSetup("ai", area="hospital", tokens={"paranoia": 4}),
                DebugCharacterSetup("office_worker", area="hospital"),
            ],
        ),
    )

    result = trigger_debug_incident(
        session,
        incident_id="hospital_accident",
        perpetrator_id="ai",
    )
    assert result.resolution.occurred is True
    assert result.resolution.has_phenomenon is False

    session.state.board.areas[AreaId.HOSPITAL].tokens.add(TokenType.INTRIGUE, 1)
    result = trigger_debug_incident(
        session,
        incident_id="hospital_accident",
        perpetrator_id="ai",
    )
    assert result.resolution.has_phenomenon is True
    assert session.state.characters["office_worker"].is_alive is False

    snapshot = get_debug_snapshot(session)
    assert snapshot["incident_results"][-1]["incident_id"] == "hospital_accident"
    assert snapshot["incident_results"][-1]["has_phenomenon"] is True
    assert "perpetrator_id" not in snapshot["incident_results"][-1]
    assert session.debug_log[-1]["action"] == "trigger_debug_incident"
