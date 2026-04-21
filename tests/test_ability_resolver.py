"""Phase 4: AbilityResolver 基础行为测试。"""

from __future__ import annotations

from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.ability import Ability
from engine.models.enums import AbilityTiming, AbilityType, AreaId, Attribute, TokenType, Trait
from engine.models.effects import Condition
from engine.models.identity import IdentityDef
from engine.resolvers.ability_resolver import AbilityResolver
from engine.rules.module_loader import apply_loaded_module, load_module


def _build_state_with_module() -> GameState:
    state = GameState()
    loaded = load_module("first_steps")
    apply_loaded_module(state, loaded)
    return state


def test_collect_identity_abilities_by_timing() -> None:
    state = _build_state_with_module()
    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物角色",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="key_person",
        original_identity_id="key_person",
    )

    resolver = AbilityResolver()
    abilities = resolver.collect_identity_abilities(
        state,
        timing=AbilityTiming.ON_DEATH,
        alive_only=False,
    )

    assert len(abilities) == 1
    assert abilities[0].source_kind == "identity"
    assert abilities[0].source_id == "key"
    assert abilities[0].ability.ability_id == "key_person_on_death"

    compat = resolver.collect_character_abilities(
        state,
        timing=AbilityTiming.ON_DEATH,
        alive_only=False,
    )
    assert len(compat) == 1
    assert compat[0].ability.ability_id == "key_person_on_death"


def test_collect_rule_abilities_and_condition_eval() -> None:
    state = _build_state_with_module()
    state.script.rules_x = list(state.module_def.rules_x) if state.module_def else []
    state.board.areas[AreaId.SCHOOL].tokens.add(TokenType.INTRIGUE, 2)

    resolver = AbilityResolver()
    abilities = resolver.collect_rule_abilities(
        state,
        timing=AbilityTiming.LOOP_END,
        ability_type=AbilityType.LOSS_CONDITION,
    )

    assert len(abilities) == 1
    assert abilities[0].source_kind == "rule"
    assert abilities[0].source_id == "fs_ripper_shadow"


def test_active_traits_and_goodwill_ignore() -> None:
    state = _build_state_with_module()
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手角色",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )

    resolver = AbilityResolver()
    traits = resolver.active_traits(state, "killer")
    assert Trait.IGNORE_GOODWILL in traits
    assert resolver.goodwill_should_be_ignored(state, "killer") is True


def test_token_check_condition_for_character_target() -> None:
    state = _build_state_with_module()
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手角色",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )
    state.characters["killer"].tokens.add(TokenType.INTRIGUE, 4)

    resolver = AbilityResolver()
    cond = Condition(
        condition_type="token_check",
        params={
            "target": "killer",
            "token": "intrigue",
            "operator": ">=",
            "value": 4,
        },
    )
    assert resolver.evaluate_condition(state, cond) is True


def test_collect_goodwill_abilities_from_character_runtime_data() -> None:
    state = _build_state_with_module()
    state.characters["ai"] = CharacterState(
        character_id="ai",
        name="AI",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
        goodwill_ability_texts=["能力1", "", "", ""],
        goodwill_ability_goodwill_costs=[3, 0, 0, 0],
        goodwill_ability_once_per_loop=[True, False],
    )
    state.characters["ai"].tokens.add(TokenType.GOODWILL, 3)

    resolver = AbilityResolver()
    abilities = resolver.collect_goodwill_abilities(state)

    assert len(abilities) == 1
    assert abilities[0].source_kind == "goodwill"
    assert abilities[0].source_id == "ai"
    assert abilities[0].ability.ability_id == "goodwill:ai:1"
    assert abilities[0].ability.goodwill_cost == 3
    assert abilities[0].ability.once_per_loop is True
    assert abilities[0].ability.can_be_refused is True

    state.ability_runtime.usages_this_loop[resolver.ability_usage_key(abilities[0])] = 1
    abilities = resolver.collect_goodwill_abilities(state)
    assert len(abilities) == 0


def test_evaluate_condition_for_attribute_and_paranoia_limit() -> None:
    state = _build_state_with_module()
    state.characters["target"] = CharacterState(
        character_id="target",
        name="目标",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
        attributes={Attribute.ADULT},
        paranoia_limit=3,
    )
    resolver = AbilityResolver()

    has_attr = Condition(
        condition_type="has_attribute",
        params={"target": "target", "attribute": "adult"},
    )
    paranoia_limit_check = Condition(
        condition_type="paranoia_limit_check",
        params={"target": "target", "operator": ">=", "value": 3},
    )

    assert resolver.evaluate_condition(state, has_attr) is True
    assert resolver.evaluate_condition(state, paranoia_limit_check) is True


def test_collect_identity_abilities_respects_unified_once_limits() -> None:
    state = _build_state_with_module()
    state.characters["x"] = CharacterState(
        character_id="x",
        name="X",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="x_identity",
        original_identity_id="x_identity",
    )
    state.identity_defs["x_identity"] = IdentityDef(
        identity_id="x_identity",
        name="X身份",
        module="test",
        abilities=[
            Ability(
                ability_id="x_once",
                name="X限次能力",
                ability_type=AbilityType.OPTIONAL,
                timing=AbilityTiming.PLAYWRIGHT_ABILITY,
                once_per_loop=True,
            )
        ],
    )

    resolver = AbilityResolver()
    abilities = resolver.collect_identity_abilities(
        state,
        timing=AbilityTiming.PLAYWRIGHT_ABILITY,
    )
    assert len(abilities) == 1
    candidate = abilities[0]
    resolver.mark_ability_used(state, candidate)

    abilities = resolver.collect_identity_abilities(
        state,
        timing=AbilityTiming.PLAYWRIGHT_ABILITY,
    )
    assert len(abilities) == 0


def test_first_steps_p4_3_identity_abilities_are_collected() -> None:
    state = _build_state_with_module()
    state.characters["killer"] = CharacterState(
        character_id="killer",
        name="杀手角色",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="killer",
        original_identity_id="killer",
    )
    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物角色",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="key_person",
        original_identity_id="key_person",
    )
    state.characters["mastermind"] = CharacterState(
        character_id="mastermind",
        name="主谋角色",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="mastermind",
        original_identity_id="mastermind",
    )
    state.characters["rumor"] = CharacterState(
        character_id="rumor",
        name="传谣人角色",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="rumormonger",
        original_identity_id="rumormonger",
    )
    state.characters["serial"] = CharacterState(
        character_id="serial",
        name="杀人狂角色",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="serial_killer",
        original_identity_id="serial_killer",
    )
    state.characters["other"] = CharacterState(
        character_id="other",
        name="其他角色",
        area=AreaId.SHRINE,
        initial_area=AreaId.SHRINE,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["key"].tokens.add(TokenType.INTRIGUE, 2)
    state.characters["killer"].tokens.add(TokenType.INTRIGUE, 4)

    resolver = AbilityResolver()

    turn_end = resolver.collect_identity_abilities(state, timing=AbilityTiming.TURN_END)
    playwright = resolver.collect_identity_abilities(state, timing=AbilityTiming.PLAYWRIGHT_ABILITY)

    assert {c.ability.ability_id for c in turn_end} == {
        "killer_turn_end_kill_key_person",
        "killer_turn_end_protagonist_death",
        "serial_killer_turn_end_kill_lone_target",
    }
    assert {c.ability.ability_id for c in playwright} == {
        "mastermind_playwright_place_intrigue_character",
        "mastermind_playwright_place_intrigue_board",
        "rumormonger_playwright_place_paranoia",
    }


def test_btx_rule_identity_and_derived_abilities_are_collected() -> None:
    state = GameState()
    loaded = load_module("basic_tragedy_x")
    apply_loaded_module(state, loaded)
    state.script.rule_y = next(rule for rule in state.module_def.rules_y if rule.rule_id == "btx_cursed_contract")
    state.script.rules_x = [next(rule for rule in state.module_def.rules_x if rule.rule_id == "btx_rumors")]
    state.characters["key"] = CharacterState(
        character_id="key",
        name="关键人物角色",
        area=AreaId.SCHOOL,
        initial_area=AreaId.SCHOOL,
        identity_id="key_person",
        original_identity_id="key_person",
    )
    state.characters["friend"] = CharacterState(
        character_id="friend",
        name="亲友角色",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="friend",
        original_identity_id="friend",
        revealed=True,
        is_alive=False,
    )
    state.characters["unstable"] = CharacterState(
        character_id="unstable",
        name="不安定因子角色",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="unstable_factor",
        original_identity_id="unstable_factor",
    )
    state.characters["key"].tokens.add(TokenType.INTRIGUE, 2)
    state.board.areas[AreaId.SCHOOL].tokens.add(TokenType.INTRIGUE, 2)
    state.board.areas[AreaId.CITY].tokens.add(TokenType.INTRIGUE, 2)

    resolver = AbilityResolver()

    rule_candidates = resolver.collect_rule_abilities(
        state,
        timing=AbilityTiming.LOOP_END,
        ability_type=AbilityType.LOSS_CONDITION,
    )
    playwright_rule = resolver.collect_rule_abilities(
        state,
        timing=AbilityTiming.PLAYWRIGHT_ABILITY,
        ability_type=AbilityType.OPTIONAL,
    )
    friend_loop_end = resolver.collect_identity_abilities(
        state,
        timing=AbilityTiming.LOOP_END,
        ability_type=AbilityType.LOSS_CONDITION,
        alive_only=False,
    )
    friend_loop_start = resolver.collect_identity_abilities(
        state,
        timing=AbilityTiming.LOOP_START,
        ability_type=AbilityType.MANDATORY,
        alive_only=False,
    )
    derived_playwright = resolver.collect_derived_abilities(
        state,
        timing=AbilityTiming.PLAYWRIGHT_ABILITY,
    )
    derived_on_death = resolver.collect_derived_abilities(
        state,
        timing=AbilityTiming.ON_DEATH,
        ability_type=AbilityType.MANDATORY,
    )

    assert {c.ability.ability_id for c in rule_candidates} == {"btx_fail_key_person_intrigue_2"}
    assert {c.ability.ability_id for c in playwright_rule} == {"btx_rumors_playwright_place_intrigue"}
    assert {c.ability.ability_id for c in friend_loop_end} == {"friend_loop_end_revealed_loss"}
    assert {c.ability.ability_id for c in friend_loop_start} == {"friend_loop_start_place_goodwill"}
    assert {c.ability.ability_id for c in derived_playwright} == {"rumormonger_playwright_place_paranoia"}
    assert {c.ability.ability_id for c in derived_on_death} == {"key_person_on_death"}


def test_resolve_targets_basic_selectors() -> None:
    state = _build_state_with_module()
    state.characters["owner"] = CharacterState(
        character_id="owner",
        name="拥有者",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["a"] = CharacterState(
        character_id="a",
        name="A",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="平民",
        original_identity_id="平民",
    )
    state.characters["b"] = CharacterState(
        character_id="b",
        name="B",
        area=AreaId.CITY,
        initial_area=AreaId.CITY,
        identity_id="平民",
        original_identity_id="平民",
    )

    resolver = AbilityResolver()
    same_area = resolver.resolve_targets(state, owner_id="owner", selector="same_area_any")
    assert set(same_area) == {"owner", "a"}
    any_board = resolver.resolve_targets(state, owner_id="owner", selector="any_board")
    assert set(any_board) == {"hospital", "school", "shrine", "city"}
    condition_target = resolver.resolve_targets(
        state,
        owner_id="owner",
        selector="condition_target",
        condition_target="b",
    )
    assert condition_target == ["b"]
