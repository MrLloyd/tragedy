"""IdentityRegistry / IncidentRegistry 与 load_module 集成（Phase 2 DoD-2 / DoD-5）。"""

from __future__ import annotations

from engine.rules.identity_registry import IdentityRegistry
from engine.rules.incident_registry import IncidentRegistry
from engine.rules.module_loader import load_module


def test_identity_registry_covers_first_steps_module() -> None:
    loaded = load_module("first_steps")
    reg = IdentityRegistry()
    reg.register(loaded.identity_defs)

    assert len(reg) == len(loaded.identity_defs)
    for iid, idef in loaded.identity_defs.items():
        assert reg.get(iid) is idef
    sample = next(iter(loaded.identity_defs.keys()))
    assert reg.get(sample) is not None
    assert reg.all()[sample] == loaded.identity_defs[sample]


def test_incident_registry_covers_first_steps_module() -> None:
    loaded = load_module("first_steps")
    reg = IncidentRegistry()
    reg.register(loaded.incident_defs)

    assert len(reg) == len(loaded.incident_defs)
    for eid, edef in loaded.incident_defs.items():
        assert reg.get(eid) is edef
