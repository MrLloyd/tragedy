"""惨剧轮回 — 阶段处理器基类与返回信号"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.models.cards import CardPlacement, PlacementIntent
from engine.models.ability import Ability
from engine.models.effects import Effect
from engine.models.enums import AbilityTiming, AbilityType, CardType, EffectType, GamePhase, Outcome, PlayerRole, TokenType, Trait
from engine.resolvers.ability_resolver import AbilityCandidate, AbilityResolver
from engine.resolvers.incident_resolver import IncidentResolver

from engine.event_bus import GameEvent, GameEventType

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.event_bus import EventBus
    from engine.resolvers.atomic_resolver import AtomicResolver


# ---------------------------------------------------------------------------
# 阶段返回信号
# ---------------------------------------------------------------------------
@dataclass
class PhaseComplete:
    """阶段完成，状态机可推进"""
    pass


@dataclass
class WaitForInput:
    """
    等待玩家输入。

    引擎挂起，UI 展示选项，玩家操作后调用 callback(choice) 继续。
    """
    input_type: str              # 输入类型标识
    prompt: str = ""             # 提示文本
    options: list[Any] = field(default_factory=list)
    player: str = "mastermind"   # 谁需要输入
    callback: Optional[Callable] = None


@dataclass
class ForceLoopEnd:
    """强制结束本轮回"""
    reason: str = ""


# 阶段返回类型
PhaseSignal = PhaseComplete | WaitForInput | ForceLoopEnd


# ---------------------------------------------------------------------------
# PhaseHandler — 阶段处理器基类
# ---------------------------------------------------------------------------
class PhaseHandler(ABC):
    """
    每个游戏阶段对应一个 PhaseHandler 子类。

    execute() 返回 PhaseSignal：
      - PhaseComplete → 自动推进
      - WaitForInput  → 挂起等待
      - ForceLoopEnd  → 跳到 loop_end
    """

    phase: GamePhase  # 子类必须声明

    def __init__(self, event_bus: EventBus,
                 atomic_resolver: AtomicResolver) -> None:
        self.event_bus = event_bus
        self.atomic_resolver = atomic_resolver
        self.ability_resolver = AbilityResolver()

    @abstractmethod
    def execute(self, state: GameState) -> PhaseSignal:
        """执行本阶段逻辑"""
        ...

    def _emit_ability_declared(self, candidate: AbilityCandidate) -> None:
        payload = {
            "source_kind": candidate.source_kind,
            "source_id": candidate.source_id,
            "ability_id": candidate.ability.ability_id,
            "timing": candidate.ability.timing.value,
        }
        if candidate.identity_id is not None:
            payload["identity_id"] = candidate.identity_id
        self.event_bus.emit(GameEvent(GameEventType.ABILITY_DECLARED, payload))

    def _resolve_candidate(
        self,
        state: GameState,
        candidate: AbilityCandidate,
        *,
        next_signal_factory: Callable[[], PhaseSignal],
    ) -> PhaseSignal:
        owner_id = self._candidate_owner_id(candidate)
        prepared = self._prepare_effects_for_resolution(
            state,
            candidate,
            owner_id=owner_id,
            next_signal_factory=next_signal_factory,
        )
        if isinstance(prepared, WaitForInput):
            return prepared

        self._emit_ability_declared(candidate)
        result = self.atomic_resolver.resolve(
            state,
            prepared,
            sequential=candidate.ability.sequential,
            perpetrator_id=owner_id,
        )
        self.ability_resolver.mark_ability_used(state, candidate)
        signal = self._resolution_result_to_signal(result, default_reason=candidate.ability.ability_id)
        if signal is not None:
            return signal
        return next_signal_factory()

    def _execute_mandatory_batch(
        self,
        state: GameState,
        candidates: list[AbilityCandidate],
        *,
        next_signal_factory: Callable[[], PhaseSignal],
    ) -> PhaseSignal:
        if not candidates:
            return next_signal_factory()

        candidate = candidates[0]

        def _next() -> PhaseSignal:
            return self._execute_mandatory_batch(
                state,
                candidates[1:],
                next_signal_factory=next_signal_factory,
            )

        return self._resolve_candidate(
            state,
            candidate,
            next_signal_factory=_next,
        )

    def _candidate_owner_id(self, candidate: AbilityCandidate) -> str:
        if candidate.source_kind in {"identity", "goodwill", "derived"}:
            return candidate.source_id
        return ""

    def _prepare_effects_for_resolution(
        self,
        state: GameState,
        candidate: AbilityCandidate,
        *,
        owner_id: str,
        next_signal_factory: Callable[[], PhaseSignal],
    ) -> list[Effect] | WaitForInput:
        effects = list(candidate.ability.effects)
        for index, effect in enumerate(effects):
            choices = self._resolve_effect_choice_options(state, owner_id=owner_id, effect=effect)
            if choices is None:
                continue
            if not choices:
                return []
            if len(choices) == 1:
                effects[index] = self._concretize_effect(effect, choices[0])
                continue

            def _on_choice(choice: Any, *, effect_index: int = index) -> PhaseSignal:
                selected = str(choice)
                if selected not in choices:
                    raise ValueError(f"invalid ability target: {selected!r}")
                updated = list(effects)
                updated[effect_index] = self._concretize_effect(effect, selected)
                follow_up = AbilityCandidate(
                    source_kind=candidate.source_kind,
                    source_id=candidate.source_id,
                    ability=Ability(
                        ability_id=candidate.ability.ability_id,
                        name=candidate.ability.name,
                        ability_type=candidate.ability.ability_type,
                        timing=candidate.ability.timing,
                        description=candidate.ability.description,
                        condition=candidate.ability.condition,
                        effects=updated,
                        sequential=candidate.ability.sequential,
                        goodwill_cost=candidate.ability.goodwill_cost,
                        once_per_loop=candidate.ability.once_per_loop,
                        once_per_day=candidate.ability.once_per_day,
                        can_be_refused=candidate.ability.can_be_refused,
                    ),
                    identity_id=candidate.identity_id,
                )
                return self._resolve_candidate(
                    state,
                    follow_up,
                    next_signal_factory=next_signal_factory,
                )

            return WaitForInput(
                input_type="choose_ability_target",
                prompt=f"请选择 {candidate.ability.name} 的目标",
                options=choices,
                player="mastermind",
                callback=_on_choice,
            )
        return effects

    def _resolve_effect_choice_options(
        self,
        state: GameState,
        *,
        owner_id: str,
        effect: Effect,
    ) -> list[str] | None:
        if effect.target in {"same_area_any", "any_character", "any_board"} or effect.target.startswith("same_area_identity:"):
            return self.ability_resolver.resolve_targets(
                state,
                owner_id=owner_id,
                selector=effect.target,
                alive_only=True,
            )
        if effect.target == "same_area_board":
            return self.ability_resolver.resolve_targets(
                state,
                owner_id=owner_id,
                selector=effect.target,
                alive_only=True,
            )
        return None

    @staticmethod
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

    @staticmethod
    def _resolution_result_to_signal(result: Any, *, default_reason: str) -> ForceLoopEnd | None:
        if result.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE):
            return ForceLoopEnd(reason=default_reason)
        if any(m.mutation_type == "force_loop_end" for m in result.mutations):
            return ForceLoopEnd(reason=default_reason)
        return None


# ---------------------------------------------------------------------------
# 具体阶段处理器（框架实现，后续逐步填充业务逻辑）
# ---------------------------------------------------------------------------
class GamePrepareHandler(PhaseHandler):
    phase = GamePhase.GAME_PREPARE

    def execute(self, state: GameState) -> PhaseSignal:
        # 游戏准备：确认剧本已加载，初始化手牌等
        state.init_protagonist_hands()
        return PhaseComplete()


class LoopStartHandler(PhaseHandler):
    phase = GamePhase.LOOP_START

    def execute(self, state: GameState) -> PhaseSignal:
        self._apply_causal_line(state)
        mandatory = self.ability_resolver.collect_abilities(
            state,
            timing=AbilityTiming.LOOP_START,
            ability_type=AbilityType.MANDATORY,
            alive_only=False,
        )
        return self._execute_mandatory_batch(
            state,
            mandatory,
            next_signal_factory=PhaseComplete,
        )

    def _apply_causal_line(self, state: GameState) -> None:
        """BTX 因果线：上轮结束时有友好的角色，本轮开始 +2 不安。"""
        if not any(rule.rule_id == "btx_causal_line" for rule in state.script.rules_x):
            return

        last_snapshot = state.get_last_loop_snapshot()
        if last_snapshot is None:
            return

        effects = [
            Effect(
                effect_type=EffectType.PLACE_TOKEN,
                target=character_id,
                token_type=TokenType.PARANOIA,
                amount=2,
            )
            for character_id, character_snapshot in last_snapshot.character_snapshots.items()
            if character_snapshot.tokens.goodwill > 0 and character_id in state.characters
        ]
        if effects:
            self.atomic_resolver.resolve(state, effects)


class TurnStartHandler(PhaseHandler):
    phase = GamePhase.TURN_START

    def execute(self, state: GameState) -> PhaseSignal:
        # 回合开始：结算回合开始触发效果
        return PhaseComplete()


class MastermindActionHandler(PhaseHandler):
    phase = GamePhase.MASTERMIND_ACTION

    def execute(self, state: GameState) -> PhaseSignal:
        # 剧作家暗置恰好 3 张行动牌（可用牌不足时取全部）
        available = state.mastermind_hand.get_available()
        max_cards = min(3, len(available))

        def _on_choice(choice: Any) -> PhaseSignal:
            # 接收 list[PlacementIntent]
            intents = choice if isinstance(choice, list) else [choice]
            if not intents or len(intents) != max_cards:
                raise ValueError(f"mastermind must choose exactly {max_cards} cards")

            for intent in intents:
                if intent.card not in available:
                    raise ValueError("selected card is not available in mastermind hand")

                # 验证目标合法性
                if intent.target_type == "character":
                    ch = state.characters.get(intent.target_id)
                    if ch is None:
                        raise ValueError(f"target character {intent.target_id} not found")
                    if not ch.is_alive:
                        raise ValueError(f"target character {intent.target_id} is not alive")
                    if Trait.NO_ACTION_CARDS in ch.base_traits:
                        raise ValueError(f"target character {intent.target_id} cannot receive action cards")
                elif intent.target_type == "board":
                    # 验证 target_id 是合法 AreaId
                    try:
                        from engine.models.enums import AreaId
                        AreaId(intent.target_id)
                    except ValueError:
                        raise ValueError(f"invalid board target area: {intent.target_id}")
                else:
                    raise ValueError(f"invalid target_type: {intent.target_type}")

                # 创建放置记录（不标记 is_used_this_loop）
                state.placed_cards.append(
                    CardPlacement(
                        card=intent.card,
                        owner=PlayerRole.MASTERMIND,
                        target_type=intent.target_type,
                        target_id=intent.target_id,
                        face_down=True,
                    )
                )
            return PhaseComplete()

        return WaitForInput(
            input_type="place_action_cards",
            prompt="剧作家请放置 3 张行动牌",
            options=available,
            player="mastermind",
            callback=_on_choice,
        )


class ProtagonistActionHandler(PhaseHandler):
    phase = GamePhase.PROTAGONIST_ACTION

    def execute(self, state: GameState) -> PhaseSignal:
        # 3 名主人公按队长起顺时针依次放牌（递归 callback 链）
        order = [(state.leader_index + i) % 3 for i in range(3)]
        return self._request_placement(state, order)

    def _request_placement(self, state: GameState, remaining: list[int]) -> PhaseSignal:
        """递归请求剩余主人公放牌"""
        if not remaining:
            return PhaseComplete()

        idx = remaining[0]
        rest = remaining[1:]
        hand = state.protagonist_hands[idx]
        available = hand.get_available()

        def _on_choice(intent: Any) -> PhaseSignal:
            # 接收 PlacementIntent
            if intent.card not in available:
                raise ValueError("selected card is not available in protagonist hand")

            # 验证目标合法性
            if intent.target_type == "character":
                ch = state.characters.get(intent.target_id)
                if ch is None:
                    raise ValueError(f"target character {intent.target_id} not found")
                if not ch.is_alive:
                    raise ValueError(f"target character {intent.target_id} is not alive")
                if Trait.NO_ACTION_CARDS in ch.base_traits:
                    raise ValueError(f"target character {intent.target_id} cannot receive action cards")
            elif intent.target_type == "board":
                # 验证 target_id 是合法 AreaId
                try:
                    from engine.models.enums import AreaId
                    AreaId(intent.target_id)
                except ValueError:
                    raise ValueError(f"invalid board target area: {intent.target_id}")
            else:
                raise ValueError(f"invalid target_type: {intent.target_type}")

            # 创建放置记录（不标记 is_used_this_loop）
            state.placed_cards.append(
                CardPlacement(
                    card=intent.card,
                    owner=hand.owner,
                    target_type=intent.target_type,
                    target_id=intent.target_id,
                    face_down=True,
                )
            )

            # 链接下一名主人公
            return self._request_placement(state, rest)

        return WaitForInput(
            input_type="place_action_card",
            prompt=f"主人公 {idx + 1} 请放置 1 张行动牌",
            options=available,
            player=f"protagonist_{idx}",
            callback=_on_choice,
        )


class ActionResolveHandler(PhaseHandler):
    phase = GamePhase.ACTION_RESOLVE

    # CardType → (TokenType, delta)
    _TOKEN_EFFECTS: dict[CardType, tuple[TokenType, int]] = {
        CardType.INTRIGUE_PLUS_2:    (TokenType.INTRIGUE,  2),
        CardType.INTRIGUE_PLUS_1:    (TokenType.INTRIGUE,  1),
        CardType.PARANOIA_PLUS_1:    (TokenType.PARANOIA,  1),
        CardType.PARANOIA_PLUS_1_P:  (TokenType.PARANOIA,  1),
        CardType.PARANOIA_MINUS_1:   (TokenType.PARANOIA, -1),
        CardType.PARANOIA_MINUS_1_P: (TokenType.PARANOIA, -1),
        CardType.GOODWILL_PLUS_1:    (TokenType.GOODWILL,  1),
        CardType.GOODWILL_PLUS_1_MM: (TokenType.GOODWILL,  1),
        CardType.GOODWILL_PLUS_2:    (TokenType.GOODWILL,  2),
        CardType.DESPAIR_PLUS_1:     (TokenType.DESPAIR,   1),
        CardType.HOPE_PLUS_1:        (TokenType.HOPE,      1),
        CardType.PARANOIA_PLUS_2_P:  (TokenType.PARANOIA,  2),
    }
    # FORBID 牌 → 被禁止的 TokenType（None = 禁止移动）
    _FORBID_TOKEN: dict[CardType, Optional[TokenType]] = {
        CardType.FORBID_GOODWILL: TokenType.GOODWILL,
        CardType.FORBID_PARANOIA: TokenType.PARANOIA,
        CardType.FORBID_INTRIGUE: TokenType.INTRIGUE,
        CardType.FORBID_MOVEMENT: None,
    }

    def execute(self, state: GameState) -> PhaseSignal:
        placements = list(state.placed_cards)
        if not placements:
            return PhaseComplete()

        # 翻牌
        for p in placements:
            p.face_down = False

        # FORBID 预处理
        self._apply_forbids(placements)

        # 标记 once_per_loop 已用（无论是否被无效化）
        for p in placements:
            if p.card.once_per_loop:
                p.card.is_used_this_loop = True

        # 移动牌先结算
        for p in placements:
            if p.nullified or not p.card.is_movement:
                continue
            dest = self._movement_destination(state, p.target_id, p.card.card_type)
            if dest is None:
                continue
            effect = Effect(effect_type=EffectType.MOVE_CHARACTER, target=p.target_id, value=dest)
            result = self.atomic_resolver.resolve(state, [effect])
            if result.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE):
                return ForceLoopEnd(reason="action_resolve")

        # 指示物牌结算
        for p in placements:
            if p.nullified or p.card.is_movement or p.card.card_type in self._FORBID_TOKEN:
                continue
            token_info = self._TOKEN_EFFECTS.get(p.card.card_type)
            if token_info is None:
                continue
            token_type, delta = token_info
            effect_type = EffectType.PLACE_TOKEN if delta > 0 else EffectType.REMOVE_TOKEN
            effect = Effect(
                effect_type=effect_type,
                target=p.target_id,
                token_type=token_type,
                amount=abs(delta),
            )
            result = self.atomic_resolver.resolve(state, [effect])
            if result.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE):
                return ForceLoopEnd(reason="action_resolve")

        return PhaseComplete()

    def _apply_forbids(self, placements: list[CardPlacement]) -> None:
        """
        FORBID 预处理（规则§3.11）：
        - 偶数张同目标同类型 FORBID → 互相抵消，全部标 nullified
        - 奇数张 → 最后一张生效，将同目标对应牌标 nullified
        """
        from collections import defaultdict
        forbid_groups: dict[tuple, list[CardPlacement]] = defaultdict(list)
        for p in placements:
            if p.card.card_type in self._FORBID_TOKEN:
                forbid_groups[(p.card.card_type, p.target_id)].append(p)

        for (forbid_type, target_id), fps in forbid_groups.items():
            if len(fps) % 2 == 0:
                for fp in fps:
                    fp.nullified = True
            else:
                blocked_token = self._FORBID_TOKEN[forbid_type]
                for p in placements:
                    if p in fps or p.nullified or p.target_id != target_id:
                        continue
                    if blocked_token is None:
                        # FORBID_MOVEMENT
                        if p.card.is_movement:
                            p.nullified = True
                    else:
                        token_info = self._TOKEN_EFFECTS.get(p.card.card_type)
                        if token_info and token_info[0] == blocked_token:
                            p.nullified = True

    def _movement_destination(
        self, state: GameState, char_id: str, card_type: CardType
    ) -> Optional[str]:
        """根据角色当前区域与牌类型，计算移动目标区域 ID"""
        ch = state.characters.get(char_id)
        if ch is None or not ch.is_alive:
            return None
        board = state.board
        if card_type in (CardType.MOVE_HORIZONTAL, CardType.MOVE_HORIZONTAL_P):
            dest = board.get_horizontal_adjacent(ch.area)
        elif card_type in (CardType.MOVE_VERTICAL, CardType.MOVE_VERTICAL_P):
            dest = board.get_vertical_adjacent(ch.area)
        elif card_type == CardType.MOVE_DIAGONAL:
            dest = board.get_diagonal_adjacent(ch.area)
        else:
            return None
        return dest.value if dest else None


class PlaywrightAbilityHandler(PhaseHandler):
    phase = GamePhase.PLAYWRIGHT_ABILITY

    def execute(self, state: GameState) -> PhaseSignal:
        mandatory = self.ability_resolver.collect_abilities(
            state,
            timing=AbilityTiming.PLAYWRIGHT_ABILITY,
            ability_type=AbilityType.MANDATORY,
        )
        return self._execute_mandatory_batch(
            state,
            mandatory,
            next_signal_factory=lambda: self._request_optional_playwright_ability(state),
        )

    def _request_optional_playwright_ability(self, state: GameState) -> PhaseSignal:
        candidates = self.ability_resolver.collect_abilities(
            state,
            timing=AbilityTiming.PLAYWRIGHT_ABILITY,
            ability_type=AbilityType.OPTIONAL,
        )
        if not candidates:
            return PhaseComplete()

        options: list[Any] = ["pass", *candidates]

        def _on_choice(choice: Any) -> PhaseSignal:
            if choice == "pass":
                return PhaseComplete()
            if choice not in candidates:
                raise ValueError("invalid playwright ability selection")
            return self._resolve_candidate(
                state,
                choice,
                next_signal_factory=lambda: self._request_optional_playwright_ability(state),
            )

        return WaitForInput(
            input_type="choose_playwright_ability",
            prompt="剧作家请选择要声明的能力，或 pass",
            options=options,
            player="mastermind",
            callback=_on_choice,
        )


class ProtagonistAbilityHandler(PhaseHandler):
    phase = GamePhase.PROTAGONIST_ABILITY

    def execute(self, state: GameState) -> PhaseSignal:
        return self._request_goodwill_ability(state)

    def _request_goodwill_ability(self, state: GameState) -> PhaseSignal:
        candidates = self.ability_resolver.collect_goodwill_abilities(state)
        if not candidates:
            return PhaseComplete()

        leader = f"protagonist_{state.leader_index}"
        options: list[Any] = ["pass", *candidates]

        def _on_choice(choice: Any) -> PhaseSignal:
            if choice == "pass":
                return PhaseComplete()
            if choice not in candidates:
                raise ValueError("invalid goodwill ability selection")
            return self._handle_goodwill_declaration(state, choice)

        return WaitForInput(
            input_type="choose_goodwill_ability",
            prompt="队长请选择要声明的友好能力，或 pass",
            options=options,
            player=leader,
            callback=_on_choice,
        )

    def _handle_goodwill_declaration(
        self,
        state: GameState,
        candidate: AbilityCandidate,
    ) -> PhaseSignal:
        owner_id = candidate.source_id
        should_ignore = self.ability_resolver.goodwill_should_be_ignored(state, owner_id)
        if candidate.ability.can_be_refused and not should_ignore:
            def _on_refuse(choice: Any) -> PhaseSignal:
                if choice not in {"allow", "refuse"}:
                    raise ValueError("invalid goodwill response")
                if choice == "refuse":
                    self.event_bus.emit(GameEvent(
                        GameEventType.ABILITY_REFUSED,
                        {"character_id": owner_id, "ability_id": candidate.ability.ability_id},
                    ))
                    self.ability_resolver.mark_ability_used(state, candidate)
                    return self._request_goodwill_ability(state)
                return self._resolve_goodwill_ability(state, candidate)

            return WaitForInput(
                input_type="respond_goodwill_ability",
                prompt="剧作家是否拒绝该友好能力？",
                options=["allow", "refuse"],
                player="mastermind",
                callback=_on_refuse,
            )
        return self._resolve_goodwill_ability(state, candidate)

    def _resolve_goodwill_ability(
        self,
        state: GameState,
        candidate: AbilityCandidate,
    ) -> PhaseSignal:
        owner = state.characters.get(candidate.source_id)
        if owner is None:
            return self._request_goodwill_ability(state)
        owner.tokens.remove(TokenType.GOODWILL, candidate.ability.goodwill_cost)
        return self._resolve_candidate(
            state,
            candidate,
            next_signal_factory=lambda: self._request_goodwill_ability(state),
        )


class IncidentHandler(PhaseHandler):
    phase = GamePhase.INCIDENT

    def __init__(self, event_bus: EventBus,
                 atomic_resolver: AtomicResolver) -> None:
        super().__init__(event_bus, atomic_resolver)
        self.incident_resolver = IncidentResolver(event_bus, atomic_resolver)

    def execute(self, state: GameState) -> PhaseSignal:
        """
        事件阶段。

        阶段处理器只负责当天事件调度；事件触发判定、公开语义与
        效果结算由 IncidentResolver 统一负责。
        """
        schedules = state.get_incidents_for_day(state.current_day)

        for schedule in schedules:
            result = self.incident_resolver.resolve_schedule(state, schedule)
            if result.outcome in (Outcome.PROTAGONIST_DEATH, Outcome.PROTAGONIST_FAILURE):
                return ForceLoopEnd(reason=schedule.incident_id)

        return PhaseComplete()


class LeaderRotateHandler(PhaseHandler):
    phase = GamePhase.LEADER_ROTATE

    def execute(self, state: GameState) -> PhaseSignal:
        state.rotate_leader()
        return PhaseComplete()


class TurnEndHandler(PhaseHandler):
    phase = GamePhase.TURN_END

    def execute(self, state: GameState) -> PhaseSignal:
        timings = [AbilityTiming.TURN_END]
        if state.is_final_day:
            timings.append(AbilityTiming.FINAL_DAY_TURN_END)

        mandatory: list[AbilityCandidate] = []
        for timing in timings:
            mandatory.extend(
                self.ability_resolver.collect_abilities(
                    state,
                    timing=timing,
                    ability_type=AbilityType.MANDATORY,
                )
            )
        return self._execute_mandatory_batch(
            state,
            mandatory,
            next_signal_factory=lambda: self._request_optional_turn_end_ability(state, timings),
        )

    def _request_optional_turn_end_ability(
        self,
        state: GameState,
        timings: list[AbilityTiming],
    ) -> PhaseSignal:
        candidates: list[AbilityCandidate] = []
        for timing in timings:
            candidates.extend(
                self.ability_resolver.collect_abilities(
                    state,
                    timing=timing,
                    ability_type=AbilityType.OPTIONAL,
                )
            )
        if not candidates:
            return PhaseComplete()

        options: list[Any] = ["pass", *candidates]

        def _on_choice(choice: Any) -> PhaseSignal:
            if choice == "pass":
                return PhaseComplete()
            if choice not in candidates:
                raise ValueError("invalid turn_end ability selection")
            return self._resolve_candidate(
                state,
                choice,
                next_signal_factory=lambda: self._request_optional_turn_end_ability(state, timings),
            )

        return WaitForInput(
            input_type="choose_turn_end_ability",
            prompt="剧作家请选择回合结束阶段能力，或 pass",
            options=options,
            player="mastermind",
            callback=_on_choice,
        )


class LoopEndHandler(PhaseHandler):
    phase = GamePhase.LOOP_END

    def execute(self, state: GameState) -> PhaseSignal:
        candidates = self.ability_resolver.collect_abilities(
            state,
            timing=AbilityTiming.LOOP_END,
            ability_type=None,
            alive_only=False,
        )
        return self._execute_loop_end_candidates(state, candidates)

    def _execute_loop_end_candidates(
        self,
        state: GameState,
        candidates: list[AbilityCandidate],
    ) -> PhaseSignal:
        if not candidates:
            return self._finalize_loop_end(state)

        candidate = candidates[0]
        owner_id = self._candidate_owner_id(candidate)
        prepared = self._prepare_effects_for_resolution(
            state,
            candidate,
            owner_id=owner_id,
            next_signal_factory=lambda: self._execute_loop_end_candidates(state, candidates[1:]),
        )
        if isinstance(prepared, WaitForInput):
            return prepared

        self._emit_ability_declared(candidate)
        self.atomic_resolver.resolve(
            state,
            prepared,
            sequential=candidate.ability.sequential,
            perpetrator_id=owner_id,
        )
        self.ability_resolver.mark_ability_used(state, candidate)
        return self._execute_loop_end_candidates(state, candidates[1:])

    def _finalize_loop_end(self, state: GameState) -> PhaseSignal:
        self.event_bus.emit(GameEvent(
            GameEventType.LOOP_ENDED,
            {"loop": state.current_loop},
        ))
        state.save_loop_snapshot()
        return PhaseComplete()


class LoopEndCheckHandler(PhaseHandler):
    phase = GamePhase.LOOP_END_CHECK

    def execute(self, state: GameState) -> PhaseSignal:
        # 判定分流（由 StateMachine 处理，此处仅做失败条件收集）
        # TODO: 检查规则 Y / 规则 X 的失败条件
        return PhaseComplete()


class FinalGuessHandler(PhaseHandler):
    phase = GamePhase.FINAL_GUESS

    def execute(self, state: GameState) -> PhaseSignal:
        # 最终决战：主人公推理身份
        def _on_choice(_: Any) -> PhaseSignal:
            # Phase 1 最小闭环：接收输入即可继续推进，具体判定后续实现。
            return PhaseComplete()

        return WaitForInput(
            input_type="final_guess",
            prompt="最终决战：请推理所有角色身份与规则",
            player="protagonists",
            callback=_on_choice,
        )


# ---------------------------------------------------------------------------
# 阶段处理器注册表
# ---------------------------------------------------------------------------
def create_phase_handlers(event_bus: EventBus,
                          atomic_resolver: AtomicResolver
                          ) -> dict[GamePhase, PhaseHandler]:
    """创建所有阶段处理器的映射"""
    handlers: list[type[PhaseHandler]] = [
        GamePrepareHandler,
        LoopStartHandler,
        TurnStartHandler,
        MastermindActionHandler,
        ProtagonistActionHandler,
        ActionResolveHandler,
        PlaywrightAbilityHandler,
        ProtagonistAbilityHandler,
        IncidentHandler,
        LeaderRotateHandler,
        TurnEndHandler,
        LoopEndHandler,
        LoopEndCheckHandler,
        FinalGuessHandler,
    ]
    return {
        cls.phase: cls(event_bus, atomic_resolver)
        for cls in handlers
    }
