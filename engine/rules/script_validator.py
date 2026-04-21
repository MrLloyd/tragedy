"""剧本实例校验入口（P4-6）。"""

from __future__ import annotations

from dataclasses import dataclass

from engine.models.enums import AreaId, Attribute, TokenType, Trait
from engine.models.script import CharacterSetup, RuleDef, Script
from engine.rules.character_loader import (
    CharacterDef,
    normalize_identity_id,
)
from engine.models.identity import IdentityDef
from engine.models.incident import IncidentDef
from engine.models.script import ModuleDef
from engine.validation.common import ValidationIssue


@dataclass
class ScriptValidationContext:
    module_def: ModuleDef
    identity_defs: dict[str, IdentityDef]
    incident_defs: dict[str, IncidentDef]
    character_defs: dict[str, CharacterDef]


class ScriptValidationError(ValueError):
    """剧本实例校验失败。"""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        message = "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        super().__init__(message)


def validate_script(script: Script, context: ScriptValidationContext) -> list[ValidationIssue]:
    """总入口：基础剧本校验 → SCRIPT_CREATION 规则校验。"""
    issues = validate_basic_script(script, context)
    if issues:
        return issues
    issues.extend(validate_script_creation_constraints(script, context))
    return issues


def validate_basic_script(
    script: Script,
    context: ScriptValidationContext,
) -> list[ValidationIssue]:
    """基础剧本结构校验，与具体规则文字无关。"""
    issues: list[ValidationIssue] = []
    module = context.module_def

    if script.rule_y is None:
        issues.append(ValidationIssue("script.rule_y", "rule_y is required"))
    elif script.rule_y.rule_id not in {rule.rule_id for rule in module.rules_y}:
        issues.append(ValidationIssue("script.rule_y", f"unknown rule_y: {script.rule_y.rule_id!r}"))

    selected_rule_x_ids = [rule.rule_id for rule in script.rules_x]
    known_rule_x_ids = {rule.rule_id for rule in module.rules_x}
    if len(script.rules_x) != module.rule_x_count:
        issues.append(
            ValidationIssue(
                "script.rules_x",
                f"expected {module.rule_x_count} rule_x, got {len(script.rules_x)}",
            )
        )
    if len(set(selected_rule_x_ids)) != len(selected_rule_x_ids):
        issues.append(ValidationIssue("script.rules_x", "duplicated rule_x"))
    for idx, rule in enumerate(script.rules_x):
        if rule.rule_id not in known_rule_x_ids:
            issues.append(ValidationIssue(f"script.rules_x[{idx}]", f"unknown rule_x: {rule.rule_id!r}"))

    seen_characters: set[str] = set()
    for idx, setup in enumerate(script.characters):
        path = f"script.characters[{idx}]"
        if setup.character_id in seen_characters:
            issues.append(ValidationIssue(f"{path}.character_id", f"duplicated character: {setup.character_id!r}"))
        seen_characters.add(setup.character_id)

        if setup.character_id not in context.character_defs:
            issues.append(ValidationIssue(f"{path}.character_id", f"unknown character: {setup.character_id!r}"))
        identity_id = normalize_identity_id(setup.identity_id)
        if identity_id != "平民" and identity_id not in context.identity_defs:
            issues.append(ValidationIssue(f"{path}.identity_id", f"unknown identity: {setup.identity_id!r}"))

    selected_character_ids = {setup.character_id for setup in script.characters}
    seen_incident_keys: set[tuple[int, str]] = set()
    for idx, incident in enumerate(script.incidents):
        path = f"script.incidents[{idx}]"
        if incident.incident_id not in context.incident_defs:
            issues.append(ValidationIssue(f"{path}.incident_id", f"unknown incident: {incident.incident_id!r}"))
        if incident.day < 1 or incident.day > script.days_per_loop:
            issues.append(
                ValidationIssue(
                    f"{path}.day",
                    f"incident day must be in 1..{script.days_per_loop}, got {incident.day}",
                )
            )
        if incident.perpetrator_id not in selected_character_ids:
            issues.append(
                ValidationIssue(
                    f"{path}.perpetrator_id",
                    f"unknown incident perpetrator: {incident.perpetrator_id!r}",
                )
            )
        for target_index, target_id in enumerate(incident.target_character_ids):
            if target_id not in selected_character_ids:
                issues.append(
                    ValidationIssue(
                        f"{path}.target_character_ids[{target_index}]",
                        f"unknown incident target character: {target_id!r}",
                    )
                )
        for area_index, area_id in enumerate(incident.target_area_ids):
            try:
                AreaId(area_id)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        f"{path}.target_area_ids[{area_index}]",
                        f"unknown incident target area: {area_id!r}",
                    )
                )
        for token_index, token_name in enumerate(incident.chosen_token_types):
            try:
                TokenType(token_name)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        f"{path}.chosen_token_types[{token_index}]",
                        f"unknown incident token type: {token_name!r}",
                    )
                )
        key = (incident.day, incident.incident_id)
        if key in seen_incident_keys:
            issues.append(ValidationIssue(path, f"duplicated incident on day: {incident.incident_id!r}"))
        seen_incident_keys.add(key)

    if script.rule_y is not None:
        issues.extend(_validate_identity_slots(script, [script.rule_y, *script.rules_x], context))

    return issues


def validate_script_creation_constraints(
    script: Script,
    context: ScriptValidationContext,
) -> list[ValidationIssue]:
    """SCRIPT_CREATION / 剧本制作时约束。"""
    if context.module_def.module_id not in {"first_steps", "basic_tragedy_x"}:
        return []

    issues: list[ValidationIssue] = []
    character_by_identity = _characters_by_identity(script)

    if script.rule_y and script.rule_y.rule_id == "btx_cursed_contract":
        for character_id in character_by_identity.get("key_person", []):
            char_def = context.character_defs[character_id]
            if Attribute.GIRL not in char_def.attributes:
                issues.append(
                    ValidationIssue(
                        f"script.rule_y.{script.rule_y.rule_id}",
                        "key_person must be assigned to a girl character",
                    )
                )

    for idx, setup in enumerate(script.characters):
        char_def = context.character_defs[setup.character_id]
        identity_id = normalize_identity_id(setup.identity_id)
        identity_def = context.identity_defs.get(identity_id)
        path = f"script.characters[{idx}]"

        if _has_script_constraint(char_def, "cannot_be_commoner") and identity_id == "平民":
            issues.append(
                ValidationIssue(
                    f"{path}.identity_id",
                    f"{char_def.name} cannot be assigned commoner at script creation",
                )
            )

        if _has_script_constraint(char_def, "cannot_ignore_goodwill_identity"):
            traits = identity_def.traits if identity_def is not None else set()
            if Trait.IGNORE_GOODWILL in traits or Trait.MUST_IGNORE_GOODWILL in traits:
                issues.append(
                    ValidationIssue(
                        f"{path}.identity_id",
                        f"{char_def.name} cannot be assigned an identity with ignore-goodwill trait",
                    )
                )

    return issues


def _validate_identity_slots(
    script: Script,
    rules: list[RuleDef],
    context: ScriptValidationContext,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required: dict[str, int] = {}
    for rule in rules:
        for identity_id, count in rule.identity_slots.items():
            required[identity_id] = required.get(identity_id, 0) + count

    actual: dict[str, int] = {}
    for setup in script.characters:
        identity_id = normalize_identity_id(setup.identity_id)
        if identity_id == "平民":
            continue
        actual[identity_id] = actual.get(identity_id, 0) + 1

    for identity_id, expected in required.items():
        got = actual.get(identity_id, 0)
        if got != expected:
            issues.append(
                ValidationIssue(
                    f"script.identity_slots.{identity_id}",
                    f"expected {expected}, got {got}",
                )
            )

    for identity_id, got in actual.items():
        if identity_id not in required:
            identity_def = context.identity_defs.get(identity_id)
            max_count = identity_def.max_count if identity_def else None
            if max_count is None:
                issues.append(
                    ValidationIssue(
                        f"script.identity_slots.{identity_id}",
                        "identity is not required by selected rules",
                    )
                )
            elif got > max_count:
                issues.append(
                    ValidationIssue(
                        f"script.identity_slots.{identity_id}",
                        f"exceeds max_count {max_count}, got {got}",
                    )
                )

    return issues


def _characters_by_identity(script: Script) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for setup in script.characters:
        identity_id = normalize_identity_id(setup.identity_id)
        result.setdefault(identity_id, []).append(setup.character_id)
    return result


def _has_script_constraint(character_def: CharacterDef, constraint: str) -> bool:
    if constraint in character_def.script_constraints:
        return True
    text = character_def.trait_rule
    if constraint == "cannot_be_commoner":
        return "不能為「平民」" in text or "不能为「平民」" in text or "不能为平民" in text
    if constraint == "cannot_ignore_goodwill_identity":
        return "无视友好特性的身份" in text or "無視友好特性的身份" in text
    return False
