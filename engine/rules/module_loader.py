"""惨剧轮回 — 模组加载器

将 data/modules/{module_id}.json 反序列化为运行时对象，
填充 GameState.identity_defs / incident_defs，并返回 ModuleDef。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.models.enums import AbilityTiming, AbilityType, EffectType, TokenType, Trait
from engine.models.identity import Ability, Condition, Effect, IdentityDef
from engine.models.incident import IncidentDef
from engine.models.script import ModuleDef, RuleDef

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
