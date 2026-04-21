"""惨剧轮回 — 模组加载器

将 data/modules/{module_id}.json 反序列化为运行时对象，
填充 GameState.identity_defs / incident_defs，并返回 ModuleDef。
"""

from __future__ import annotations

import json
import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.models.ability import Ability
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.effects import Condition, Effect
from engine.models.enums import AbilityTiming, AbilityType, EffectType, TokenType, Trait
from engine.models.identity import IdentityDef
from engine.models.incident import IncidentDef, IncidentSchedule
from engine.models.script import CharacterSetup, ModuleDef, RuleDef
from engine.rules.character_loader import (
    CharacterDef,
    instantiate_character_state,
    load_character_defs,
    normalize_identity_id,
)
from engine.rules.script_validator import (
    ScriptValidationContext,
    ScriptValidationError,
    validate_script,
)

# data/modules/ 目录（相对于本文件向上三级）
_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "modules"


# ---------------------------------------------------------------------------
# 加载结果容器
# ---------------------------------------------------------------------------
@dataclass
class LoadedModule:
    module_def: ModuleDef
    identity_defs: dict[str, IdentityDef] = field(default_factory=dict)
    incident_defs: dict[str, IncidentDef] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 公开入口
# ---------------------------------------------------------------------------
def load_module(module_id: str) -> LoadedModule:
    """
    加载指定模组。

    Args:
        module_id: 如 "first_steps", "basic_tragedy_x"

    Returns:
        LoadedModule，包含 ModuleDef、identity_defs、incident_defs

    Raises:
        FileNotFoundError: JSON 文件不存在
        ValueError: JSON 结构不符合预期
    """
    path = _DATA_DIR / f"{module_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Module file not found: {path}")

    with path.open(encoding="utf-8") as f:
        raw = json.load(f)

    identity_defs = {
        d["identity_id"]: _parse_identity_def(d)
        for d in raw.get("identities", [])
    }
    incident_defs = {
        d["incident_id"]: _parse_incident_def(d)
        for d in raw.get("incidents", [])
    }
    module_def = _parse_module_def(
        raw["module"],
        rules_y=[_parse_rule_def(r) for r in raw.get("rules_y", [])],
        rules_x=[_parse_rule_def(r) for r in raw.get("rules_x", [])],
        identity_pool=list(identity_defs.keys()),
        incident_pool=list(incident_defs.keys()),
    )

    return LoadedModule(
        module_def=module_def,
        identity_defs=identity_defs,
        incident_defs=incident_defs,
    )


def apply_loaded_module(state: GameState, loaded: LoadedModule) -> None:
    """
    将 load_module 结果写入 GameState：模组元数据、身份/事件定义表、
    与 EX 等与 GameState 字段对齐的开关。
    """
    state.module_def = loaded.module_def
    state.identity_defs = dict(loaded.identity_defs)
    state.incident_defs = dict(loaded.incident_defs)
    state.script.module_id = loaded.module_def.module_id
    state.script.special_rules_text = list(loaded.module_def.special_rules)
    state.ex_gauge_resets_per_loop = loaded.module_def.ex_gauge_resets_per_loop


def build_game_state_from_module(
    module_id: str,
    *,
    loop_count: int | None = None,
    days_per_loop: int | None = None,
    character_setups: list[CharacterSetup] | None = None,
    incidents: list[IncidentSchedule] | None = None,
    rule_y_id: str | None = None,
    rule_x_ids: list[str] | None = None,
    character_defs: dict[str, CharacterDef] | None = None,
    skip_script_validation: bool = False,
) -> GameState:
    """
    从模组 JSON 装配可开局使用的 GameState（含 `apply_loaded_module`、主人公手牌）。

    `loop_count` / `days_per_loop` 省略时使用 `Script` 默认值（4/4）。
    """
    loaded = load_module(module_id)
    state = GameState()
    if loop_count is not None:
        state.script.loop_count = loop_count
    if days_per_loop is not None:
        state.script.days_per_loop = days_per_loop
    apply_loaded_module(state, loaded)
    state.init_protagonist_hands()

    if rule_y_id is not None:
        state.script.rule_y = _pick_rule(loaded.module_def.rules_y, rule_y_id, "rule_y")
    if rule_x_ids is not None:
        state.script.rules_x = [
            _pick_rule(loaded.module_def.rules_x, rid, "rule_x")
            for rid in rule_x_ids
        ]

    defs = character_defs if character_defs is not None else load_character_defs()

    if character_setups is not None:
        state.script.characters = copy.deepcopy(character_setups)
        state.characters = _build_characters_from_setups(
            character_setups,
            defs,
            state.identity_defs,
        )

    if incidents is not None:
        state.script.incidents = copy.deepcopy(incidents)
        state.script.incident_public = _build_incident_public_info(incidents, state.incident_defs)

    if not skip_script_validation and _script_has_instance_input(
        character_setups=character_setups,
        incidents=incidents,
        rule_y_id=rule_y_id,
        rule_x_ids=rule_x_ids,
    ):
        issues = validate_script(
            state.script,
            ScriptValidationContext(
                module_def=loaded.module_def,
                identity_defs=loaded.identity_defs,
                incident_defs=loaded.incident_defs,
                character_defs=defs,
            ),
        )
        if issues:
            raise ScriptValidationError(issues)

    return state


def _script_has_instance_input(
    *,
    character_setups: list[CharacterSetup] | None,
    incidents: list[IncidentSchedule] | None,
    rule_y_id: str | None,
    rule_x_ids: list[str] | None,
) -> bool:
    return (
        character_setups is not None
        and incidents is not None
        and rule_y_id is not None
        and rule_x_ids is not None
    )


def _pick_rule(pool: list[RuleDef], rule_id: str, rule_kind: str) -> RuleDef:
    for rule in pool:
        if rule.rule_id == rule_id:
            return copy.deepcopy(rule)
    raise ValueError(f"Unknown {rule_kind} id: {rule_id}")


def _build_characters_from_setups(
    setups: list[CharacterSetup],
    defs: dict[str, CharacterDef],
    identity_defs: dict[str, IdentityDef],
) -> dict[str, CharacterState]:
    states: dict[str, CharacterState] = {}
    for setup in setups:
        if setup.character_id in states:
            raise ValueError(f"Duplicated character in setup: {setup.character_id}")
        identity_id = normalize_identity_id(setup.identity_id)
        if identity_id not in identity_defs and identity_id != "平民":
            raise ValueError(f"Unknown identity_id in setup: {setup.identity_id}")
        state = instantiate_character_state(setup, defs)
        states[setup.character_id] = state
    return states


def _build_incident_public_info(
    incidents: list[IncidentSchedule],
    incident_defs: dict[str, IncidentDef],
) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for inc in incidents:
        incident_def = incident_defs.get(inc.incident_id)
        public.append(
            {
                "name": incident_def.name if incident_def else inc.incident_id,
                "day": inc.day,
            }
        )
    return public


# ---------------------------------------------------------------------------
# 内部解析函数
# ---------------------------------------------------------------------------
def _parse_effect(data: dict[str, Any]) -> Effect:
    effect_type = EffectType(data["effect_type"])
    token_type = TokenType(data["token_type"]) if data.get("token_type") else None
    condition = _parse_condition(data["condition"]) if data.get("condition") else None
    return Effect(
        effect_type=effect_type,
        target=data.get("target", "self"),
        token_type=token_type,
        amount=data.get("amount", 0),
        value=data.get("value"),
        condition=condition,
    )


def _parse_condition(data: dict[str, Any]) -> Condition:
    return Condition(
        condition_type=data["condition_type"],
        params=data.get("params", {}),
    )


def _parse_ability(data: dict[str, Any]) -> Ability:
    return Ability(
        ability_id=data["ability_id"],
        name=data["name"],
        ability_type=AbilityType(data["ability_type"]),
        timing=AbilityTiming(data["timing"]),
        description=data.get("description", ""),
        condition=_parse_condition(data["condition"]) if data.get("condition") else None,
        effects=[_parse_effect(e) for e in data.get("effects", [])],
        sequential=data.get("sequential", False),
        goodwill_cost=data.get("goodwill_cost", 0),
        once_per_loop=data.get("once_per_loop", False),
        once_per_day=data.get("once_per_day", False),
        can_be_refused=data.get("can_be_refused", False),
    )


def _parse_identity_def(data: dict[str, Any]) -> IdentityDef:
    traits = {Trait(t) for t in data.get("traits", [])}
    return IdentityDef(
        identity_id=data["identity_id"],
        name=data["name"],
        module=data["module"],
        traits=traits,
        max_count=data.get("max_count"),
        abilities=[_parse_ability(a) for a in data.get("abilities", [])],
        description=data.get("description", ""),
    )


def _parse_incident_def(data: dict[str, Any]) -> IncidentDef:
    return IncidentDef(
        incident_id=data["incident_id"],
        name=data["name"],
        module=data["module"],
        effects=[_parse_effect(e) for e in data.get("effects", [])],
        sequential=data.get("sequential", False),
        extra_condition=_parse_condition(data["extra_condition"]) if data.get("extra_condition") else None,
        description=data.get("description", ""),
    )


def _parse_rule_def(data: dict[str, Any]) -> RuleDef:
    return RuleDef(
        rule_id=data["rule_id"],
        name=data["name"],
        rule_type=data["rule_type"],
        module=data["module"],
        identity_slots=data.get("identity_slots", {}),
        abilities=[_parse_ability(a) for a in data.get("abilities", [])],
        description=data.get("description", ""),
    )


def _parse_module_def(
    data: dict[str, Any],
    rules_y: list[RuleDef],
    rules_x: list[RuleDef],
    identity_pool: list[str],
    incident_pool: list[str],
) -> ModuleDef:
    return ModuleDef(
        module_id=data["module_id"],
        name=data["name"],
        special_rules=data.get("special_rules", []),
        rule_x_count=data.get("rule_x_count", 2),
        has_final_guess=data.get("has_final_guess", True),
        has_ex_gauge=data.get("has_ex_gauge", False),
        ex_gauge_resets_per_loop=data.get("ex_gauge_resets_per_loop", True),
        rules_y=rules_y,
        rules_x=rules_x,
        identity_pool=identity_pool,
        incident_pool=incident_pool,
    )
