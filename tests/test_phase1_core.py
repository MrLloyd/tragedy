"""Phase 1 核心回归：状态机分支、同时裁定、事件触发链。"""

from __future__ import annotations

from engine.event_bus import EventBus, GameEventType
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.effects import Effect
from engine.models.enums import AreaId, EffectType, GamePhase, Outcome, TokenType
from engine.phases.phase_base import LoopEndHandler, PhaseComplete
from engine.resolvers.atomic_resolver import AtomicResolver
from engine.resolvers.death_resolver import DeathResolver
from engine.rules.module_loader import apply_loaded_module, load_module
from engine.state_machine import StateMachine


def test_state_machine_loop_end_check_branches() -> None:
    sm = StateMachine()
    sm.current_phase = GamePhase.LOOP_END_CHECK
    assert sm.advance(
        failure_reached=False,
        protagonist_dead=False,
        is_last_loop=False,
        has_final_guess=True,
    ) == GamePhase.GAME_END

    sm.current_phase = GamePhase.LOOP_END_CHECK
    assert sm.advance(
        failure_reached=True,
        protagonist_dead=False,
        is_last_loop=False,
        has_final_guess=True,
    ) == GamePhase.NEXT_LOOP

    sm.current_phase = GamePhase.LOOP_END_CHECK
    assert sm.advance(
        failure_reached=True,
        protagonist_dead=False,
        is_last_loop=True,
        has_final_guess=True,
    ) == GamePhase.FINAL_GUESS

    sm.current_phase = GamePhase.LOOP_END_CHECK
    assert sm.advance(
        failure_reached=True,
        protagonist_dead=False,
        is_last_loop=True,
        has_final_guess=False,
    ) == GamePhase.GAME_END


def test_state_machine_force_loop_end_jump() -> None:
    sm = StateMachine()
    sm.current_phase = GamePhase.INCIDENT
    sm.force_loop_end()

    assert sm.advance() == GamePhase.LOOP_END


def test_atomic_resolver_death_has_priority_over_failure() -> None:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    state = GameState.create_minimal_test_state()

    result = resolver.resolve(
        state,
        effects=[
            Effect(effect_type=EffectType.PROTAGONIST_DEATH, value="test"),
            Effect(effect_type=EffectType.PROTAGONIST_FAILURE, value="test"),
        ],
        sequential=False,
    )

    assert result.outcome == Outcome.PROTAGONIST_DEATH
    assert any(e.event_type == GameEventType.PROTAGONIST_DEATH for e in bus.log)
    assert not any(e.event_type == GameEventType.PROTAGONIST_FAILURE for e in bus.log)


def test_atomic_resolver_failure_when_soldier_blocks_death() -> None:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    state = GameState.create_minimal_test_state()
    state.soldier_protection_active = True

    result = resolver.resolve(
        state,
        effects=[
            Effect(effect_type=EffectType.PROTAGONIST_DEATH, value="test"),
            Effect(effect_type=EffectType.PROTAGONIST_FAILURE, value="test"),
        ],
        sequential=False,
    )

    assert result.outcome == Outcome.PROTAGONIST_FAILURE
    assert state.protagonist_dead is False
    assert any(e.event_type == GameEventType.PROTAGONIST_FAILURE for e in bus.log)


def test_loop_end_handler_emits_loop_ended_event() -> None:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    handler = LoopEndHandler(bus, resolver)
    state = GameState.create_minimal_test_state()
    state.current_loop = 2

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert any(
        e.event_type == GameEventType.LOOP_ENDED and e.data.get("loop") == 2
        for e in bus.log
    )


def test_on_death_ability_is_published_and_triggered() -> None:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    state = GameState()
    loaded = load_module("first_steps")
    apply_loaded_module(state, loaded)

    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="key_person",
        original_identity_id="key_person",
    )

    result = resolver.resolve(
        state,
        effects=[Effect(effect_type=EffectType.KILL_CHARACTER, target="key")],
        sequential=False,
    )

    assert result.outcome == Outcome.PROTAGONIST_FAILURE
    assert any(
        e.event_type == GameEventType.ABILITY_DECLARED
        and e.data.get("ability_id") == "key_person_on_death"
        for e in bus.log
    )
    assert any(e.event_type == GameEventType.PROTAGONIST_FAILURE for e in bus.log)


def test_on_other_death_ability_is_published_and_triggered() -> None:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    state = GameState()
    loaded = load_module("basic_tragedy_x")
    apply_loaded_module(state, loaded)

    state.characters["beloved"] = CharacterState(
        character_id="beloved",
        name="心上人",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="beloved",
        original_identity_id="beloved",
    )
    state.characters["lover"] = CharacterState(
        character_id="lover",
        name="求爱者",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="lover",
        original_identity_id="lover",
    )

    result = resolver.resolve(
        state,
        effects=[Effect(effect_type=EffectType.KILL_CHARACTER, target="lover")],
        sequential=False,
    )

    assert result.outcome == Outcome.NONE
    assert state.characters["beloved"].tokens.get(TokenType.PARANOIA) == 6
    assert any(
        e.event_type == GameEventType.ABILITY_DECLARED
        and e.data.get("ability_id") == "beloved_on_lover_death_gain_paranoia"
        for e in bus.log
    )
