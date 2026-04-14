"""惨剧轮回 — 原子结算引擎

实现规则文档定义的"读-写-触发"三步法。

6 种原子结算类型：
  ① 同阶段全部强制能力
  ② 一张行动牌效果
  ③ 一次剧作家任意能力
  ④ 一次主人公友好能力
  ⑤ 一个事件的完整效果
  ⑥ 回合结束强制能力（杀人狂等）
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from engine.models.enums import AbilityTiming, AreaId, DeathResult, EffectType, Outcome, TokenType, Trait
from engine.event_bus import EventBus, GameEvent, GameEventType

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.models.identity import Effect
    from engine.resolvers.death_resolver import DeathResolver


# ---------------------------------------------------------------------------
# Mutation — 单个状态变更记录
# ---------------------------------------------------------------------------
@dataclass
class Mutation:
    mutation_type: str           # "token_change" | "character_death" | "character_move" | ...
    target_id: str               # character_id 或 area_id
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Trigger — 触发效果（死亡触发等）
# ---------------------------------------------------------------------------
@dataclass
class Trigger:
    trigger_type: str            # "on_death" | "protagonist_death" | "protagonist_failure" | ...
    source_id: str = ""          # 触发来源角色
    is_terminal: bool = False    # 是否为终局效果
    effects: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# ResolutionResult — 原子结算结果
# ---------------------------------------------------------------------------
@dataclass
class ResolutionResult:
    mutations: list[Mutation] = field(default_factory=list)
    outcome: Outcome = Outcome.NONE
    announcements: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AtomicResolver — 原子结算器
# ---------------------------------------------------------------------------
class AtomicResolver:
    """
    三步法：
      1. 读（plan）：在快照上确定所有效果的目标和数值
      2. 写（apply）：批量应用到真实状态
      3. 触发（trigger）：处理死亡等链式效果，队列式非递归
    """

    def __init__(self, event_bus: EventBus, death_resolver: DeathResolver) -> None:
        self.event_bus = event_bus
        self.death_resolver = death_resolver

    def resolve(self, state: GameState, effects: list[Effect],
                sequential: bool = False,
                perpetrator_id: str = "") -> ResolutionResult:
        """
        执行一次原子结算。

        Args:
            state: 真实游戏状态（会被修改）
            effects: 待执行的效果列表
            sequential: True=有"随后"，逐个结算；False=同时生效
            perpetrator_id: 事件当事人 ID，用于解析 same_area_* 等符号目标
        """
        if sequential:
            return self._resolve_sequential(state, effects, perpetrator_id)
        return self._resolve_simultaneous(state, effects, perpetrator_id)

    # ==================================================================
    # 同时生效结算
    # ==================================================================

    def _resolve_simultaneous(self, state: GameState,
                              effects: list[Effect],
                              perpetrator_id: str = "") -> ResolutionResult:
        # ① 读：在快照上规划
        snapshot = state.snapshot()
        planned_mutations = []
        for effect in effects:
            mutations = self._plan_effect(snapshot, effect, perpetrator_id)
            planned_mutations.extend(mutations)

        # ② 写：批量应用到真实状态
        for mutation in planned_mutations:
            self._apply_mutation(state, mutation)

        # ③ 触发：收集并处理链式效果
        return self._process_triggers(state, planned_mutations)

    # ==================================================================
    # 顺序结算（含"随后"）
    # ==================================================================

    def _resolve_sequential(self, state: GameState,
                            effects: list[Effect],
                            perpetrator_id: str = "") -> ResolutionResult:
        all_mutations: list[Mutation] = []
        final_outcome = Outcome.NONE

        for effect in effects:
            # 每步独立走完三步法
            sub_result = self._resolve_simultaneous(state, [effect], perpetrator_id)
            all_mutations.extend(sub_result.mutations)

            # 如果产生终局效果，记录但继续（后续步骤基于新状态）
            if sub_result.outcome != Outcome.NONE:
                final_outcome = sub_result.outcome

        return ResolutionResult(
            mutations=all_mutations,
            outcome=final_outcome,
        )

    # ==================================================================
    # 第一步：读 — 在快照上规划变更
    # ==================================================================

    def _resolve_target_ids(self, snapshot: GameState, target: str,
                            perpetrator_id: str) -> list[str]:
        """
        将符号目标解析为具体的角色 ID 或区域 ID 列表。

        支持的符号目标：
          same_area_all   — 当事人所在区域的全部存活角色（含当事人）
          same_area_other — 同区域除当事人外的存活角色
          same_area_board — 当事人所在区域的版图 area_id（返回区域 ID 字符串）
          其他            — 原样返回（具体角色 ID / 区域 ID）
        """
        if target == "self":
            return [perpetrator_id] if perpetrator_id and perpetrator_id in snapshot.characters else []

        if target in ("same_area_all", "same_area_other", "same_area_board"):
            if not perpetrator_id or perpetrator_id not in snapshot.characters:
                return []
            perp_area = snapshot.characters[perpetrator_id].area
            if target == "same_area_board":
                return [perp_area.value]
            alive_in_area = [
                cid for cid, ch in snapshot.characters.items()
                if ch.area == perp_area and ch.is_alive
            ]
            if target == "same_area_other":
                alive_in_area = [cid for cid in alive_in_area if cid != perpetrator_id]
            return alive_in_area
        return [target]

    def _plan_effect(self, snapshot: GameState, effect: Effect,
                     perpetrator_id: str = "") -> list[Mutation]:
        """根据效果类型规划 mutations（不修改状态）"""
        mutations = []

        match effect.effect_type:

            case EffectType.PLACE_TOKEN:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    mutations.append(Mutation(
                        mutation_type="token_change",
                        target_id=tid,
                        details={
                            "token_type": effect.token_type.value if effect.token_type else "",
                            "delta": effect.amount,
                        },
                    ))

            case EffectType.REMOVE_TOKEN:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    mutations.append(Mutation(
                        mutation_type="token_change",
                        target_id=tid,
                        details={
                            "token_type": effect.token_type.value if effect.token_type else "",
                            "delta": -effect.amount,
                        },
                    ))

            case EffectType.REMOVE_ALL_TOKENS:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    if tid in snapshot.characters:
                        ch = snapshot.characters[tid]
                        if effect.token_type:
                            current = ch.tokens.get(effect.token_type)
                            if current > 0:
                                mutations.append(Mutation(
                                    mutation_type="token_change",
                                    target_id=tid,
                                    details={
                                        "token_type": effect.token_type.value,
                                        "delta": -current,
                                    },
                                ))

            case EffectType.KILL_CHARACTER:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    mutations.append(Mutation(
                        mutation_type="character_death",
                        target_id=tid,
                        details={"cause": "effect"},
                    ))

            case EffectType.MOVE_CHARACTER:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    mutations.append(Mutation(
                        mutation_type="character_move",
                        target_id=tid,
                        details={"destination": effect.value},
                    ))

            case EffectType.PROTAGONIST_DEATH:
                mutations.append(Mutation(
                    mutation_type="protagonist_death",
                    target_id="",
                    details={"cause": effect.value or "effect"},
                ))

            case EffectType.PROTAGONIST_FAILURE:
                mutations.append(Mutation(
                    mutation_type="protagonist_failure",
                    target_id="",
                    details={"cause": effect.value or "effect"},
                ))

            case EffectType.FORCE_LOOP_END:
                mutations.append(Mutation(
                    mutation_type="force_loop_end",
                    target_id="",
                    details={"cause": effect.value or "effect"},
                ))

            case EffectType.REVEAL_IDENTITY:
                for tid in self._resolve_target_ids(snapshot, effect.target, perpetrator_id):
                    mutations.append(Mutation(
                        mutation_type="reveal_identity",
                        target_id=tid,
                        details={},
                    ))

            case EffectType.MODIFY_EX_GAUGE:
                mutations.append(Mutation(
                    mutation_type="ex_gauge_change",
                    target_id="",
                    details={"delta": effect.amount},
                ))

            case EffectType.NO_EFFECT:
                pass  # 事件发生但无现象

            case _:
                pass  # 其他类型后续扩展

        return mutations

    # ==================================================================
    # 第二步：写 — 批量应用到真实状态
    # ==================================================================

    def _apply_mutation(self, state: GameState, mutation: Mutation) -> None:
        """将单个 mutation 写入真实状态"""

        match mutation.mutation_type:

            case "token_change":
                target_id = mutation.target_id
                token_type = TokenType(mutation.details["token_type"])
                delta = mutation.details["delta"]

                # 目标可能是角色或版图
                if target_id in state.characters:
                    state.characters[target_id].tokens.add(token_type, delta)
                    self.event_bus.emit(GameEvent(
                        GameEventType.TOKEN_CHANGED,
                        {"target_id": target_id, "token_type": token_type.value,
                         "delta": delta},
                    ))
                elif hasattr(AreaId, target_id.upper()):
                    area_id = AreaId(target_id)
                    if area_id in state.board.areas:
                        state.board.areas[area_id].tokens.add(token_type, delta)
                        self.event_bus.emit(GameEvent(
                            GameEventType.TOKEN_CHANGED,
                            {"target_id": target_id, "token_type": token_type.value,
                             "delta": delta},
                        ))

            case "character_death":
                cid = mutation.target_id
                if cid in state.characters:
                    ch = state.characters[cid]
                    if ch.is_alive:
                        result = self.death_resolver.process_death(ch, state)
                        mutation.details["death_result"] = result

            case "character_move":
                cid = mutation.target_id
                dest = mutation.details["destination"]
                if cid in state.characters:
                    ch = state.characters[cid]
                    ch.area = AreaId(dest) if isinstance(dest, str) else dest
                    self.event_bus.emit(GameEvent(
                        GameEventType.CHARACTER_MOVED,
                        {"character_id": cid, "destination": str(ch.area.value)},
                    ))

            case "protagonist_death":
                if not state.soldier_protection_active:
                    state.protagonist_dead = True

            case "protagonist_failure":
                state.failure_flags.add(mutation.details.get("cause", "unknown"))

            case "force_loop_end":
                pass  # 由 GameController 处理

            case "reveal_identity":
                cid = mutation.target_id
                if cid in state.characters:
                    ch = state.characters[cid]
                    ch.revealed = True
                    self.event_bus.emit(GameEvent(
                        GameEventType.IDENTITY_REVEALED,
                        {"character_id": cid, "identity_id": ch.identity_id},
                    ))

            case "ex_gauge_change":
                delta = mutation.details["delta"]
                state.ex_gauge = max(0, state.ex_gauge + delta)
                self.event_bus.emit(GameEvent(
                    GameEventType.EX_GAUGE_CHANGED,
                    {"delta": delta, "new_value": state.ex_gauge},
                ))

    # ==================================================================
    # 第三步：触发 — 处理链式效果（队列式）
    # ==================================================================

    def _process_triggers(self, state: GameState,
                          mutations: list[Mutation]) -> ResolutionResult:
        """收集死亡等触发，队列式处理，最后统一裁定终局效果"""
        trigger_queue: deque[Trigger] = deque()
        terminal_effects: list[Trigger] = []

        # 收集初始触发
        for m in mutations:
            triggers = self._collect_triggers_from_mutation(m, state)
            trigger_queue.extend(triggers)

        # 队列式处理
        while trigger_queue:
            trigger = trigger_queue.popleft()

            if trigger.is_terminal:
                terminal_effects.append(trigger)
            else:
                # 非终局触发：执行效果，可能产生新触发（以 source_id 作为 perpetrator）
                for effect in trigger.effects:
                    sub_mutations = self._plan_effect(state, effect, trigger.source_id)
                    for sm in sub_mutations:
                        self._apply_mutation(state, sm)
                        new_triggers = self._collect_triggers_from_mutation(sm, state)
                        trigger_queue.extend(new_triggers)

        # 统一裁定终局
        outcome = self._adjudicate(terminal_effects, state)

        # 裁定后发布终局事件
        if outcome == Outcome.PROTAGONIST_DEATH:
            self.event_bus.emit(GameEvent(GameEventType.PROTAGONIST_DEATH, {"cause": "adjudication"}))
        elif outcome == Outcome.PROTAGONIST_FAILURE:
            self.event_bus.emit(GameEvent(GameEventType.PROTAGONIST_FAILURE, {"cause": "adjudication"}))

        # 如果有强制结束轮回的 mutation，标记到结果
        has_force_end = any(m.mutation_type == "force_loop_end" for m in mutations)
        if has_force_end and outcome == Outcome.NONE:
            outcome = Outcome.PROTAGONIST_FAILURE

        return ResolutionResult(mutations=mutations, outcome=outcome)

    def _collect_triggers_from_mutation(self, mutation: Mutation,
                                       state: GameState) -> list[Trigger]:
        """从单个 mutation 收集触发"""
        triggers = []

        if mutation.mutation_type == "character_death":
            death_result = mutation.details.get("death_result")
            if death_result == DeathResult.DIED:
                cid = mutation.target_id
                self.event_bus.emit(GameEvent(
                    GameEventType.CHARACTER_DEATH,
                    {"character_id": cid},
                ))
                # 接入身份 ON_DEATH 能力触发入口
                ch = state.characters.get(cid)
                if ch and ch.identity_id:
                    identity_def = state.identity_defs.get(ch.identity_id)
                    if identity_def:
                        for ability in identity_def.abilities:
                            if ability.timing == AbilityTiming.ON_DEATH:
                                triggers.append(Trigger(
                                    trigger_type="on_death",
                                    source_id=cid,
                                    is_terminal=False,
                                    effects=ability.effects,
                                ))

        if mutation.mutation_type == "protagonist_death":
            if state.protagonist_dead:
                triggers.append(Trigger(
                    trigger_type="protagonist_death",
                    is_terminal=True,
                ))

        if mutation.mutation_type == "protagonist_failure":
            triggers.append(Trigger(
                trigger_type="protagonist_failure",
                is_terminal=True,
            ))

        return triggers

    # ==================================================================
    # 同时裁定
    # ==================================================================

    @staticmethod
    def _adjudicate(terminal_effects: list[Trigger],
                    state: GameState) -> Outcome:
        """
        同时裁定规则（rules.md:179）：
        - 同时产生死亡+失败 → 仅报送死亡
        - 死亡被阻止（军人）且有失败 → 报送失败
        - 死亡被阻止且无失败 → 无终局效果
        """
        has_death = any(t.trigger_type == "protagonist_death" for t in terminal_effects)
        has_failure = any(t.trigger_type == "protagonist_failure" for t in terminal_effects)

        if not has_death and not has_failure:
            return Outcome.NONE

        if has_death:
            if not state.soldier_protection_active:
                return Outcome.PROTAGONIST_DEATH
            else:
                # 死亡被军人阻止
                state.protagonist_dead = False
                if has_failure:
                    return Outcome.PROTAGONIST_FAILURE
                return Outcome.NONE

        if has_failure:
            return Outcome.PROTAGONIST_FAILURE

        return Outcome.NONE
