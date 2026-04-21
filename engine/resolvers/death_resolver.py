"""惨剧轮回 — 死亡处理链

责任链模式，依次检查：
  1. 护卫指示物（消耗 1 枚代替死亡）
  2. 不死特性（阻止死亡）
  3. 实际死亡（标记死亡，收集身份触发）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from engine.models.enums import DeathResult, TokenType, Trait
from engine.rules.runtime_identities import sync_character_identity

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.models.character import CharacterState


class DeathResolver:
    """
    处理角色死亡判定。

    调用 process_death() 后返回 DeathResult，
    实际的死亡触发（如关键人物→主人公失败）由 AtomicResolver 的触发阶段处理。
    """

    def process_death(self, character: CharacterState,
                      state: GameState) -> DeathResult:
        """
        尝试杀死一个角色，返回结果。

        Args:
            character: 目标角色
            state: 游戏状态（可能需要全局信息）
        """
        if not character.is_alive:
            return DeathResult.PREVENTED_BY_GUARD  # 已经是尸体，忽略


         # ---- 层 1：不死特性 ----
        active_traits = self._get_active_traits(character, state)
        if Trait.IMMORTAL in active_traits:
            return DeathResult.PREVENTED_BY_IMMORTAL


        # ---- 层 2：护卫指示物 ----
        if character.tokens.guard > 0:
            character.tokens.remove(TokenType.GUARD, 1)
            return DeathResult.PREVENTED_BY_GUARD

       

        # ---- 层 3：实际死亡 ----
        character.is_alive = False
        return DeathResult.DIED

    def _get_active_traits(self, character: CharacterState,
                           state: GameState) -> set[Trait]:
        """
        获取角色当前生效的特性。

        包含基础特性 + 运行时派生特性（如不安定因子的条件特性、
        纸老虎的条件转换等）。
        """
        sync_character_identity(state, character)
        traits = set(character.base_traits)
        identity_def = state.identity_defs.get(character.identity_id)
        if identity_def is not None:
            traits.update(identity_def.traits)

        # 纸老虎（HSA）：2+ 不安 → 失去不死，获得必定无视友好
        # 此处预留，具体模组注册时补充

        return traits
