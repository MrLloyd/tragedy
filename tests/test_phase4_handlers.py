from __future__ import annotations

from engine.event_bus import EventBus, GameEventType
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.enums import AbilityTiming, AreaId, TokenType
from engine.phases.phase_base import (
    ForceLoopEnd,
    LoopEndHandler,
    LoopStartHandler,
    PhaseComplete,
    PlaywrightAbilityHandler,
    ProtagonistAbilityHandler,
    TurnEndHandler,
    WaitForInput,
)
from engine.resolvers.atomic_resolver import AtomicResolver
from engine.resolvers.death_resolver import DeathResolver
from engine.rules.module_loader import apply_loaded_module, load_module


def _resolver_bundle() -> tuple[EventBus, AtomicResolver]:
    bus = EventBus()
    return bus, AtomicResolver(bus, DeathResolver())


def _ability_choice(wait: WaitForInput, ability_id: str):
    return next(
        option for option in wait.options
        if getattr(option, "ability", None) is not None
        and option.ability.ability_id == ability_id
    )


def test_loop_start_handler_executes_friend_reveal_effect() -> None:
    bus, resolver = _resolver_bundle()
    handler = LoopStartHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["friend"] = CharacterState(
        character_id="friend",
        name="亲友",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="friend",
        original_identity_id="friend",
        revealed=True,
    )

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.characters["friend"].tokens.get(TokenType.GOODWILL) == 1


def test_loop_start_handler_applies_causal_line_from_last_snapshot() -> None:
    bus, resolver = _resolver_bundle()
    handler = LoopStartHandler(bus, resolver)
    state = GameState()
    loaded = load_module("basic_tragedy_x")
    apply_loaded_module(state, loaded)
    state.script.rules_x = [
        next(rule for rule in loaded.module_def.rules_x if rule.rule_id == "btx_causal_line")
    ]
    state.characters["survivor"] = CharacterState(
        character_id="survivor",
        name="角色A",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["dead"] = CharacterState(
        character_id="dead",
        name="角色B",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="平民",
        original_identity_id="平民",
        is_alive=False,
    )
    state.characters["survivor"].tokens.add(TokenType.GOODWILL, 1)
    state.characters["dead"].tokens.add(TokenType.GOODWILL, 2)
    state.save_loop_snapshot()
    state.reset_for_new_loop()

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.characters["survivor"].tokens.get(TokenType.PARANOIA) == 2
    assert state.characters["dead"].tokens.get(TokenType.PARANOIA) == 2


def test_loop_start_handler_applies_causal_line_and_friend_reveal_together() -> None:
    bus, resolver = _resolver_bundle()
    handler = LoopStartHandler(bus, resolver)
    state = GameState()
    loaded = load_module("basic_tragedy_x")
    apply_loaded_module(state, loaded)
    state.script.rules_x = [
        next(rule for rule in loaded.module_def.rules_x if rule.rule_id == "btx_causal_line")
    ]
    state.characters["friend"] = CharacterState(
        character_id="friend",
        name="亲友",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="friend",
        original_identity_id="friend",
        revealed=True,
    )
    state.characters["friend"].tokens.add(TokenType.GOODWILL, 1)
    state.save_loop_snapshot()
    state.reset_for_new_loop()
    state.characters["friend"].revealed = True

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.characters["friend"].tokens.get(TokenType.PARANOIA) == 2
    assert state.characters["friend"].tokens.get(TokenType.GOODWILL) == 1


def test_playwright_ability_handler_declares_and_resolves_targeted_ability() -> None:
    bus, resolver = _resolver_bundle()
    handler = PlaywrightAbilityHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["mastermind"] = CharacterState(
        character_id="mastermind",
        name="主谋",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="mastermind",
        original_identity_id="mastermind",
    )
    state.characters["target"] = CharacterState(
        character_id="target",
        name="目标",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="平民",
        original_identity_id="平民",
    )

    signal = handler.execute(state)

    assert isinstance(signal, WaitForInput)
    assert signal.input_type == "choose_playwright_ability"
    choice = next(
        option for option in signal.options
        if getattr(option, "ability", None) is not None
        and option.ability.ability_id == "mastermind_playwright_place_intrigue_character"
    )
    target_wait = signal.callback(choice)
    assert isinstance(target_wait, WaitForInput)
    assert target_wait.input_type == "choose_ability_target"

    follow_up = target_wait.callback("target")

    assert isinstance(follow_up, WaitForInput)
    assert state.characters["target"].tokens.get(TokenType.INTRIGUE) == 1
    assert any(
        event.event_type == GameEventType.ABILITY_DECLARED
        and event.data.get("ability_id") == "mastermind_playwright_place_intrigue_character"
        for event in bus.log
    )


def test_mastermind_playwright_ability_places_intrigue_on_board() -> None:
    bus, resolver = _resolver_bundle()
    handler = PlaywrightAbilityHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["mastermind"] = CharacterState(
        character_id="mastermind",
        name="主谋",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="mastermind",
        original_identity_id="mastermind",
    )

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = _ability_choice(signal, "mastermind_playwright_place_intrigue_board")

    follow_up = signal.callback(choice)

    assert isinstance(follow_up, WaitForInput)
    assert state.board.areas[AreaId.SCHOOL].tokens.get(TokenType.INTRIGUE) == 1
    assert any(
        event.event_type == GameEventType.ABILITY_DECLARED
        and event.data.get("ability_id") == "mastermind_playwright_place_intrigue_board"
        for event in bus.log
    )


def test_rumormonger_playwright_ability_places_paranoia_in_same_area() -> None:
    bus, resolver = _resolver_bundle()
    handler = PlaywrightAbilityHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["rumor"] = CharacterState(
        character_id="rumor",
        name="传谣人",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="rumormonger",
        original_identity_id="rumormonger",
    )
    state.characters["target"] = CharacterState(
        character_id="target",
        name="目标",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="平民",
        original_identity_id="平民",
    )

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = _ability_choice(signal, "rumormonger_playwright_place_paranoia")
    target_wait = signal.callback(choice)
    assert isinstance(target_wait, WaitForInput)

    follow_up = target_wait.callback("target")

    assert isinstance(follow_up, WaitForInput)
    assert state.characters["target"].tokens.get(TokenType.PARANOIA) == 1
    assert any(
        event.event_type == GameEventType.ABILITY_DECLARED
        and event.data.get("ability_id") == "rumormonger_playwright_place_paranoia"
        for event in bus.log
    )


def test_protagonist_ability_handler_supports_refuse_and_allow() -> None:
    bus, resolver = _resolver_bundle()
    handler = ProtagonistAbilityHandler(bus, resolver)
    state = GameState()
    state.characters["ai"] = CharacterState(
        character_id="ai",
        name="AI",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
        goodwill_ability_texts=["能力1", "", "", ""],
        goodwill_ability_goodwill_costs=[1, 0, 0, 0],
        goodwill_ability_once_per_loop=[False],
    )
    state.characters["ai"].tokens.add(TokenType.GOODWILL, 2)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = next(option for option in signal.options if getattr(option, "ability", None) is not None)

    refuse_wait = signal.callback(choice)
    assert isinstance(refuse_wait, WaitForInput)
    assert refuse_wait.input_type == "respond_goodwill_ability"
    next_signal = refuse_wait.callback("refuse")
    assert isinstance(next_signal, WaitForInput)
    assert state.characters["ai"].tokens.get(TokenType.GOODWILL) == 2
    assert any(event.event_type == GameEventType.ABILITY_REFUSED for event in bus.log)

    allow_wait = next_signal.callback(choice)
    assert isinstance(allow_wait, WaitForInput)
    done = allow_wait.callback("allow")
    assert isinstance(done, WaitForInput)
    assert state.characters["ai"].tokens.get(TokenType.GOODWILL) == 1


def test_protagonist_ability_refuse_consumes_once_per_loop_without_cost() -> None:
    bus, resolver = _resolver_bundle()
    handler = ProtagonistAbilityHandler(bus, resolver)
    state = GameState()
    state.characters["ai"] = CharacterState(
        character_id="ai",
        name="AI",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
        goodwill_ability_texts=["能力1", "", "", ""],
        goodwill_ability_goodwill_costs=[1, 0, 0, 0],
        goodwill_ability_once_per_loop=[True],
    )
    state.characters["ai"].tokens.add(TokenType.GOODWILL, 2)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = next(option for option in signal.options if getattr(option, "ability", None) is not None)
    refuse_wait = signal.callback(choice)
    assert isinstance(refuse_wait, WaitForInput)

    next_signal = refuse_wait.callback("refuse")

    assert isinstance(next_signal, PhaseComplete)
    assert state.characters["ai"].tokens.get(TokenType.GOODWILL) == 2
    assert any(event.event_type == GameEventType.ABILITY_REFUSED for event in bus.log)


def test_protagonist_ability_ignores_refusal_when_identity_ignores_goodwill() -> None:
    bus, resolver = _resolver_bundle()
    handler = ProtagonistAbilityHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
        goodwill_ability_texts=["能力1", "", "", ""],
        goodwill_ability_goodwill_costs=[1, 0, 0, 0],
        goodwill_ability_once_per_loop=[False],
    )
    state.characters["killer"].tokens.add(TokenType.GOODWILL, 1)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = next(option for option in signal.options if getattr(option, "ability", None) is not None)
    follow_up = signal.callback(choice)

    assert isinstance(follow_up, PhaseComplete)
    assert state.characters["killer"].tokens.get(TokenType.GOODWILL) == 0


def test_turn_end_handler_executes_mandatory_then_optional() -> None:
    bus, resolver = _resolver_bundle()
    handler = TurnEndHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["serial"] = CharacterState(
        character_id="serial",
        name="杀人狂",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="serial_killer",
        original_identity_id="serial_killer",
    )
    state.characters["victim"] = CharacterState(
        character_id="victim",
        name="牺牲者",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )
    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="key_person",
        original_identity_id="key_person",
    )
    state.characters["key"].tokens.add(TokenType.INTRIGUE, 2)

    signal = handler.execute(state)

    assert isinstance(signal, WaitForInput)
    assert not state.characters["victim"].is_alive
    assert signal.input_type == "choose_turn_end_ability"


def test_killer_turn_end_ability_kills_key_person_and_forces_loop_end() -> None:
    bus, resolver = _resolver_bundle()
    handler = TurnEndHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )
    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="key_person",
        original_identity_id="key_person",
    )
    state.characters["key"].tokens.add(TokenType.INTRIGUE, 2)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = _ability_choice(signal, "killer_turn_end_kill_key_person")

    result = signal.callback(choice)

    assert isinstance(result, ForceLoopEnd)
    assert result.reason == "killer_turn_end_kill_key_person"
    assert not state.characters["key"].is_alive
    assert "key_person_dead" in state.failure_flags


def test_killer_turn_end_ability_causes_protagonist_death_at_four_intrigue() -> None:
    bus, resolver = _resolver_bundle()
    handler = TurnEndHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )
    state.characters["killer"].tokens.add(TokenType.INTRIGUE, 4)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = _ability_choice(signal, "killer_turn_end_protagonist_death")

    result = signal.callback(choice)

    assert isinstance(result, ForceLoopEnd)
    assert result.reason == "killer_turn_end_protagonist_death"
    assert state.protagonist_dead is True


def test_serial_killer_mandatory_turn_end_ability_kills_other_lone_character() -> None:
    bus, resolver = _resolver_bundle()
    handler = TurnEndHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("first_steps"))
    state.characters["serial"] = CharacterState(
        character_id="serial",
        name="杀人狂",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="serial_killer",
        original_identity_id="serial_killer",
    )
    state.characters["victim"] = CharacterState(
        character_id="victim",
        name="牺牲者",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="平民",
        original_identity_id="平民",
    )

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.characters["serial"].is_alive
    assert not state.characters["victim"].is_alive
    assert any(
        event.event_type == GameEventType.ABILITY_DECLARED
        and event.data.get("ability_id") == "serial_killer_turn_end_kill_lone_target"
        for event in bus.log
    )


def test_turn_end_handler_executes_time_traveler_final_day_failure() -> None:
    bus, resolver = _resolver_bundle()
    handler = TurnEndHandler(bus, resolver)
    state = GameState()
    state.script.days_per_loop = 3
    state.current_day = 3
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["traveler"] = CharacterState(
        character_id="traveler",
        name="时间旅者",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="time_traveler",
        original_identity_id="time_traveler",
    )
    state.characters["traveler"].tokens.add(TokenType.GOODWILL, 2)

    signal = handler.execute(state)
    assert isinstance(signal, WaitForInput)
    choice = next(
        option for option in signal.options
        if getattr(option, "ability", None) is not None
        and option.ability.ability_id == "time_traveler_final_day_failure"
    )

    result = signal.callback(choice)

    assert isinstance(result, ForceLoopEnd)
    assert result.reason == "time_traveler_final_day_failure"
    assert "time_traveler_goodwill_2" in state.failure_flags


def test_loop_end_handler_resolves_loss_conditions_and_saves_snapshot() -> None:
    bus, resolver = _resolver_bundle()
    handler = LoopEndHandler(bus, resolver)
    state = GameState()
    apply_loaded_module(state, load_module("basic_tragedy_x"))
    state.characters["friend"] = CharacterState(
        character_id="friend",
        name="亲友",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="friend",
        original_identity_id="friend",
        is_alive=False,
    )

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert "friend_dead" in state.failure_flags
    assert state.characters["friend"].revealed is True
    assert len(state.loop_history) == 1
