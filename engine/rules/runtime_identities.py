"""运行时身份同步（P4-5）。"""

from __future__ import annotations

import copy

from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.identity import IdentityDef
from engine.rules.module_loader import load_module

_VIRUS_REASON = "paranoia_expansion_virus"
_IDENTITY_FALLBACK_MODULES = ("basic_tragedy_x", "first_steps")
_RUNTIME_IDENTITY_CACHE: dict[str, IdentityDef] = {}


def sync_dynamic_identities(state: GameState) -> None:
    """同步所有角色的运行时身份变化。"""
    for character in state.characters.values():
        sync_character_identity(state, character)


def sync_character_identity(state: GameState, character: CharacterState) -> None:
    """同步单个角色的运行时身份变化。"""
    if character.is_removed:
        return

    if _should_be_serial_killer_by_virus(state, character):
        _apply_identity_change(state, character, "serial_killer", reason=_VIRUS_REASON)
        return

    if character.identity_change_reason == _VIRUS_REASON:
        _apply_identity_change(
            state,
            character,
            character.original_identity_id,
            reason=None,
        )


def apply_identity_change(
    state: GameState,
    character_id: str,
    *,
    identity_id: str,
    reason: str | None = None,
) -> None:
    """显式应用身份变更效果。"""
    character = state.characters.get(character_id)
    if character is None:
        return
    _apply_identity_change(state, character, identity_id, reason=reason)


def _apply_identity_change(
    state: GameState,
    character: CharacterState,
    identity_id: str,
    *,
    reason: str | None,
) -> None:
    if identity_id != "平民" and identity_id not in state.identity_defs:
        fallback = _load_runtime_identity_def(identity_id)
        if fallback is None:
            raise ValueError(f"Unknown identity_id for runtime change: {identity_id}")
        state.identity_defs[identity_id] = fallback
    character.identity_id = identity_id
    character.identity_change_reason = reason


def _should_be_serial_killer_by_virus(state: GameState, character: CharacterState) -> bool:
    return (
        _load_runtime_identity_def("serial_killer") is not None
        and character.is_alive
        and character.original_identity_id == "平民"
        and character.tokens.paranoia >= 3
    )


def _load_runtime_identity_def(identity_id: str) -> IdentityDef | None:
    cached = _RUNTIME_IDENTITY_CACHE.get(identity_id)
    if cached is not None:
        return copy.deepcopy(cached)

    for module_id in _IDENTITY_FALLBACK_MODULES:
        loaded = load_module(module_id)
        identity_def = loaded.identity_defs.get(identity_id)
        if identity_def is None:
            continue
        _RUNTIME_IDENTITY_CACHE[identity_id] = copy.deepcopy(identity_def)
        return copy.deepcopy(identity_def)

    return None
