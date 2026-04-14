"""惨剧轮回 — 阶段处理器基类与返回信号"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.models.cards import CardPlacement
from engine.models.enums import GamePhase, PlayerRole

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.event_bus import EventBus
    from engine.resolvers.atomic_resolver import AtomicResolver


# ---------------------------------------------------------------------------
# 阶段返回信号
# ---------------------------------------------------------------------------
@dataclass
class PhaseComplete:
    """阶段完成，状态机可推进"""
    pass


@dataclass
class WaitForInput:
    """
    等待玩家输入。

    引擎挂起，UI 展示选项，玩家操作后调用 callback(choice) 继续。
    """
    input_type: str              # 输入类型标识
    prompt: str = ""             # 提示文本
    options: list[Any] = field(default_factory=list)
    player: str = "mastermind"   # 谁需要输入
    callback: Optional[Callable] = None


@dataclass
class ForceLoopEnd:
    """强制结束本轮回"""
    reason: str = ""


# 阶段返回类型
PhaseSignal = PhaseComplete | WaitForInput | ForceLoopEnd


# ---------------------------------------------------------------------------
# PhaseHandler — 阶段处理器基类
# ---------------------------------------------------------------------------
class PhaseHandler(ABC):
    """
    每个游戏阶段对应一个 PhaseHandler 子类。

    execute() 返回 PhaseSignal：
      - PhaseComplete → 自动推进
      - WaitForInput  → 挂起等待
      - ForceLoopEnd  → 跳到 loop_end
    """

    phase: GamePhase  # 子类必须声明

    def __init__(self, event_bus: EventBus,
                 atomic_resolver: AtomicResolver) -> None:
        self.event_bus = event_bus
        self.atomic_resolver = atomic_resolver

    @abstractmethod
    def execute(self, state: GameState) -> PhaseSignal:
        """执行本阶段逻辑"""
        ...


# ---------------------------------------------------------------------------
# 具体阶段处理器（框架实现，后续逐步填充业务逻辑）
# ---------------------------------------------------------------------------
class GamePrepareHandler(PhaseHandler):
    phase = GamePhase.GAME_PREPARE

    def execute(self, state: GameState) -> PhaseSignal:
        # 游戏准备：确认剧本已加载，初始化手牌等
        state.init_protagonist_hands()
        return PhaseComplete()


class LoopStartHandler(PhaseHandler):
    phase = GamePhase.LOOP_START

    def execute(self, state: GameState) -> PhaseSignal:
        # 轮回开始：时之裂隙讨论、跨轮回效果结算
        # TODO: 结算因果线、亲友身份公开效果等
        return PhaseComplete()


class TurnStartHandler(PhaseHandler):
    phase = GamePhase.TURN_START

    def execute(self, state: GameState) -> PhaseSignal:
        # 回合开始：结算回合开始触发效果
        return PhaseComplete()


class MastermindActionHandler(PhaseHandler):
    phase = GamePhase.MASTERMIND_ACTION

    def execute(self, state: GameState) -> PhaseSignal:
        # 剧作家暗置 3 张行动牌
        available = state.mastermind_hand.get_available()

        def _on_choice(choice: Any) -> PhaseSignal:
            # 最小闭环：允许 UI 一次提交 1~3 张牌，合法后标记为已使用并记录放置。
            selected = choice if isinstance(choice, list) else [choice]
            if not selected or len(selected) > 3:
                raise ValueError("mastermind must choose 1 to 3 cards")

            for card in selected:
                if card not in available:
                    raise ValueError("selected card is not available in mastermind hand")
                card.is_used_this_loop = True
                state.placed_cards.append(
                    CardPlacement(
                        card=card,
                        owner=PlayerRole.MASTERMIND,
                        target_type="board",
                        target_id="school",
                        face_down=True,
                    )
                )
            return PhaseComplete()

        return WaitForInput(
            input_type="place_action_cards",
            prompt="剧作家请放置 3 张行动牌",
            options=available,
            player="mastermind",
            callback=_on_choice,
        )


class ProtagonistActionHandler(PhaseHandler):
    phase = GamePhase.PROTAGONIST_ACTION

    def execute(self, state: GameState) -> PhaseSignal:
        # 主人公按队长起顺时针依次放牌
        leader = state.leader_index
        hand = state.protagonist_hands[leader]
        available = hand.get_available()

        def _on_choice(choice: Any) -> PhaseSignal:
            if choice not in available:
                raise ValueError("selected card is not available in protagonist hand")
            choice.is_used_this_loop = True
            state.placed_cards.append(
                CardPlacement(
                    card=choice,
                    owner=hand.owner,
                    target_type="board",
                    target_id="school",
                    face_down=True,
                )
            )
            return PhaseComplete()

        return WaitForInput(
            input_type="place_action_card",
            prompt=f"主人公 {leader + 1}（队长）请放置 1 张行动牌",
            options=available,
            player=f"protagonist_{leader}",
            callback=_on_choice,
        )


class ActionResolveHandler(PhaseHandler):
    phase = GamePhase.ACTION_RESOLVE

    def execute(self, state: GameState) -> PhaseSignal:
        # 翻开所有行动牌，先移动后其他
        # TODO: 实现 action_resolver 调用
        return PhaseComplete()


class PlaywrightAbilityHandler(PhaseHandler):
    phase = GamePhase.PLAYWRIGHT_ABILITY

    def execute(self, state: GameState) -> PhaseSignal:
        # 先同步结算全部强制能力，再由剧作家逐个声明任意能力
        # TODO: 收集可用能力，等待剧作家选择
        return PhaseComplete()


class ProtagonistAbilityHandler(PhaseHandler):
    phase = GamePhase.PROTAGONIST_ABILITY

    def execute(self, state: GameState) -> PhaseSignal:
        # 队长声明友好能力，剧作家可拒绝
        # TODO: 收集可声明能力，等待队长选择
        return PhaseComplete()


class IncidentHandler(PhaseHandler):
    phase = GamePhase.INCIDENT

    def execute(self, state: GameState) -> PhaseSignal:
        # 判定当日事件是否发生，执行效果
        # TODO: 实现 incident_resolver 调用
        return PhaseComplete()


class LeaderRotateHandler(PhaseHandler):
    phase = GamePhase.LEADER_ROTATE

    def execute(self, state: GameState) -> PhaseSignal:
        state.rotate_leader()
        return PhaseComplete()


class TurnEndHandler(PhaseHandler):
    phase = GamePhase.TURN_END

    def execute(self, state: GameState) -> PhaseSignal:
        # 1. EX 槽更新（预留）
        # 2. 全部强制能力同步结算（杀人狂等）
        # 3. 剧作家逐个声明任意能力（杀手、求爱者等）
        # TODO: 实现 turn_end 能力结算
        return PhaseComplete()


class LoopEndHandler(PhaseHandler):
    phase = GamePhase.LOOP_END

    def execute(self, state: GameState) -> PhaseSignal:
        # 结算"轮回结束时"效果，保存 LoopSnapshot
        state.save_loop_snapshot()
        return PhaseComplete()


class LoopEndCheckHandler(PhaseHandler):
    phase = GamePhase.LOOP_END_CHECK

    def execute(self, state: GameState) -> PhaseSignal:
        # 判定分流（由 StateMachine 处理，此处仅做失败条件收集）
        # TODO: 检查规则 Y / 规则 X 的失败条件
        return PhaseComplete()


class FinalGuessHandler(PhaseHandler):
    phase = GamePhase.FINAL_GUESS

    def execute(self, state: GameState) -> PhaseSignal:
        # 最终决战：主人公推理身份
        def _on_choice(_: Any) -> PhaseSignal:
            # Phase 1 最小闭环：接收输入即可继续推进，具体判定后续实现。
            return PhaseComplete()

        return WaitForInput(
            input_type="final_guess",
            prompt="最终决战：请推理所有角色身份与规则",
            player="protagonists",
            callback=_on_choice,
        )


# ---------------------------------------------------------------------------
# 阶段处理器注册表
# ---------------------------------------------------------------------------
def create_phase_handlers(event_bus: EventBus,
                          atomic_resolver: AtomicResolver
                          ) -> dict[GamePhase, PhaseHandler]:
    """创建所有阶段处理器的映射"""
    handlers: list[type[PhaseHandler]] = [
        GamePrepareHandler,
        LoopStartHandler,
        TurnStartHandler,
        MastermindActionHandler,
        ProtagonistActionHandler,
        ActionResolveHandler,
        PlaywrightAbilityHandler,
        ProtagonistAbilityHandler,
        IncidentHandler,
        LeaderRotateHandler,
        TurnEndHandler,
        LoopEndHandler,
        LoopEndCheckHandler,
        FinalGuessHandler,
    ]
    return {
        cls.phase: cls(event_bus, atomic_resolver)
        for cls in handlers
    }
