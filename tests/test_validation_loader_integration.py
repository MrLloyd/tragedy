"""校验通过后，loader 可消费同一份 data（Phase 2 DoD-4 联动）。"""

from __future__ import annotations

from engine.validation.runner import default_data_dir, validate_data_root
from engine.rules.module_loader import load_module


def test_validate_data_root_then_load_both_modules() -> None:
    root = default_data_dir()
    issues = validate_data_root(root)
    assert not issues, "\n".join(f"{i.path}: {i.message}" for i in issues)

    for module_id in ("first_steps", "basic_tragedy_x"):
        loaded = load_module(module_id)
        assert loaded.module_def.module_id == module_id
        assert isinstance(loaded.identity_defs, dict)
        assert isinstance(loaded.incident_defs, dict)
