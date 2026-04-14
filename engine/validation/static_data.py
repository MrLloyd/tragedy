"""board.json / cards.json / characters.json 校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine.models.enums import AreaId, Attribute, CardType
from engine.validation.common import ValidationIssue, enum_values

_AREA_VALUES = enum_values(AreaId)
_CARD_VALUES = enum_values(CardType)
_ATTR_VALUES = enum_values(Attribute)
# 2x2 版图格，不含远方
_BOARD_CELL_AREAS = _AREA_VALUES - {AreaId.FARAWAY.value}


def validate_board(path: Path, file_rel: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return [ValidationIssue(file_rel, f"invalid JSON: {e}")]

    if not isinstance(data, dict):
        return [ValidationIssue(file_rel, "root must be an object")]

    layout = data.get("layout")
    if layout is None:
        issues.append(ValidationIssue(f"{file_rel}:layout", "missing key 'layout'"))
        return issues
    if not isinstance(layout, dict):
        issues.append(ValidationIssue(f"{file_rel}:layout", "must be an object"))
        return issues

    for key, pos in layout.items():
        if key not in _BOARD_CELL_AREAS:
            issues.append(
                ValidationIssue(
                    f"{file_rel}:layout.{key}",
                    f"unknown or invalid board cell area (must be 2x2 id, not faraway): {key!r}",
                )
            )
        if not isinstance(pos, dict):
            issues.append(ValidationIssue(f"{file_rel}:layout.{key}", "position must be an object"))
            continue
        for rk in ("row", "col"):
            if rk not in pos:
                issues.append(ValidationIssue(f"{file_rel}:layout.{key}", f"missing '{rk}'"))
            else:
                v = pos[rk]
                if not isinstance(v, int) or v not in (0, 1):
                    issues.append(
                        ValidationIssue(
                            f"{file_rel}:layout.{key}.{rk}",
                            f"expected 0 or 1, got {v!r}",
                        )
                    )

    sa = data.get("special_areas")
    if sa is None:
        issues.append(ValidationIssue(f"{file_rel}:special_areas", "missing key 'special_areas'"))
    elif not isinstance(sa, list):
        issues.append(ValidationIssue(f"{file_rel}:special_areas", "must be an array"))
    else:
        for i, a in enumerate(sa):
            if a not in _AREA_VALUES:
                issues.append(
                    ValidationIssue(
                        f"{file_rel}:special_areas[{i}]",
                        f"invalid AreaId: {a!r}",
                    )
                )

    return issues


def _validate_card_entries(
    items: Any,
    file_rel: str,
    path_prefix: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(items, list):
        issues.append(ValidationIssue(path_prefix, "must be an array"))
        return
    for i, entry in enumerate(items):
        p = f"{path_prefix}[{i}]"
        if not isinstance(entry, dict):
            issues.append(ValidationIssue(p, "entry must be an object"))
            continue
        ct = entry.get("card_type")
        if ct not in _CARD_VALUES:
            issues.append(
                ValidationIssue(
                    f"{p}.card_type",
                    f"invalid CardType: {ct!r}",
                )
            )
        c = entry.get("count")
        if not isinstance(c, int) or c < 1:
            issues.append(ValidationIssue(f"{p}.count", f"expected positive int, got {c!r}"))
        opl = entry.get("once_per_loop")
        if not isinstance(opl, bool):
            issues.append(ValidationIssue(f"{p}.once_per_loop", f"expected bool, got {opl!r}"))


def validate_cards(path: Path, file_rel: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [ValidationIssue(file_rel, f"invalid JSON: {e}")]

    if not isinstance(data, dict):
        return [ValidationIssue(file_rel, "root must be an object")]

    for key in ("mastermind_base", "protagonist_base"):
        if key not in data:
            issues.append(ValidationIssue(f"{file_rel}:{key}", f"missing key {key!r}"))
        else:
            _validate_card_entries(data[key], file_rel, f"{file_rel}:{key}", issues)

    ext = data.get("extensions")
    if ext is None:
        issues.append(ValidationIssue(f"{file_rel}:extensions", "missing key 'extensions'"))
    elif not isinstance(ext, dict):
        issues.append(ValidationIssue(f"{file_rel}:extensions", "must be an object"))
    else:
        for sub in ("mastermind", "protagonist"):
            if sub not in ext:
                issues.append(ValidationIssue(f"{file_rel}:extensions", f"missing key {sub!r}"))
            else:
                _validate_card_entries(
                    ext[sub], file_rel, f"{file_rel}:extensions.{sub}", issues
                )

    return issues


def validate_characters(
    path: Path,
    file_rel: str,
    board_layout_keys: frozenset[str],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [ValidationIssue(file_rel, f"invalid JSON: {e}")]

    chars = data.get("characters")
    if chars is None:
        return [ValidationIssue(f"{file_rel}:characters", "missing key 'characters'")]
    if not isinstance(chars, list):
        return [ValidationIssue(f"{file_rel}:characters", "must be an array")]

    seen_ids: set[str] = set()
    for i, ch in enumerate(chars):
        p = f"{file_rel}:characters[{i}]"
        if not isinstance(ch, dict):
            issues.append(ValidationIssue(p, "entry must be an object"))
            continue

        cid = ch.get("character_id")
        if not isinstance(cid, str) or not cid.strip():
            issues.append(ValidationIssue(f"{p}.character_id", "must be non-empty string"))
        else:
            if cid in seen_ids:
                issues.append(ValidationIssue(f"{p}.character_id", f"duplicate character_id: {cid!r}"))
            seen_ids.add(cid)

        ia = ch.get("initial_area")
        if ia not in _AREA_VALUES:
            issues.append(ValidationIssue(f"{p}.initial_area", f"invalid AreaId: {ia!r}"))
        else:
            if ia != AreaId.FARAWAY.value and ia not in board_layout_keys:
                issues.append(
                    ValidationIssue(
                        f"{p}.initial_area",
                        f"initial_area {ia!r} not present in board.json layout",
                    )
                )

        fa = ch.get("forbidden_areas")
        if not isinstance(fa, list):
            issues.append(ValidationIssue(f"{p}.forbidden_areas", "must be an array"))
        else:
            for j, area in enumerate(fa):
                if area not in _AREA_VALUES:
                    issues.append(
                        ValidationIssue(
                            f"{p}.forbidden_areas[{j}]",
                            f"invalid AreaId: {area!r}",
                        )
                    )

        attrs = ch.get("attributes")
        if not isinstance(attrs, list):
            issues.append(ValidationIssue(f"{p}.attributes", "must be an array"))
        else:
            for j, at in enumerate(attrs):
                if at not in _ATTR_VALUES:
                    issues.append(
                        ValidationIssue(
                            f"{p}.attributes[{j}]",
                            f"invalid Attribute: {at!r}",
                        )
                    )

        pl = ch.get("paranoia_limit")
        if not isinstance(pl, int) or pl < 1:
            issues.append(
                ValidationIssue(f"{p}.paranoia_limit", f"expected int >= 1, got {pl!r}")
            )

    return issues


def load_board_layout_keys(path: Path) -> frozenset[str] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        layout = data.get("layout")
        if isinstance(layout, dict):
            return frozenset(layout.keys())
    except (json.JSONDecodeError, OSError):
        pass
    return None
