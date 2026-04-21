"""P4 调试 API。

这些入口只用于测试与未来 UI 调试面板，不进入正式游戏流程。
受控 setup 可以构造前置状态；能力和事件触发仍走正式 resolver。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.event_bus import EventBus, GameEvent, GameEventType
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.effects import Effect
from engine.models.enums import AbilityTiming, AbilityType, AreaId, GamePhase, Outcome, TokenType
from engine.models.incident import IncidentSchedule
from engine.resolvers.ability_resolver import AbilityCandidate, AbilityResolver
from engine.resolvers.atomic_resolver import AtomicResolver, ResolutionResult
from engine.resolvers.death_resolver import DeathResolver
from engine.resolvers.incident_resolver import IncidentResolver, IncidentResolution
from engine.rules.module_loader import build_game_state_from_module


@dataclass
class DebugSession:
    state: GameState
    event_bus: EventBus
    death_resolver: DeathResolver
    atomic_resolver: AtomicResolver
    ability_resolver: AbilityResolver
    incident_resolver: IncidentResolver
    debug_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DebugCharacterSetup:
    character_id: str
    area: str | None = None
    tokens: dict[str, int] = field(default_factory=dict)
    is_alive: bool | None = None
    is_removed: bool | None = None
    revealed: bool | None = None
    identity_id: str | None = None
    current_as_original: bool = False


@dataclass
class DebugSetup:
    current_loop: int | None = None
    current_day: int | None = None
    current_phase: str | GamePhase | None = None
    characters: list[DebugCharacterSetup] = field(default_factory=list)


@dataclass
class DebugAbilityResult:
    candidate: AbilityCandidate
    resolution: ResolutionResult
    forced_loop_end: bool = False


@dataclass
class DebugIncidentResult:
    resolution: IncidentResolution
    forced_loop_end: bool = False


def build_debug_state(
    module_id: str,
    *,
    skip_script_validation: bool = True,
    **kwargs: Any,
) -> DebugSession:
    """创建调试局；默认跳过剧本校验，仅供测试/UI 调试模式使用。"""
    state = build_game_state_from_module(
        module_id,
        skip_script_validation=skip_script_validation,
        **kwargs,
    )
    event_bus = EventBus()
    death_resolver = DeathResolver()
    atomic_resolver = AtomicResolver(event_bus, death_resolver)
    ability_resolver = AbilityResolver()
    incident_resolver = IncidentResolver(event_bus, atomic_resolver)
    return DebugSession(
        state=state,
        event_bus=event_bus,
        death_resolver=death_resolver,
        atomic_resolver=atomic_resolver,
        ability_resolver=ability_resolver,
        incident_resolver=incident_resolver,
    )


def apply_debug_setup(session: DebugSession, setup: DebugSetup) -> GameState:
    """受控设置前置状态；不提供任意字段直改能力。"""
    state = session.state
    if setup.current_loop is not None:
        state.current_loop = setup.current_loop
    if setup.current_day is not None:
        state.current_day = setup.current_day
    if setup.current_phase is not None:
        state.current_phase = _coerce_phase(setup.current_phase)

    for character_setup in setup.characters:
        character = state.characters.get(character_setup.character_id)
        if character is None:
            raise ValueError(f"unknown character: {character_setup.character_id!r}")
        _apply_character_setup(character, character_setup)

    session.debug_log.append({
        "action": "apply_debug_setup",
        "current_loop": state.current_loop,
        "current_day": state.current_day,
        "current_phase": state.current_phase.value,
        "characters": [item.character_id for item in setup.characters],
    })
    return state


def list_debug_abilities(
    session: DebugSession,
    *,
    actor_id: str | None = None,
    timing: AbilityTiming | str | None = None,
    ability_type: AbilityType | str | None = None,
    alive_only: bool = True,
) -> list[AbilityCandidate]:
    """列出当前可发动能力；可按 actor / timing / ability_type 过滤。"""
    timings = [_coerce_timing(timing)] if timing is not None else list(AbilityTiming)
    coerced_ability_type = _coerce_ability_type(ability_type) if ability_type is not None else None
    candidates: list[AbilityCandidate] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for candidate_timing in timings:
        for candidate in session.ability_resolver.collect_abilities(
            session.state,
            timing=candidate_timing,
            ability_type=coerced_ability_type,
            alive_only=alive_only,
        ):
            if actor_id is not None and candidate.source_id != actor_id:
                continue
            key = (
                candidate.source_kind,
                candidate.source_id,
                candidate.ability.ability_id,
                candidate.ability.timing.value,
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append(candidate)
    return candidates


def trigger_debug_ability(
    session: DebugSession,
    *,
    actor_id: str,
    ability_id: str,
    timing: AbilityTiming | str | None = None,
    ability_type: AbilityType | str | None = None,
    target_choices: list[str] | None = None,
    ignore_timing: bool = False,
) -> DebugAbilityResult:
    """手动触发能力；效果仍由 AbilityResolver + AtomicResolver 结算。"""
    candidates = list_debug_abilities(
        session,
        actor_id=actor_id,
        timing=None if ignore_timing else timing,
        ability_type=ability_type,
        alive_only=False,
    )
    candidate = next(
        (item for item in candidates if item.ability.ability_id == ability_id),
        None,
    )
    if candidate is None:
        raise ValueError(f"debug ability not available: actor={actor_id!r}, ability={ability_id!r}")

    owner_id = _candidate_owner_id(candidate)
    effects = _concretize_debug_effects(
        session,
        candidate,
        owner_id=owner_id,
        target_choices=target_choices or [],
    )

    session.event_bus.emit(GameEvent(
        GameEventType.ABILITY_DECLARED,
        {
            "source_kind": candidate.source_kind,
            "source_id": candidate.source_id,
            "ability_id": candidate.ability.ability_id,
            "timing": candidate.ability.timing.value,
            "debug": True,
        },
    ))
    resolution = session.atomic_resolver.resolve(
        session.state,
        effects,
        sequential=candidate.ability.sequential,
        perpetrator_id=owner_id,
    )
    session.ability_resolver.mark_ability_used(session.state, candidate)
    forced_loop_end = _is_force_loop_end(resolution)
    session.debug_log.append({
        "action": "trigger_debug_ability",
        "actor_id": actor_id,
        "ability_id": ability_id,
        "targets": target_choices or [],
        "mutations": [_mutation_to_dict(item) for item in resolution.mutations],
        "outcome": resolution.outcome.value,
        "forced_loop_end": forced_loop_end,
    })
    return DebugAbilityResult(
        candidate=candidate,
        resolution=resolution,
        forced_loop_end=forced_loop_end,
    )


def trigger_debug_incident(
    session: DebugSession,
    *,
    incident_id: str,
    perpetrator_id: str,
    day: int | None = None,
    target_character_ids: list[str] | None = None,
    target_area_ids: list[str] | None = None,
    chosen_token_types: list[str] | None = None,
) -> DebugIncidentResult:
    """手动触发事件；仍走 IncidentResolver。"""
    schedule = IncidentSchedule(
        incident_id=incident_id,
        day=day if day is not None else session.state.current_day,
        perpetrator_id=perpetrator_id,
        target_character_ids=list(target_character_ids or []),
        target_area_ids=list(target_area_ids or []),
        chosen_token_types=list(chosen_token_types or []),
    )
    resolution = session.incident_resolver.resolve_schedule(session.state, schedule)
    forced_loop_end = resolution.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE)
    session.debug_log.append({
        "action": "trigger_debug_incident",
        "incident_id": incident_id,
        "perpetrator_id": perpetrator_id,
        "targets": target_character_ids or [],
        "areas": target_area_ids or [],
        "tokens": chosen_token_types or [],
        "occurred": resolution.occurred,
        "has_phenomenon": resolution.has_phenomenon,
        "outcome": resolution.outcome.value,
        "forced_loop_end": forced_loop_end,
    })
    return DebugIncidentResult(resolution=resolution, forced_loop_end=forced_loop_end)


def get_debug_snapshot(session: DebugSession) -> dict[str, Any]:
    """返回 UI/测试可消费的调试快照。"""
    state = session.state
    return {
        "current_loop": state.current_loop,
        "current_day": state.current_day,
        "current_phase": state.current_phase.value,
        "failure_flags": sorted(state.failure_flags),
        "protagonist_dead": state.protagonist_dead,
        "characters": {
            character_id: {
                "name": character.name,
                "area": character.area.value,
                "identity_id": character.identity_id,
                "original_identity_id": character.original_identity_id,
                "revealed": character.revealed,
                "is_alive": character.is_alive,
                "is_removed": character.is_removed,
                "tokens": _tokens_to_dict(character.tokens),
            }
            for character_id, character in state.characters.items()
        },
        "board_tokens": {
            area_id.value: _tokens_to_dict(area.tokens)
            for area_id, area in state.board.areas.items()
        },
        "incident_results": [
            {
                "incident_id": item.incident_id,
                "day": item.day,
                "occurred": item.occurred,
                "has_phenomenon": item.has_phenomenon,
                "result_tags": list(item.result_tags),
            }
            for item in state.incident_results_this_loop
        ],
        "event_log": [
            {
                "event_type": event.event_type.name,
                "data": dict(event.data),
            }
            for event in session.event_bus.log
        ],
        "debug_log": list(session.debug_log),
    }


def _apply_character_setup(character: CharacterState, setup: DebugCharacterSetup) -> None:
    if setup.area is not None:
        character.area = AreaId(setup.area)
    if setup.is_alive is not None:
        character.is_alive = setup.is_alive
    if setup.is_removed is not None:
        character.is_removed = setup.is_removed
    if setup.revealed is not None:
        character.revealed = setup.revealed
    if setup.identity_id is not None:
        character.identity_id = setup.identity_id
        if setup.current_as_original:
            character.original_identity_id = setup.identity_id
    for token_name, value in setup.tokens.items():
        character.tokens.set(TokenType(token_name), value)


def _concretize_debug_effects(
    session: DebugSession,
    candidate: AbilityCandidate,
    *,
    owner_id: str,
    target_choices: list[str],
) -> list[Effect]:
    choices = list(target_choices)
    effects: list[Effect] = []
    for effect in candidate.ability.effects:
        options = _resolve_debug_effect_options(session, owner_id=owner_id, effect=effect)
        if options is None:
            effects.append(effect)
            continue
        if not options:
            continue
        selected = choices.pop(0) if choices else options[0]
        if selected not in options:
            raise ValueError(f"invalid debug target {selected!r}; valid options: {options!r}")
        effects.append(_concretize_effect(effect, selected))
    return effects


def _resolve_debug_effect_options(
    session: DebugSession,
    *,
    owner_id: str,
    effect: Effect,
) -> list[str] | None:
    if effect.target in {"same_area_any", "any_character", "any_board", "same_area_board"} or effect.target.startswith("same_area_identity:"):
        return session.ability_resolver.resolve_targets(
            session.state,
            owner_id=owner_id,
            selector=effect.target,
            alive_only=True,
        )
    return None


def _concretize_effect(effect: Effect, target_id: str) -> Effect:
    return Effect(
        effect_type=effect.effect_type,
        target=target_id,
        token_type=effect.token_type,
        amount=effect.amount,
        chooser=effect.chooser,
        value=effect.value,
        condition=effect.condition,
    )


def _candidate_owner_id(candidate: AbilityCandidate) -> str:
    if candidate.source_kind in {"identity", "goodwill", "derived"}:
        return candidate.source_id
    return ""


def _is_force_loop_end(resolution: ResolutionResult) -> bool:
    return (
        resolution.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE)
        or any(item.mutation_type == "force_loop_end" for item in resolution.mutations)
    )


def _tokens_to_dict(tokens: Any) -> dict[str, int]:
    return {
        token_type.value: tokens.get(token_type)
        for token_type in TokenType
        if tokens.get(token_type) > 0
    }


def _mutation_to_dict(mutation: Any) -> dict[str, Any]:
    return {
        "mutation_type": mutation.mutation_type,
        "target_id": mutation.target_id,
        "details": dict(mutation.details),
    }


def _coerce_phase(value: str | GamePhase) -> GamePhase:
    return value if isinstance(value, GamePhase) else GamePhase(value)


def _coerce_timing(value: str | AbilityTiming) -> AbilityTiming:
    return value if isinstance(value, AbilityTiming) else AbilityTiming(value)


def _coerce_ability_type(value: str | AbilityType) -> AbilityType:
    return value if isinstance(value, AbilityType) else AbilityType(value)
