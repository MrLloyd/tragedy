"""惨剧轮回 — 能力收集与条件求值框架

本模块负责：
- 按时机收集角色/规则能力
- 计算角色当前生效特性
- 对声明式 Condition 做基础求值
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Optional

from engine.game_state import GameState
from engine.models.ability import Ability
from engine.models.effects import Condition
from engine.models.enums import AbilityTiming, AbilityType, AreaId, Attribute, TokenType, Trait
from engine.models.identity import IdentityDef
from engine.rules.runtime_identities import sync_dynamic_identities


@dataclass(frozen=True)
class AbilityCandidate:
    """一次可结算能力的候选项。"""

    source_kind: str  # "goodwill" | "identity" | "rule" | "derived"
    source_id: str
    ability: Ability
    identity_id: Optional[str] = None


class AbilityResolver:
    """
    能力层基础框架。

    说明：
    - 本类不直接执行 Effect，仅提供候选能力与条件判断。
    - 具体声明顺序、WaitForInput、拒绝公告由 PhaseHandler 层控制。
    """

    def collect_goodwill_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming = AbilityTiming.PROTAGONIST_ABILITY,
        ability_type: AbilityType | None = None,
        alive_only: bool = True,
    ) -> list[AbilityCandidate]:
        if timing != AbilityTiming.PROTAGONIST_ABILITY:
            return []
        if ability_type is not None and ability_type != AbilityType.OPTIONAL:
            return []

        result: list[AbilityCandidate] = []
        for ch in state.characters.values():
            if alive_only and (not ch.is_alive or ch.is_removed):
                continue

            texts = ch.goodwill_ability_texts
            costs = ch.goodwill_ability_goodwill_costs
            once_limits = ch.goodwill_ability_once_per_loop

            for slot in range(min(len(texts), len(costs))):
                text = texts[slot].strip()
                if not text:
                    continue

                cost = costs[slot]
                if ch.tokens.goodwill < cost:
                    continue

                once_per_loop = once_limits[slot] if slot < len(once_limits) else False
                ability_id = f"goodwill:{ch.character_id}:{slot + 1}"
                candidate = AbilityCandidate(
                    source_kind="goodwill",
                    source_id=ch.character_id,
                    ability=Ability(
                        ability_id=ability_id,
                        name=f"{ch.name} 友好能力{slot + 1}",
                        ability_type=AbilityType.OPTIONAL,
                        timing=AbilityTiming.PROTAGONIST_ABILITY,
                        description=text,
                        goodwill_cost=cost,
                        once_per_loop=once_per_loop,
                        can_be_refused=True,
                    ),
                )
                if not self.is_ability_available(state, candidate):
                    continue
                result.append(candidate)
        return result

    def collect_identity_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None = None,
        alive_only: bool = True,
    ) -> list[AbilityCandidate]:
        sync_dynamic_identities(state)
        result: list[AbilityCandidate] = []
        for ch in state.characters.values():
            if alive_only and (not ch.is_alive or ch.is_removed):
                continue

            identity_def = state.identity_defs.get(ch.identity_id)
            if identity_def is None:
                continue

            for ability in identity_def.abilities:
                if ability.timing != timing:
                    continue
                if ability_type is not None and ability.ability_type != ability_type:
                    continue
                if not self.evaluate_condition(state, ability.condition, owner_id=ch.character_id):
                    continue
                candidate = AbilityCandidate(
                    source_kind="identity",
                    source_id=ch.character_id,
                    ability=ability,
                    identity_id=identity_def.identity_id,
                )
                if not self.is_ability_available(state, candidate):
                    continue
                result.append(candidate)
        return result

    def collect_character_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None = None,
        alive_only: bool = True,
    ) -> list[AbilityCandidate]:
        """兼容旧接口：语义已收束为身份能力收集。"""
        return self.collect_identity_abilities(
            state,
            timing=timing,
            ability_type=ability_type,
            alive_only=alive_only,
        )

    def collect_rule_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None = None,
    ) -> list[AbilityCandidate]:
        result: list[AbilityCandidate] = []

        if state.script.rule_y is not None:
            result.extend(
                self._collect_from_rule(
                    state,
                    timing=timing,
                    ability_type=ability_type,
                    rule_id=state.script.rule_y.rule_id,
                    abilities=state.script.rule_y.abilities,
                )
            )

        for rule in state.script.rules_x:
            result.extend(
                self._collect_from_rule(
                    state,
                    timing=timing,
                    ability_type=ability_type,
                    rule_id=rule.rule_id,
                    abilities=rule.abilities,
                )
            )

        return result

    def collect_derived_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None = None,
        alive_only: bool = True,
    ) -> list[AbilityCandidate]:
        """常驻派生能力入口（P4-3）。"""
        sync_dynamic_identities(state)
        result: list[AbilityCandidate] = []
        for ch in state.characters.values():
            if alive_only and (not ch.is_alive or ch.is_removed):
                continue

            if ch.identity_id != "unstable_factor":
                continue

            if self.evaluate_condition(
                state,
                Condition(
                    condition_type="token_check",
                    params={
                        "target": AreaId.SCHOOL.value,
                        "token": TokenType.INTRIGUE.value,
                        "operator": ">=",
                        "value": 2,
                    },
                ),
                owner_id=ch.character_id,
            ):
                result.extend(
                    self._collect_identity_as_derived(
                        state,
                        owner_id=ch.character_id,
                        derived_identity_id="rumormonger",
                        timing=timing,
                        ability_type=ability_type,
                    )
                )

            if self.evaluate_condition(
                state,
                Condition(
                    condition_type="token_check",
                    params={
                        "target": AreaId.CITY.value,
                        "token": TokenType.INTRIGUE.value,
                        "operator": ">=",
                        "value": 2,
                    },
                ),
                owner_id=ch.character_id,
            ):
                result.extend(
                    self._collect_identity_as_derived(
                        state,
                        owner_id=ch.character_id,
                        derived_identity_id="key_person",
                        timing=timing,
                        ability_type=ability_type,
                    )
                )

        return result

    def collect_abilities(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None = None,
        alive_only: bool = True,
    ) -> list[AbilityCandidate]:
        """统一入口：角色友好 / 身份 / 规则 / 常驻派生。"""
        goodwill_candidates = self.collect_goodwill_abilities(
            state,
            timing=timing,
            ability_type=ability_type,
            alive_only=alive_only,
        )
        identity_candidates = self.collect_identity_abilities(
            state,
            timing=timing,
            ability_type=ability_type,
            alive_only=alive_only,
        )
        rule_candidates = self.collect_rule_abilities(
            state,
            timing=timing,
            ability_type=ability_type,
        )
        derived_candidates = self.collect_derived_abilities(
            state,
            timing=timing,
            ability_type=ability_type,
            alive_only=alive_only,
        )
        return [*goodwill_candidates, *identity_candidates, *rule_candidates, *derived_candidates]

    def ability_usage_key(self, candidate: AbilityCandidate) -> str:
        return f"{candidate.source_kind}:{candidate.source_id}:{candidate.ability.ability_id}"

    def is_ability_available(self, state: GameState, candidate: AbilityCandidate) -> bool:
        key = self.ability_usage_key(candidate)
        if candidate.ability.once_per_loop:
            if state.ability_runtime.usages_this_loop.get(key, 0) > 0:
                return False
        if candidate.ability.once_per_day:
            if state.ability_runtime.usages_this_day.get(key, 0) > 0:
                return False
        return True

    def mark_ability_used(self, state: GameState, candidate: AbilityCandidate) -> None:
        """能力结算成功后调用，统一记录 once-per-loop/day 次数。"""
        key = self.ability_usage_key(candidate)
        state.ability_runtime.usages_this_loop[key] = state.ability_runtime.usages_this_loop.get(key, 0) + 1
        state.ability_runtime.usages_this_day[key] = state.ability_runtime.usages_this_day.get(key, 0) + 1

    def resolve_targets(
        self,
        state: GameState,
        *,
        owner_id: str,
        selector: str,
        condition_target: str | None = None,
        alive_only: bool = True,
    ) -> list[str]:
        """目标解析入口（P4-2 基础版）。"""
        owner = state.characters.get(owner_id)
        if selector == "self":
            return [owner_id] if owner is not None else []
        if owner is None and selector.startswith("same_area_"):
            return []
        if selector == "same_area_any":
            return [
                ch.character_id
                for ch in state.characters_in_area(owner.area, alive_only=alive_only)  # type: ignore[union-attr]
            ]
        if selector.startswith("same_area_identity:"):
            identity_id = selector.split(":", 1)[1]
            return [
                ch.character_id
                for ch in state.characters_in_area(owner.area, alive_only=alive_only)  # type: ignore[union-attr]
                if ch.identity_id == identity_id
            ]
        if selector == "any_character":
            if alive_only:
                return [ch.character_id for ch in state.alive_characters()]
            return [ch.character_id for ch in state.characters.values() if not ch.is_removed]
        if selector == "any_board":
            return [aid.value for aid in state.board.areas]
        if selector == "condition_target":
            return [condition_target] if condition_target else []
        if selector == "hospital_all":
            return [
                ch.character_id
                for ch in state.characters_in_area(AreaId.HOSPITAL, alive_only=alive_only)
            ]
        return [selector]

    def active_traits(self, state: GameState, character_id: str) -> set[Trait]:
        """角色当前生效特性：基础特性 + 当前身份特性 + 常驻派生特性。"""
        sync_dynamic_identities(state)
        ch = state.characters.get(character_id)
        if ch is None:
            return set()
        traits = set(ch.base_traits)
        identity_def: IdentityDef | None = state.identity_defs.get(ch.identity_id)
        if identity_def is not None:
            traits.update(identity_def.traits)
        return traits

    def goodwill_should_be_ignored(self, state: GameState, character_id: str) -> bool:
        """用于主人公能力阶段：判断是否应视为无视友好。"""
        traits = self.active_traits(state, character_id)
        return (
            Trait.MUST_IGNORE_GOODWILL in traits
            or Trait.IGNORE_GOODWILL in traits
        )

    def evaluate_condition(
        self,
        state: GameState,
        condition: Condition | None,
        *,
        owner_id: str = "",
        other_id: str = "",
    ) -> bool:
        """基础 Condition 求值；未知 condition_type 视为 False。"""
        if condition is None:
            return True

        cond_type = condition.condition_type
        params = condition.params

        if cond_type in {"all_of", "any_of"}:
            raw_items = params.get("conditions", [])
            if not isinstance(raw_items, list):
                return False
            evaluated = [
                self.evaluate_condition(
                    state,
                    self._coerce_condition(item),
                    owner_id=owner_id,
                    other_id=other_id,
                )
                for item in raw_items
            ]
            return all(evaluated) if cond_type == "all_of" else any(evaluated)

        if cond_type == "is_final_day":
            return state.is_final_day

        if cond_type == "character_alive":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            target = state.characters.get(target_id)
            return bool(target is not None and target.is_alive and not target.is_removed)

        if cond_type == "character_dead":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            target = state.characters.get(target_id)
            return bool(target is not None and (not target.is_alive or target.is_removed))

        if cond_type == "identity_is":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            expected = str(params.get("value", ""))
            target = state.characters.get(target_id)
            return bool(target is not None and target.identity_id == expected)

        if cond_type == "other_identity_is":
            expected = str(params.get("value", ""))
            target = state.characters.get(other_id)
            return bool(target is not None and target.identity_id == expected)

        if cond_type == "identity_revealed":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            target = state.characters.get(target_id)
            return bool(target is not None and target.revealed)

        if cond_type == "has_trait":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            trait_name = params.get("trait")
            if not isinstance(trait_name, str):
                return False
            try:
                trait = Trait(trait_name)
            except ValueError:
                return False
            return trait in self.active_traits(state, target_id)

        if cond_type == "has_attribute":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            attr_name = params.get("attribute")
            if not isinstance(attr_name, str):
                return False
            target = state.characters.get(target_id)
            if target is None:
                return False
            try:
                attribute = Attribute(attr_name)
            except ValueError:
                return False
            return attribute in target.attributes

        if cond_type == "area_is":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            expected_area = str(params.get("value", ""))
            target = state.characters.get(target_id)
            return bool(target is not None and target.area.value == expected_area)

        if cond_type == "token_check":
            return self._evaluate_token_check(state, params, owner_id=owner_id)

        if cond_type == "identity_token_check":
            return self._evaluate_identity_token_check(state, params)

        if cond_type == "same_area_identity_token_check":
            return self._evaluate_same_area_identity_token_check(state, params, owner_id=owner_id)

        if cond_type == "same_area_count":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            target = state.characters.get(target_id)
            if target is None:
                return False
            operator = str(params.get("operator", "=="))
            value = int(params.get("value", 0))
            count = len(state.characters_in_area(target.area, alive_only=True))
            return _compare_number(count, operator, value)

        if cond_type == "loop_number_check":
            operator = str(params.get("operator", "=="))
            value = int(params.get("value", 0))
            return _compare_number(state.current_loop, operator, value)

        if cond_type == "ex_gauge_check":
            operator = str(params.get("operator", "=="))
            value = int(params.get("value", 0))
            return _compare_number(state.ex_gauge, operator, value)

        if cond_type == "paranoia_limit_check":
            target_id = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id, other_id=other_id)
            target = state.characters.get(target_id)
            if target is None:
                return False
            operator = str(params.get("operator", "=="))
            value = int(params.get("value", 0))
            return _compare_number(target.paranoia_limit, operator, value)

        if cond_type == "incident_occurred":
            incident_id = str(params.get("incident_id", ""))
            return incident_id in state.incidents_occurred_this_loop

        return False

    def _collect_identity_as_derived(
        self,
        state: GameState,
        *,
        owner_id: str,
        derived_identity_id: str,
        timing: AbilityTiming,
        ability_type: AbilityType | None,
    ) -> list[AbilityCandidate]:
        identity_def = state.identity_defs.get(derived_identity_id)
        if identity_def is None:
            return []

        result: list[AbilityCandidate] = []
        for ability in identity_def.abilities:
            if ability.timing != timing:
                continue
            if ability_type is not None and ability.ability_type != ability_type:
                continue
            if not self.evaluate_condition(state, ability.condition, owner_id=owner_id):
                continue
            candidate = AbilityCandidate(
                source_kind="derived",
                source_id=owner_id,
                ability=ability,
                identity_id=derived_identity_id,
            )
            if not self.is_ability_available(state, candidate):
                continue
            result.append(candidate)
        return result

    def _collect_from_rule(
        self,
        state: GameState,
        *,
        timing: AbilityTiming,
        ability_type: AbilityType | None,
        rule_id: str,
        abilities: list[Ability],
    ) -> list[AbilityCandidate]:
        result: list[AbilityCandidate] = []
        for ability in abilities:
            if ability.timing != timing:
                continue
            if ability_type is not None and ability.ability_type != ability_type:
                continue
            if not self.evaluate_condition(state, ability.condition):
                continue
            candidate = AbilityCandidate(
                source_kind="rule",
                source_id=rule_id,
                ability=ability,
            )
            if not self.is_ability_available(state, candidate):
                continue
            result.append(candidate)
        return result

    def _evaluate_token_check(
        self,
        state: GameState,
        params: dict[str, object],
        *,
        owner_id: str,
    ) -> bool:
        target = self._resolve_target_ref(params.get("target", owner_id), owner_id=owner_id)
        token_name = params.get("token")
        if not isinstance(token_name, str):
            return False
        try:
            token_type = TokenType(token_name)
        except ValueError:
            return False

        operator = str(params.get("operator", "=="))
        value = int(params.get("value", 0))

        amount = 0
        if target in state.characters:
            amount = state.characters[target].tokens.get(token_type)
        else:
            try:
                area_id = AreaId(target)
            except ValueError:
                return False
            board_area = state.board.areas.get(area_id)
            if board_area is None:
                return False
            amount = board_area.tokens.get(token_type)

        return _compare_number(amount, operator, value)

    def _evaluate_identity_token_check(
        self,
        state: GameState,
        params: dict[str, object],
    ) -> bool:
        identity_id = str(params.get("identity_id", ""))
        token_name = params.get("token")
        if not isinstance(token_name, str):
            return False
        try:
            token_type = TokenType(token_name)
        except ValueError:
            return False
        operator = str(params.get("operator", "=="))
        value = int(params.get("value", 0))

        for ch in state.characters.values():
            if ch.is_removed:
                continue
            if ch.identity_id != identity_id:
                continue
            if _compare_number(ch.tokens.get(token_type), operator, value):
                return True
        return False

    def _evaluate_same_area_identity_token_check(
        self,
        state: GameState,
        params: dict[str, object],
        *,
        owner_id: str,
    ) -> bool:
        owner = state.characters.get(owner_id)
        if owner is None:
            return False
        identity_id = str(params.get("identity_id", ""))
        token_name = params.get("token")
        if not isinstance(token_name, str):
            return False
        try:
            token_type = TokenType(token_name)
        except ValueError:
            return False
        operator = str(params.get("operator", "=="))
        value = int(params.get("value", 0))

        for ch in state.characters_in_area(owner.area, alive_only=True):
            if ch.identity_id != identity_id:
                continue
            if _compare_number(ch.tokens.get(token_type), operator, value):
                return True
        return False

    @staticmethod
    def _coerce_condition(raw: Any) -> Condition | None:
        if isinstance(raw, Condition):
            return raw
        if isinstance(raw, dict):
            condition_type = raw.get("condition_type")
            if isinstance(condition_type, str):
                params = raw.get("params", {})
                if isinstance(params, dict):
                    return Condition(condition_type=condition_type, params=params)
        return None

    @staticmethod
    def _resolve_target_ref(raw_target: object, *, owner_id: str, other_id: str = "") -> str:
        target = str(raw_target)
        if target == "self":
            return owner_id
        if target == "other":
            return other_id
        return target


def _compare_number(left: int, operator: str, right: int) -> bool:
    if operator == ">=":
        return left >= right
    if operator == ">":
        return left > right
    if operator == "<=":
        return left <= right
    if operator == "<":
        return left < right
    if operator == "!=":
        return left != right
    return left == right
