"""Smoke test: committed data/ passes validate_data_root."""

from __future__ import annotations

from pathlib import Path

from engine.validation.runner import default_data_dir, validate_data_root


def test_committed_data_passes_validation() -> None:
    root = default_data_dir()
    assert root.is_dir(), f"expected data dir at {root}"
    issues = validate_data_root(root)
    assert not issues, "\n".join(f"{i.path}: {i.message}" for i in issues)


def test_validate_data_root_accepts_explicit_path() -> None:
    here = Path(__file__).resolve().parent
    project = here.parent
    data = project / "data"
    issues = validate_data_root(data)
    assert not issues
