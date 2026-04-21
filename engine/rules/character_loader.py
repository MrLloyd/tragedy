"""惨剧轮回 — 角色数据加载器

读取 data/characters.json，提供：
- CharacterDef 角色模板
- CharacterSetup -> CharacterState 的实例化
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from engine.models.character import CharacterState
from engine.models.enums import AreaId, Attribute, Trait
from engine.models.script import CharacterSetup

_CHARACTER_DATA_FILE = Path(__file__).parent.parent.parent / "data" / "characters.json"

# 兼容历史脚本中的平民写法。
_COMMONER_ALIASES = {"平民", "commoner"}


@dataclass(frozen=True)
class CharacterDef:
    character_id: str
    name: str
    initial_area: AreaId
    forbidden_areas: list[AreaId] = field(default_factory=list)
    attributes: set[Attribute] = field(default_factory=set)
    paranoia_limit: int = 2
    base_traits: set[Trait] = field(default_factory=set)
    trait_rule: str = ""
    script_constraints: list[str] = field(default_factory=list)
    goodwill_ability_texts: list[str] = field(default_factory=list)
    goodwill_ability_goodwill_costs: list[int] = field(default_factory=list)
    goodwill_ability_once_per_loop: list[bool] = field(default_factory=list)
    initial_area_candidates: list[AreaId] = field(default_factory=list)


def normalize_identity_id(identity_id: str) -> str:
    """统一平民身份的兼容输入。"""
    if identity_id in _COMMONER_ALIASES:
        return "平民"
    return identity_id


def load_character_defs(path: Path | None = None) -> dict[str, CharacterDef]:
    """
    加载角色模板定义。

    Args:
        path: characters.json 路径，默认使用仓库 data/characters.json

    Returns:
        以 character_id 为键的 CharacterDef 字典
    """
    target = path or _CHARACTER_DATA_FILE
    if not target.exists():
        raise FileNotFoundError(f"Character file not found: {target}")

    with target.open(encoding="utf-8") as f:
        raw = json.load(f)

    items = raw.get("characters")
    if not isinstance(items, list):
        raise ValueError(f"Invalid characters payload in {target}: missing 'characters' array")

    defs: dict[str, CharacterDef] = {}
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid characters[{idx}] in {target}: expected object")
        char_def = _parse_character_def(item)
        defs[char_def.character_id] = char_def
    return defs


def instantiate_character_state(
    setup: CharacterSetup,
    defs: dict[str, CharacterDef],
) -> CharacterState:
    """
    将 CharacterSetup 实例化为 CharacterState。

    仅负责角色基础状态；事件当事人等信息仍由 Script/IncidentSchedule 表达。
    """
    char_def = defs.get(setup.character_id)
    if char_def is None:
        raise ValueError(f"Unknown character_id in setup: {setup.character_id}")

    identity_id = normalize_identity_id(setup.identity_id)
    return CharacterState(
        character_id=char_def.character_id,
        name=char_def.name,
        area=char_def.initial_area,
        initial_area=char_def.initial_area,
        identity_id=identity_id,
        original_identity_id=identity_id,
        base_traits=set(char_def.base_traits),
        attributes=set(char_def.attributes),
        paranoia_limit=char_def.paranoia_limit,
        forbidden_areas=list(char_def.forbidden_areas),
        goodwill_ability_texts=list(char_def.goodwill_ability_texts),
        goodwill_ability_goodwill_costs=list(char_def.goodwill_ability_goodwill_costs),
        goodwill_ability_once_per_loop=list(char_def.goodwill_ability_once_per_loop),
    )


def _parse_character_def(data: dict[str, object]) -> CharacterDef:
    character_id = str(data["character_id"])
    name = str(data["name"])
    initial_area = AreaId(str(data["initial_area"]))

    forbidden_areas = [
        AreaId(str(v))
        for v in data.get("forbidden_areas", [])
    ]
    attributes = {
        Attribute(str(v))
        for v in data.get("attributes", [])
    }
    base_traits = {
        Trait(str(v))
        for v in data.get("base_traits", [])
    }
    initial_area_candidates = [
        AreaId(str(v))
        for v in data.get("initial_area_candidates", [])
    ]

    paranoia_limit = int(data.get("paranoia_limit", 2))
    trait_rule = str(data.get("trait_rule", ""))
    script_constraints = [str(v) for v in data.get("script_constraints", [])]

    goodwill_texts = [str(v) for v in data.get("goodwill_ability_texts", [])]
    goodwill_costs = [int(v) for v in data.get("goodwill_ability_goodwill_costs", [])]
    goodwill_once = [bool(v) for v in data.get("goodwill_ability_once_per_loop", [])]

    return CharacterDef(
        character_id=character_id,
        name=name,
        initial_area=initial_area,
        forbidden_areas=forbidden_areas,
        attributes=attributes,
        paranoia_limit=paranoia_limit,
        base_traits=base_traits,
        trait_rule=trait_rule,
        script_constraints=script_constraints,
        goodwill_ability_texts=goodwill_texts,
        goodwill_ability_goodwill_costs=goodwill_costs,
        goodwill_ability_once_per_loop=goodwill_once,
        initial_area_candidates=initial_area_candidates,
    )
