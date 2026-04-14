"""聚合校验 data/ 目录。"""

from __future__ import annotations

from pathlib import Path

from engine.validation.common import ValidationIssue
from engine.validation.modules import validate_module_file
from engine.validation.static_data import (
    load_board_layout_keys,
    validate_board,
    validate_cards,
    validate_characters,
)


def default_data_dir() -> Path:
    """仓库根目录下的 data/（engine/validation/runner.py → 上两级为 engine，再上为根）。"""
    return Path(__file__).resolve().parent.parent.parent / "data"


def validate_data_root(data_root: Path | None = None) -> list[ValidationIssue]:
    """
    校验 data_root 下 board.json、cards.json、characters.json、modules/*.json。
    返回所有问题列表；空列表表示通过。
    """
    root = data_root if data_root is not None else default_data_dir()
    issues: list[ValidationIssue] = []

    board_path = root / "board.json"
    cards_path = root / "cards.json"
    chars_path = root / "characters.json"
    modules_dir = root / "modules"

    if not root.is_dir():
        return [ValidationIssue(str(root), "data directory does not exist")]

    if board_path.is_file():
        issues.extend(validate_board(board_path, "board.json"))
    else:
        issues.append(ValidationIssue("board.json", "file missing"))

    layout_keys = load_board_layout_keys(board_path) if board_path.is_file() else None
    if layout_keys is None and board_path.is_file():
        layout_keys = frozenset()

    if cards_path.is_file():
        issues.extend(validate_cards(cards_path, "cards.json"))
    else:
        issues.append(ValidationIssue("cards.json", "file missing"))

    if chars_path.is_file():
        issues.extend(
            validate_characters(
                chars_path,
                "characters.json",
                layout_keys if layout_keys is not None else frozenset(),
            )
        )
    else:
        issues.append(ValidationIssue("characters.json", "file missing"))

    if modules_dir.is_dir():
        json_files = sorted(modules_dir.glob("*.json"))
        if not json_files:
            issues.append(ValidationIssue("modules/", "no module JSON files found"))
        for mod_path in json_files:
            rel = f"modules/{mod_path.name}"
            issues.extend(validate_module_file(mod_path, rel))
    else:
        issues.append(ValidationIssue("modules/", "directory missing"))

    return issues
