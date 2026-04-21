"""校验共用类型与枚举辅助。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeVar

E = TypeVar("E", bound=Enum)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """单条校验问题：path 为逻辑路径（含文件名前缀），便于定位。"""

    path: str
    message: str


def enum_values(enum_cls: type[E]) -> frozenset[str]:
    return frozenset(e.value for e in enum_cls)


# 与 engine.models.identity.Condition 文档对齐
KNOWN_CONDITION_TYPES = frozenset(
    {
        "all_of",
        "any_of",
        "token_check",
        "identity_token_check",
        "same_area_identity_token_check",
        "same_area_count",
        "character_alive",
        "character_dead",
        "is_final_day",
        "identity_is",
        "other_identity_is",
        "identity_revealed",
        "ex_gauge_check",
        "has_trait",
        "area_is",
        "world_line_check",
        "loop_number_check",
        "incident_occurred",
    }
)
