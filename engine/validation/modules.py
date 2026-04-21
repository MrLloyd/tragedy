"""data/modules/*.json 校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.models.enums import (
    AbilityTiming,
    AbilityType,
    AreaId,
    EffectType,
    TokenType,
    Trait,
)
from engine.validation.common import KNOWN_CONDITION_TYPES, ValidationIssue, enum_values

_TIMING = enum_values(AbilityTiming)
_ABILITY_TYPE = enum_values(AbilityType)
_EFFECT_TYPE = enum_values(EffectType)
_TOKEN_TYPE = enum_values(TokenType)
_TRAIT = enum_values(Trait)
_AREA = enum_values(AreaId)


def _validate_condition(
    cond: Any,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(cond, dict):
        issues.append(ValidationIssue(path, "condition must be an object"))
        return
    ct = cond.get("condition_type")
    if ct not in KNOWN_CONDITION_TYPES:
        issues.append(
            ValidationIssue(
                f"{path}.condition_type",
                f"unknown condition_type: {ct!r}",
            )
        )
    params = cond.get("params")
    if params is not None and not isinstance(params, dict):
        issues.append(ValidationIssue(f"{path}.params", "must be an object"))
        return
    if ct in {"all_of", "any_of"} and isinstance(params, dict):
        nested = params.get("conditions")
        if not isinstance(nested, list):
            issues.append(ValidationIssue(f"{path}.params.conditions", "must be an array"))
        else:
            for idx, item in enumerate(nested):
                _validate_condition(item, f"{path}.params.conditions[{idx}]", issues)
    if ct == "token_check" and isinstance(params, dict):
        tgt = params.get("target")
        if isinstance(tgt, str) and tgt not in _AREA and tgt not in {"self", "other"}:
            issues.append(
                ValidationIssue(
                    f"{path}.params.target",
                    f"invalid area or token target: {tgt!r}",
                )
            )
        tok = params.get("token")
        if isinstance(tok, str) and tok not in _TOKEN_TYPE:
            issues.append(
                ValidationIssue(
                    f"{path}.params.token",
                    f"invalid TokenType: {tok!r}",
                )
            )
    if ct in {"identity_token_check", "same_area_identity_token_check"} and isinstance(params, dict):
        identity_id = params.get("identity_id")
        if not isinstance(identity_id, str) or not identity_id.strip():
            issues.append(
                ValidationIssue(
                    f"{path}.params.identity_id",
                    "must be non-empty string",
                )
            )
        tok = params.get("token")
        if isinstance(tok, str) and tok not in _TOKEN_TYPE:
            issues.append(
                ValidationIssue(
                    f"{path}.params.token",
                    f"invalid TokenType: {tok!r}",
                )
            )


def _validate_effects(
    effects: Any,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(effects, list):
        issues.append(ValidationIssue(path, "effects must be an array"))
        return
    for j, eff in enumerate(effects):
        ep = f"{path}[{j}]"
        if not isinstance(eff, dict):
            issues.append(ValidationIssue(ep, "effect must be an object"))
            continue
        et = eff.get("effect_type")
        if et not in _EFFECT_TYPE:
            issues.append(
                ValidationIssue(f"{ep}.effect_type", f"invalid EffectType: {et!r}")
            )
        if et == EffectType.PLACE_TOKEN.value:  # "place_token"
            tt = eff.get("token_type")
            if tt not in _TOKEN_TYPE and eff.get("value") != "choose_token_type":
                issues.append(
                    ValidationIssue(
                        f"{ep}.token_type",
                        f"place_token requires valid token_type, got {tt!r}",
                    )
                )


def _validate_abilities(
    abilities: Any,
    path: str,
    issues: list[ValidationIssue],
    seen_ability_ids: set[str],
) -> None:
    if not isinstance(abilities, list):
        issues.append(ValidationIssue(path, "abilities must be an array"))
        return
    for k, ab in enumerate(abilities):
        ap = f"{path}[{k}]"
        if not isinstance(ab, dict):
            issues.append(ValidationIssue(ap, "ability must be an object"))
            continue
        aid = ab.get("ability_id")
        if isinstance(aid, str):
            if aid in seen_ability_ids:
                issues.append(ValidationIssue(f"{ap}.ability_id", f"duplicate ability_id: {aid!r}"))
            seen_ability_ids.add(aid)
        at = ab.get("ability_type")
        if at not in _ABILITY_TYPE:
            issues.append(ValidationIssue(f"{ap}.ability_type", f"invalid AbilityType: {at!r}"))
        tm = ab.get("timing")
        if tm not in _TIMING:
            issues.append(ValidationIssue(f"{ap}.timing", f"invalid AbilityTiming: {tm!r}"))
        if "condition" in ab and ab["condition"] is not None:
            _validate_condition(ab["condition"], f"{ap}.condition", issues)
        _validate_effects(ab.get("effects"), f"{ap}.effects", issues)


def _validate_rules(
    rules: Any,
    path_key: str,
    file_rel: str,
    module_id: str,
    expected_rule_type: str,
    identity_ids: frozenset[str],
    issues: list[ValidationIssue],
    seen_ability_ids: set[str],
) -> None:
    if not isinstance(rules, list):
        issues.append(ValidationIssue(f"{file_rel}:{path_key}", "must be an array"))
        return
    for i, rule in enumerate(rules):
        rp = f"{file_rel}:{path_key}[{i}]"
        if not isinstance(rule, dict):
            issues.append(ValidationIssue(rp, "rule must be an object"))
            continue
        rid = rule.get("rule_id")
        if not isinstance(rid, str) or not rid.strip():
            issues.append(ValidationIssue(f"{rp}.rule_id", "must be non-empty string"))
        rt = rule.get("rule_type")
        if rt != expected_rule_type:
            issues.append(
                ValidationIssue(
                    f"{rp}.rule_type",
                    f"expected {expected_rule_type!r}, got {rt!r}",
                )
            )
        mod = rule.get("module")
        if mod != module_id:
            issues.append(
                ValidationIssue(
                    f"{rp}.module",
                    f"expected {module_id!r}, got {mod!r}",
                )
            )
        slots = rule.get("identity_slots")
        if not isinstance(slots, dict):
            issues.append(ValidationIssue(f"{rp}.identity_slots", "must be an object"))
        else:
            for slot_key in slots.keys():
                if slot_key not in identity_ids:
                    issues.append(
                        ValidationIssue(
                            f"{rp}.identity_slots.{slot_key}",
                            f"identity_id not defined in identities: {slot_key!r}",
                        )
                    )
                c = slots[slot_key]
                if not isinstance(c, int) or c < 1:
                    issues.append(
                        ValidationIssue(
                            f"{rp}.identity_slots.{slot_key}",
                            f"expected positive int, got {c!r}",
                        )
                    )
        _validate_abilities(
            rule.get("abilities"),
            f"{rp}.abilities",
            issues,
            seen_ability_ids,
        )


def _validate_identities(
    identities: Any,
    file_rel: str,
    issues: list[ValidationIssue],
    seen_ability_ids: set[str],
) -> frozenset[str]:
    ids: set[str] = set()
    if not isinstance(identities, list):
        issues.append(ValidationIssue(f"{file_rel}:identities", "must be an array"))
        return frozenset()
    for i, idf in enumerate(identities):
        ip = f"{file_rel}:identities[{i}]"
        if not isinstance(idf, dict):
            issues.append(ValidationIssue(ip, "identity must be an object"))
            continue
        iid = idf.get("identity_id")
        if not isinstance(iid, str) or not iid.strip():
            issues.append(ValidationIssue(f"{ip}.identity_id", "must be non-empty string"))
        else:
            if iid in ids:
                issues.append(ValidationIssue(f"{ip}.identity_id", f"duplicate identity_id: {iid!r}"))
            ids.add(iid)
        traits = idf.get("traits")
        if not isinstance(traits, list):
            issues.append(ValidationIssue(f"{ip}.traits", "must be an array"))
        else:
            for j, tr in enumerate(traits):
                if tr not in _TRAIT:
                    issues.append(
                        ValidationIssue(f"{ip}.traits[{j}]", f"invalid Trait: {tr!r}")
                    )
        mc = idf.get("max_count")
        if mc is not None and (not isinstance(mc, int) or mc < 1):
            issues.append(
                ValidationIssue(f"{ip}.max_count", f"expected positive int or omitted, got {mc!r}")
            )
        _validate_abilities(
            idf.get("abilities"),
            f"{ip}.abilities",
            issues,
            seen_ability_ids,
        )
    return frozenset(ids)


def _validate_incidents(
    incidents: Any,
    file_rel: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(incidents, list):
        issues.append(ValidationIssue(f"{file_rel}:incidents", "must be an array"))
        return
    seen: set[str] = set()
    for i, inc in enumerate(incidents):
        p = f"{file_rel}:incidents[{i}]"
        if not isinstance(inc, dict):
            issues.append(ValidationIssue(p, "incident must be an object"))
            continue
        iid = inc.get("incident_id")
        if not isinstance(iid, str) or not iid.strip():
            issues.append(ValidationIssue(f"{p}.incident_id", "must be non-empty string"))
        elif iid in seen:
            issues.append(ValidationIssue(f"{p}.incident_id", f"duplicate incident_id: {iid!r}"))
        else:
            seen.add(iid)
        mod = inc.get("module")
        # module id checked after we read expected from filename
        seq = inc.get("sequential")
        if not isinstance(seq, bool):
            issues.append(ValidationIssue(f"{p}.sequential", f"expected bool, got {seq!r}"))
        _validate_effects(inc.get("effects"), f"{p}.effects", issues)


def validate_module_file(path: Path, file_rel: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [ValidationIssue(file_rel, f"invalid JSON: {e}")]

    if not isinstance(data, dict):
        return [ValidationIssue(file_rel, "root must be an object")]

    expected_keys = ("module", "rules_y", "rules_x", "identities", "incidents")
    for k in expected_keys:
        if k not in data:
            issues.append(ValidationIssue(f"{file_rel}:{k}", f"missing key {k!r}"))

    mod = data.get("module")
    if not isinstance(mod, dict):
        issues.append(ValidationIssue(f"{file_rel}:module", "must be an object"))
        return issues

    stem = path.stem
    mid = mod.get("module_id")
    if mid != stem:
        issues.append(
            ValidationIssue(
                f"{file_rel}:module.module_id",
                f"expected {stem!r} (from filename), got {mid!r}",
            )
        )

    module_id = mid if isinstance(mid, str) else stem

    seen_ability_ids: set[str] = set()
    identities = data.get("identities")
    identity_ids = _validate_identities(identities, file_rel, issues, seen_ability_ids)

    _validate_rules(
        data.get("rules_y"),
        "rules_y",
        file_rel,
        module_id,
        "Y",
        identity_ids,
        issues,
        seen_ability_ids,
    )
    _validate_rules(
        data.get("rules_x"),
        "rules_x",
        file_rel,
        module_id,
        "X",
        identity_ids,
        issues,
        seen_ability_ids,
    )

    _validate_incidents(data.get("incidents"), file_rel, issues)
    # incident module field
    incs = data.get("incidents")
    if isinstance(incs, list):
        for i, inc in enumerate(incs):
            if isinstance(inc, dict):
                m = inc.get("module")
                if m != module_id:
                    issues.append(
                        ValidationIssue(
                            f"{file_rel}:incidents[{i}].module",
                            f"expected {module_id!r}, got {m!r}",
                        )
                    )

    return issues
