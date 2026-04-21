"""Phase 4 P4-0: character_loader 与测试导入实例链路。"""

from __future__ import annotations

import pytest

from engine.models.enums import AreaId, Attribute
from engine.models.incident import IncidentSchedule
from engine.models.script import CharacterSetup
from engine.rules.character_loader import (
    instantiate_character_state,
    load_character_defs,
)
from engine.rules.module_loader import build_game_state_from_module


def test_load_character_defs_reads_character_templates() -> None:
    defs = load_character_defs()
    assert "ai" in defs

    ai = defs["ai"]
    assert ai.name == "AI"
    assert ai.initial_area == AreaId.CITY
    assert ai.paranoia_limit == 4
    assert len(ai.goodwill_ability_texts) == 4
    assert len(ai.goodwill_ability_goodwill_costs) == 4
    assert len(ai.goodwill_ability_once_per_loop) == 2


def test_instantiate_character_state_applies_template_and_identity_alias() -> None:
    defs = load_character_defs()
    setup = CharacterSetup(character_id="ai", identity_id="commoner")
    state = instantiate_character_state(setup, defs)

    assert state.character_id == "ai"
    assert state.identity_id == "平民"
    assert state.original_identity_id == "平民"
    assert state.paranoia_limit == 4
    assert Attribute.CREATION in state.attributes
    assert len(state.goodwill_ability_texts) == 4
    assert len(state.goodwill_ability_goodwill_costs) == 4
    assert len(state.goodwill_ability_once_per_loop) == 2


def test_build_game_state_from_module_supports_test_instance_import() -> None:
    setups = [
        CharacterSetup(character_id="ai", identity_id="killer"),
        CharacterSetup(character_id="streamer", identity_id="平民"),
    ]
    incidents = [
        IncidentSchedule(
            incident_id="murder",
            day=1,
            perpetrator_id="ai",
        )
    ]

    state = build_game_state_from_module(
        "first_steps",
        loop_count=1,
        days_per_loop=2,
        character_setups=setups,
        incidents=incidents,
        rule_y_id="fs_murder_plan",
        rule_x_ids=["fs_ripper_shadow"],
        skip_script_validation=True,
    )

    assert state.script.loop_count == 1
    assert state.script.days_per_loop == 2
    assert state.script.rule_y is not None
    assert state.script.rule_y.rule_id == "fs_murder_plan"
    assert len(state.script.rules_x) == 1
    assert state.script.rules_x[0].rule_id == "fs_ripper_shadow"

    assert set(state.characters.keys()) == {"ai", "streamer"}
    assert state.characters["ai"].identity_id == "killer"
    assert state.characters["ai"].paranoia_limit == 4
    assert state.characters["ai"].initial_area == AreaId.CITY
    assert Attribute.CREATION in state.characters["ai"].attributes

    assert len(state.script.incidents) == 1
    assert state.script.incidents[0].incident_id == "murder"
    assert len(state.script.incident_public) == 1
    assert state.script.incident_public[0]["name"] == "谋杀"
    assert state.script.incident_public[0]["day"] == 1


def test_build_game_state_from_module_rejects_unknown_identity() -> None:
    setups = [CharacterSetup(character_id="ai", identity_id="unknown_identity")]
    with pytest.raises(ValueError, match="Unknown identity_id"):
        build_game_state_from_module(
            "first_steps",
            character_setups=setups,
        )
