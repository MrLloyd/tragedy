"""惨剧轮回 — 事件结算器

事件结算器负责事件专属语义：
  1. 判定事件是否发生
  2. 标记事件发生并发布内部事件
  3. 维护公开结果语义
  4. 将已定义的事件效果交给 AtomicResolver 执行

AtomicResolver 仍只负责通用 effect/mutation/trigger 的原子结算。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from engine.event_bus import GameEvent, GameEventType
from engine.models.effects import Effect
from engine.models.enums import Outcome, TokenType
from engine.models.incident import IncidentPublicResult
from engine.resolvers.ability_resolver import AbilityResolver

if TYPE_CHECKING:
    from engine.event_bus import EventBus
    from engine.game_state import GameState
    from engine.models.incident import IncidentDef, IncidentSchedule
    from engine.resolvers.atomic_resolver import AtomicResolver, Mutation

@dataclass
class IncidentResolution:
    """单个事件的完整结算结果。"""

    schedule: IncidentSchedule
    incident_def: IncidentDef | None = None
    occurred: bool = False
    has_phenomenon: bool = False
    outcome: Outcome = Outcome.NONE
    mutations: list[Mutation] = field(default_factory=list)
    public_result: IncidentPublicResult | None = None


class IncidentResolver:
    """事件专属结算入口。"""

    def __init__(self, event_bus: EventBus, atomic_resolver: AtomicResolver) -> None:
        self.event_bus = event_bus
        self.atomic_resolver = atomic_resolver
        self.condition_resolver = AbilityResolver()

    def resolve_schedule(
        self,
        state: GameState,
        schedule: IncidentSchedule,
    ) -> IncidentResolution:
        incident_def = state.incident_defs.get(schedule.incident_id)
        resolution = IncidentResolution(schedule=schedule, incident_def=incident_def)

        if not self.can_occur(state, schedule, incident_def):
            resolution.public_result = self._build_public_result(
                state,
                schedule,
                occurred=False,
                has_phenomenon=False,
            )
            self._record_public_result(state, resolution.public_result)
            return resolution

        self._mark_occurred(state, schedule)
        self._emit_occurred(state, schedule)
        resolution.occurred = True

        if incident_def is None:
            resolution.public_result = self._build_public_result(
                state,
                schedule,
                occurred=True,
                has_phenomenon=False,
            )
            self._record_public_result(state, resolution.public_result)
            return resolution

        effects = self._materialize_effects(state, schedule, incident_def.effects)
        result = self.atomic_resolver.resolve(
            state,
            effects,
            sequential=incident_def.sequential,
            perpetrator_id=schedule.perpetrator_id,
        )

        resolution.mutations = result.mutations
        resolution.outcome = result.outcome
        resolution.has_phenomenon = len(result.mutations) > 0
        resolution.public_result = self._build_public_result(
            state,
            schedule,
            occurred=True,
            has_phenomenon=resolution.has_phenomenon,
        )
        self._record_public_result(state, resolution.public_result)
        return resolution

    def can_occur(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        incident_def: IncidentDef | None = None,
    ) -> bool:
        if schedule.occurred:
            return False

        perpetrator = state.characters.get(schedule.perpetrator_id)
        if perpetrator is None or not perpetrator.is_alive:
            return False

        if self._incident_check_value(state, schedule) < self._incident_threshold(state, schedule, incident_def):
            return False

        if incident_def is not None and incident_def.extra_condition is not None:
            return self.condition_resolver.evaluate_condition(
                state,
                incident_def.extra_condition,
                owner_id=schedule.perpetrator_id,
            )

        return True

    def _incident_check_value(self, state: GameState, schedule: IncidentSchedule) -> int:
        """事件触发判定值；默认使用当事人不安，后续可替换为密谋等机制。"""
        perpetrator = state.characters[schedule.perpetrator_id]
        return perpetrator.tokens.paranoia

    def _incident_threshold(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        incident_def: IncidentDef | None,
    ) -> int:
        """事件触发阈值；默认使用当事人不安限度，预留事件/身份修正入口。"""
        perpetrator = state.characters[schedule.perpetrator_id]
        threshold = perpetrator.paranoia_limit
        if incident_def is not None:
            threshold += incident_def.modifies_paranoia_limit
        return threshold

    def _mark_occurred(self, state: GameState, schedule: IncidentSchedule) -> None:
        schedule.occurred = True
        state.incidents_occurred_this_loop.append(schedule.incident_id)

    def _emit_occurred(self, state: GameState, schedule: IncidentSchedule) -> None:
        self.event_bus.emit(GameEvent(
            GameEventType.INCIDENT_OCCURRED,
            {
                "incident_id": schedule.incident_id,
                "perpetrator_id": schedule.perpetrator_id,
                "day": state.current_day,
            },
        ))

    def _build_public_result(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        *,
        occurred: bool,
        has_phenomenon: bool,
    ) -> IncidentPublicResult:
        return IncidentPublicResult(
            incident_id=schedule.incident_id,
            day=state.current_day,
            occurred=occurred,
            has_phenomenon=has_phenomenon,
            result_tags=["phenomenon"] if has_phenomenon else ["no_phenomenon"],
        )

    def _record_public_result(self, state: GameState, public_result: IncidentPublicResult | None) -> None:
        if public_result is not None:
            state.incident_results_this_loop.append(public_result)

    def _materialize_effects(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        effects: list[Effect],
    ) -> list[Effect]:
        character_choices: deque[str] = deque(schedule.target_character_ids)
        area_choices: deque[str] = deque(schedule.target_area_ids)
        token_choices: deque[str] = deque(schedule.chosen_token_types)
        chosen_characters: list[str] = []
        concretized: list[Effect] = []

        for effect in effects:
            updated = replace(effect)
            chosen_token_type: TokenType | None = None
            if effect.token_type is None and effect.value == "choose_token_type":
                chosen_token_type = self._resolve_token_choice(token_choices)
            updated.target = self._resolve_effect_target(
                state,
                schedule,
                effect,
                character_choices=character_choices,
                chosen_characters=chosen_characters,
            )
            updated.value = self._resolve_effect_value(
                state,
                schedule,
                effect,
                area_choices=area_choices,
                chosen_token_type=chosen_token_type,
            )
            if chosen_token_type is not None:
                updated.token_type = chosen_token_type
            if effect.target in {"any_character", "same_area_any", "another_character", "any_other_character"}:
                updated.condition = None
            concretized.append(updated)
            if updated.target in state.characters:
                chosen_characters.append(updated.target)

        return concretized

    def _resolve_effect_target(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        effect: Effect,
        *,
        character_choices: deque[str],
        chosen_characters: list[str],
    ) -> str:
        selector = effect.target
        if selector not in {"any_character", "same_area_any", "another_character", "any_other_character"}:
            return selector

        candidates = self._resolve_character_candidates(
            state,
            schedule,
            effect,
            selector=selector,
            chosen_characters=chosen_characters,
        )
        if not candidates:
            return "__no_target__"

        scripted_choice = character_choices[0] if character_choices else None
        if scripted_choice in candidates:
            character_choices.popleft()
            return scripted_choice

        return sorted(candidates)[0]

    def _resolve_effect_value(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        effect: Effect,
        *,
        area_choices: deque[str],
        chosen_token_type: TokenType | None,
    ) -> object:
        if effect.effect_type.name == "MOVE_CHARACTER" and effect.value == "any_board":
            candidates = self.condition_resolver.resolve_targets(
                state,
                owner_id=schedule.perpetrator_id,
                selector="any_board",
                alive_only=False,
            )
            scripted_choice = area_choices[0] if area_choices else None
            if scripted_choice in candidates:
                area_choices.popleft()
                return scripted_choice
            return sorted(candidates)[0] if candidates else effect.value
        if chosen_token_type is not None:
            return chosen_token_type.value
        return effect.value

    def _resolve_token_choice(self, token_choices: deque[str]) -> TokenType:
        if token_choices:
            raw = token_choices.popleft()
            try:
                return TokenType(raw)
            except ValueError:
                pass
        return TokenType.GOODWILL

    def _resolve_character_candidates(
        self,
        state: GameState,
        schedule: IncidentSchedule,
        effect: Effect,
        *,
        selector: str,
        chosen_characters: list[str],
    ) -> list[str]:
        owner_id = schedule.perpetrator_id
        if selector == "another_character":
            base_candidates = self.condition_resolver.resolve_targets(
                state,
                owner_id=owner_id,
                selector="any_character",
            )
            if chosen_characters:
                base_candidates = [cid for cid in base_candidates if cid != chosen_characters[-1]]
        elif selector == "any_other_character":
            base_candidates = [
                cid for cid in self.condition_resolver.resolve_targets(
                    state,
                    owner_id=owner_id,
                    selector="any_character",
                )
                if cid != owner_id
            ]
        else:
            base_candidates = self.condition_resolver.resolve_targets(
                state,
                owner_id=owner_id,
                selector=selector,
            )

        result: list[str] = []
        for candidate in base_candidates:
            if effect.condition is not None and not self.condition_resolver.evaluate_condition(
                state,
                effect.condition,
                owner_id=owner_id,
                other_id=candidate,
            ):
                continue
            result.append(candidate)
        return result
