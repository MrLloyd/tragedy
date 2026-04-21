"""Phase 4 P4-5 / P4-6 回归测试。"""

from __future__ import annotations

import pytest

from engine.event_bus import EventBus
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.effects import Effect
from engine.models.enums import AbilityTiming, AbilityType, AreaId, EffectType, TokenType, Trait
from engine.models.incident import IncidentSchedule
from engine.models.script import CharacterSetup
from engine.resolvers.ability_resolver import AbilityResolver
from engine.resolvers.atomic_resolver import AtomicResolver
from engine.resolvers.death_resolver import DeathResolver
from engine.rules.module_loader import apply_loaded_module, build_game_state_from_module, load_module
from engine.rules.script_validator import ScriptValidationError


def test_change_identity_effect_and_loop_reset_restore_original_identity() -> None:
    state = GameState()
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["target"] = CharacterState(
        character_id="target",
        name="目标",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
    )

    resolver = AtomicResolver(EventBus(), DeathResolver())
    resolver.resolve(
        state,
        [Effect(effect_type=EffectType.CHANGE_IDENTITY, target="target", value="killer")],
    )

    assert state.characters["target"].identity_id == "killer"
    assert Trait.IGNORE_GOODWILL in AbilityResolver().active_traits(state, "target")

    state.reset_for_new_loop()

    assert state.characters["target"].identity_id == "平民"
    assert state.characters["target"].original_identity_id == "平民"


def test_paranoia_expansion_virus_switches_commoner_identity_realtime() -> None:
    state = GameState()
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["commoner"] = CharacterState(
        character_id="commoner",
        name="平民",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["victim"] = CharacterState(
        character_id="victim",
        name="目标",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="friend",
        original_identity_id="friend",
    )
    resolver = AbilityResolver()

    state.characters["commoner"].tokens.add(TokenType.PARANOIA, 3)
    abilities = resolver.collect_abilities(
        state,
        timing=AbilityTiming.TURN_END,
        ability_type=AbilityType.MANDATORY,
    )

    assert state.characters["commoner"].identity_id == "serial_killer"
    assert any(candidate.source_id == "commoner" for candidate in abilities)

    state.characters["commoner"].tokens.remove(TokenType.PARANOIA, 1)
    abilities = resolver.collect_abilities(
        state,
        timing=AbilityTiming.TURN_END,
        ability_type=AbilityType.MANDATORY,
    )

    assert state.characters["commoner"].identity_id == "平民"
    assert not any(candidate.source_id == "commoner" for candidate in abilities)


def test_paranoia_expansion_virus_can_generate_serial_killer_without_module_definition() -> None:
    state = GameState()
    state.characters["commoner"] = CharacterState(
        character_id="commoner",
        name="平民",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["victim"] = CharacterState(
        character_id="victim",
        name="目标",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="friend",
        original_identity_id="friend",
    )
    state.identity_defs["friend"] = load_module("basic_tragedy_x").identity_defs["friend"]

    state.characters["commoner"].tokens.add(TokenType.PARANOIA, 3)
    abilities = AbilityResolver().collect_abilities(
        state,
        timing=AbilityTiming.TURN_END,
        ability_type=AbilityType.MANDATORY,
    )

    assert state.characters["commoner"].identity_id == "serial_killer"
    assert "serial_killer" in state.identity_defs
    assert any(candidate.source_id == "commoner" for candidate in abilities)


def test_time_traveler_immortal_trait_uses_current_identity_traits() -> None:
    state = GameState()
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["traveler"] = CharacterState(
        character_id="traveler",
        name="时间旅者",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="time_traveler",
        original_identity_id="time_traveler",
    )

    AtomicResolver(EventBus(), DeathResolver()).resolve(
        state,
        [Effect(effect_type=EffectType.KILL_CHARACTER, target="traveler")],
    )

    assert state.characters["traveler"].is_alive is True


def test_btx_script_validator_accepts_valid_cursed_contract_script() -> None:
    state = build_game_state_from_module(
        "basic_tragedy_x",
        loop_count=2,
        days_per_loop=3,
        rule_y_id="btx_cursed_contract",
        rule_x_ids=["btx_rumors", "btx_latent_serial_killer"],
        character_setups=[
            CharacterSetup("idol", "key_person"),
            CharacterSetup("male_student", "rumormonger"),
            CharacterSetup("soldier", "serial_killer"),
            CharacterSetup("detective", "friend"),
        ],
        incidents=[IncidentSchedule("murder", day=1, perpetrator_id="idol")],
    )

    assert state.script.rule_y is not None
    assert state.script.rule_y.rule_id == "btx_cursed_contract"


def test_btx_script_validator_rejects_key_person_not_girl() -> None:
    with pytest.raises(ScriptValidationError) as excinfo:
        build_game_state_from_module(
            "basic_tragedy_x",
            loop_count=2,
            days_per_loop=3,
            rule_y_id="btx_cursed_contract",
            rule_x_ids=["btx_rumors", "btx_latent_serial_killer"],
            character_setups=[
                CharacterSetup("soldier", "key_person"),
                CharacterSetup("male_student", "rumormonger"),
                CharacterSetup("detective", "serial_killer"),
                CharacterSetup("idol", "friend"),
            ],
            incidents=[IncidentSchedule("murder", day=1, perpetrator_id="soldier")],
        )

    assert any("key_person must be assigned to a girl" in issue.message for issue in excinfo.value.issues)


def test_script_validator_supports_skip_for_debug_or_partial_import() -> None:
    state = build_game_state_from_module(
        "first_steps",
        rule_y_id="fs_murder_plan",
        rule_x_ids=["fs_ripper_shadow"],
        character_setups=[CharacterSetup("ai", "平民")],
        incidents=[IncidentSchedule("murder", day=1, perpetrator_id="ai")],
        skip_script_validation=True,
    )

    assert state.characters["ai"].identity_id == "平民"


def test_script_validator_rejects_character_script_creation_constraints() -> None:
    with pytest.raises(ScriptValidationError) as excinfo:
        build_game_state_from_module(
            "first_steps",
            rule_y_id="fs_murder_plan",
            rule_x_ids=["fs_ripper_shadow"],
            character_setups=[
                CharacterSetup("ai", "平民"),
                CharacterSetup("female_student", "key_person"),
                CharacterSetup("soldier", "killer"),
                CharacterSetup("office_worker", "mastermind"),
                CharacterSetup("male_student", "rumormonger"),
                CharacterSetup("detective", "serial_killer"),
            ],
            incidents=[IncidentSchedule("murder", day=1, perpetrator_id="ai")],
        )

    assert any("cannot be assigned commoner" in issue.message for issue in excinfo.value.issues)
