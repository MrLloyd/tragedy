"""测试 IncidentHandler 的触发判定与效果执行逻辑"""

from __future__ import annotations

from engine.event_bus import EventBus, GameEventType
from engine.game_state import GameState
from engine.models.character import CharacterState
from engine.models.enums import AreaId, EffectType, TokenType
from engine.models.identity import Effect
from engine.models.incident import IncidentDef, IncidentSchedule
from engine.phases.phase_base import ForceLoopEnd, IncidentHandler, PhaseComplete
from engine.resolvers.atomic_resolver import AtomicResolver
from engine.resolvers.death_resolver import DeathResolver


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_handler() -> tuple[IncidentHandler, EventBus]:
    bus = EventBus()
    resolver = AtomicResolver(bus, DeathResolver())
    handler = IncidentHandler(bus, resolver)
    return handler, bus


def _make_state_with_incident(
    *,
    paranoia: int = 0,
    paranoia_limit: int = 2,
    day: int = 1,
    incident_id: str = "test_incident",
    perpetrator_id: str = "perp",
    is_alive: bool = True,
    incident_def: IncidentDef | None = None,
) -> GameState:
    """构造一个含单条事件日程的最小游戏状态"""
    state = GameState.create_minimal_test_state(days_per_loop=3)
    state.current_day = day

    # 当事人角色
    state.characters[perpetrator_id] = CharacterState(
        character_id=perpetrator_id,
        name="当事人",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="平民",
        original_identity_id="平民",
        paranoia_limit=paranoia_limit,
    )
    state.characters[perpetrator_id].is_alive = is_alive
    state.characters[perpetrator_id].tokens.paranoia = paranoia

    # 事件日程
    state.script.incidents = [
        IncidentSchedule(
            incident_id=incident_id,
            day=day,
            perpetrator_id=perpetrator_id,
        )
    ]

    # 注入 IncidentDef（可选）
    if incident_def is not None:
        state.incident_defs[incident_id] = incident_def

    return state


# ---------------------------------------------------------------------------
# 测试 1：不安不足，不触发
# ---------------------------------------------------------------------------

def test_incident_does_not_trigger_when_paranoia_below_limit() -> None:
    handler, bus = _make_handler()
    state = _make_state_with_incident(paranoia=1, paranoia_limit=2)

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert not state.script.incidents[0].occurred
    assert state.incidents_occurred_this_loop == []


# ---------------------------------------------------------------------------
# 测试 2：当事人已死亡，不触发
# ---------------------------------------------------------------------------

def test_incident_does_not_trigger_when_perpetrator_dead() -> None:
    handler, bus = _make_handler()
    state = _make_state_with_incident(paranoia=5, paranoia_limit=2, is_alive=False)

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert not state.script.incidents[0].occurred


# ---------------------------------------------------------------------------
# 测试 3：满足条件，触发标记与事件发出
# ---------------------------------------------------------------------------

def test_incident_triggers_and_marks_occurred() -> None:
    handler, bus = _make_handler()

    emitted: list = []
    bus.subscribe(GameEventType.INCIDENT_OCCURRED, emitted.append)

    state = _make_state_with_incident(paranoia=2, paranoia_limit=2)

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.script.incidents[0].occurred
    assert "test_incident" in state.incidents_occurred_this_loop
    assert len(emitted) == 1
    assert emitted[0].data["incident_id"] == "test_incident"
    assert emitted[0].data["perpetrator_id"] == "perp"


# ---------------------------------------------------------------------------
# 测试 4：无 incident_defs 时安全降级
# ---------------------------------------------------------------------------

def test_incident_triggers_without_defs_no_crash() -> None:
    """incident_defs 为空时：触发标记正常，不执行效果，不崩溃"""
    handler, bus = _make_handler()
    state = _make_state_with_incident(paranoia=3, paranoia_limit=2, incident_def=None)

    signal = handler.execute(state)

    assert isinstance(signal, PhaseComplete)
    assert state.script.incidents[0].occurred
    assert "test_incident" in state.incidents_occurred_this_loop


# ---------------------------------------------------------------------------
# 测试 5：事件效果产生主人公死亡 → ForceLoopEnd
# ---------------------------------------------------------------------------

def test_incident_protagonist_death_returns_force_loop_end() -> None:
    death_effect = Effect(effect_type=EffectType.PROTAGONIST_DEATH, value="incident")
    incident_def = IncidentDef(
        incident_id="fatal_incident",
        name="致命事件",
        module="test",
        effects=[death_effect],
        sequential=False,
        extra_condition=None,
        is_crowd_event=False,
        required_corpse_count=0,
        modifies_paranoia_limit=0,
        no_ex_gauge_increment=False,
        ex_gauge_increment=0,
        description="",
    )

    handler, bus = _make_handler()
    state = _make_state_with_incident(
        paranoia=3,
        paranoia_limit=2,
        incident_id="fatal_incident",
        incident_def=incident_def,
    )

    signal = handler.execute(state)

    assert isinstance(signal, ForceLoopEnd)
    assert signal.reason == "fatal_incident"


# ---------------------------------------------------------------------------
# 测试 6：same_area_all 目标 — 杀死同区域全部存活角色
# ---------------------------------------------------------------------------

def test_incident_same_area_all_kills_all_in_area() -> None:
    kill_all = Effect(effect_type=EffectType.KILL_CHARACTER, target="same_area_all")
    incident_def = IncidentDef(
        incident_id="mass_incident",
        name="群体事件",
        module="test",
        effects=[kill_all],
        sequential=False,
        extra_condition=None,
        is_crowd_event=False,
        required_corpse_count=0,
        modifies_paranoia_limit=0,
        no_ex_gauge_increment=False,
        ex_gauge_increment=0,
        description="",
    )

    handler, bus = _make_handler()
    state = _make_state_with_incident(
        paranoia=3,
        paranoia_limit=2,
        incident_id="mass_incident",
        incident_def=incident_def,
    )

    # 在当事人同区域再加一个角色
    state.characters["victim"] = CharacterState(
        character_id="victim",
        name="受害者",
        area=AreaId.HOSPITAL,
        initial_area=AreaId.HOSPITAL,
        identity_id="平民",
        original_identity_id="平民",
    )

    handler.execute(state)

    # 当事人和受害者都应死亡
    assert not state.characters["perp"].is_alive
    assert not state.characters["victim"].is_alive
