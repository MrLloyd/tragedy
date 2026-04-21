"""受控调试入口（P4-9）。"""

from engine.debug.api import (
    DebugAbilityResult,
    DebugCharacterSetup,
    DebugIncidentResult,
    DebugSession,
    DebugSetup,
    apply_debug_setup,
    build_debug_state,
    get_debug_snapshot,
    list_debug_abilities,
    trigger_debug_ability,
    trigger_debug_incident,
)

__all__ = [
    "DebugAbilityResult",
    "DebugCharacterSetup",
    "DebugIncidentResult",
    "DebugSession",
    "DebugSetup",
    "apply_debug_setup",
    "build_debug_state",
    "get_debug_snapshot",
    "list_debug_abilities",
    "trigger_debug_ability",
    "trigger_debug_incident",
]
