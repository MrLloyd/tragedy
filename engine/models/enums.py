"""惨剧轮回 — 全局枚举定义"""

from enum import Enum, auto


# ---------------------------------------------------------------------------
# 游戏阶段（状态机节点）
# ---------------------------------------------------------------------------
class GamePhase(Enum):
    """状态机的 15 个节点 + NEXT_LOOP 中转"""

    GAME_PREPARE = "game_prepare"
    LOOP_START = "loop_start"
    TURN_START = "turn_start"
    MASTERMIND_ACTION = "mastermind_action"
    PROTAGONIST_ACTION = "protagonist_action"
    ACTION_RESOLVE = "action_resolve"
    PLAYWRIGHT_ABILITY = "playwright_ability"
    PROTAGONIST_ABILITY = "protagonist_ability"
    INCIDENT = "incident"
    LEADER_ROTATE = "leader_rotate"
    TURN_END = "turn_end"
    LOOP_END = "loop_end"
    LOOP_END_CHECK = "loop_end_check"
    NEXT_LOOP = "next_loop"
    FINAL_GUESS = "final_guess"
    GAME_END = "game_end"


# ---------------------------------------------------------------------------
# 指示物类型
# ---------------------------------------------------------------------------
class TokenType(Enum):
    PARANOIA = "paranoia"    # 不安
    INTRIGUE = "intrigue"    # 密谋
    GOODWILL = "goodwill"    # 友好
    HOPE = "hope"            # 希望（WM/AHR/LL）
    DESPAIR = "despair"      # 绝望（WM/AHR/LL）
    GUARD = "guard"          # 护卫（刑警能力）


# ---------------------------------------------------------------------------
# 版图区域
# ---------------------------------------------------------------------------
class AreaId(Enum):
    HOSPITAL = "hospital"    # 医院
    SCHOOL = "school"        # 学校
    SHRINE = "shrine"        # 神社
    CITY = "city"            # 都市
    FARAWAY = "faraway"      # 远方（非版图）


# ---------------------------------------------------------------------------
# 玩家角色
# ---------------------------------------------------------------------------
class PlayerRole(Enum):
    MASTERMIND = "mastermind"          # 剧作家
    PROTAGONIST_0 = "protagonist_0"    # 主人公 1（初始队长）
    PROTAGONIST_1 = "protagonist_1"    # 主人公 2
    PROTAGONIST_2 = "protagonist_2"    # 主人公 3


# ---------------------------------------------------------------------------
# 能力触发窗口
# ---------------------------------------------------------------------------
class AbilityTiming(Enum):
    """能力声明/结算所在的阶段"""
    SCRIPT_CREATION = "script_creation"          # 剧本制作时
    LOOP_START = "loop_start"                    # 轮回开始时
    TURN_START = "turn_start"                    # 回合开始
    ACTION_RESOLVE = "action_resolve"            # 行动结算阶段
    PLAYWRIGHT_ABILITY = "playwright_ability"    # 剧作家能力阶段
    PROTAGONIST_ABILITY = "protagonist_ability"  # 主人公能力阶段
    INCIDENT = "incident"                        # 事件阶段
    TURN_END = "turn_end"                        # 回合结束阶段
    FINAL_DAY_TURN_END = "final_day_turn_end"    # 最终日回合结束
    ON_DEATH = "on_death"                        # 该角色死亡时
    ON_OTHER_DEATH = "on_other_death"            # 其他指定角色死亡时
    LOOP_END = "loop_end"                        # 轮回结束时
    ALWAYS = "always"                            # 常驻
    AFTER_GOODWILL_ABILITY = "after_goodwill_ability"  # 结算友好能力后（AHR）


# ---------------------------------------------------------------------------
# 能力类型
# ---------------------------------------------------------------------------
class AbilityType(Enum):
    MANDATORY = "mandatory"   # 强制：条件满足必须执行
    OPTIONAL = "optional"     # 任意：拥有方选择是否执行
    LOSS_CONDITION = "loss_condition"  # 失败条件（轮回结束时判定）


# ---------------------------------------------------------------------------
# 效果类型（Effect 原语，全模组通用）
# ---------------------------------------------------------------------------
class EffectType(Enum):
    # 指示物操作
    PLACE_TOKEN = "place_token"            # 放置指示物
    REMOVE_TOKEN = "remove_token"          # 移除指示物
    MOVE_TOKEN = "move_token"              # 移动指示物（两角色间）
    REMOVE_ALL_TOKENS = "remove_all_tokens"  # 移除所有某类指示物

    # 角色操作
    KILL_CHARACTER = "kill_character"       # 角色死亡
    REVIVE_CHARACTER = "revive_character"   # 复活角色
    MOVE_CHARACTER = "move_character"       # 移动角色
    REMOVE_CHARACTER = "remove_character"   # 从游戏中移除角色

    # 终局效果
    PROTAGONIST_DEATH = "protagonist_death"      # 主人公死亡
    PROTAGONIST_FAILURE = "protagonist_failure"   # 主人公失败
    FORCE_LOOP_END = "force_loop_end"            # 强制结束本轮回

    # 信息操作
    REVEAL_IDENTITY = "reveal_identity"    # 公开身份
    REVEAL_INCIDENT = "reveal_incident"    # 公开事件当事人

    # 卡牌操作
    NULLIFY_CARD = "nullify_card"          # 无效化行动牌
    RETURN_CARD = "return_card"            # 回收行动牌

    # 选择（挂起引擎等待输入）
    CHOOSE_TARGET = "choose_target"        # 选择目标（角色/版图）

    # EX 相关（预留）
    MODIFY_EX_GAUGE = "modify_ex_gauge"    # 修改 EX 槽
    PLACE_EX_CARD = "place_ex_card"        # 放置 EX 牌
    REMOVE_EX_CARD = "remove_ex_card"      # 移除 EX 牌

    # 世界线（AHR 预留）
    WORLD_MOVE = "world_move"              # 世界移动

    # 身份变更
    CHANGE_IDENTITY = "change_identity"    # 身份变更（妄想扩大病毒等）

    # 无效果
    NO_EFFECT = "no_effect"                # 事件发生但无现象


# ---------------------------------------------------------------------------
# 角色特性
# ---------------------------------------------------------------------------
class Trait(Enum):
    IGNORE_GOODWILL = "ignore_goodwill"                  # 无视友好
    MUST_IGNORE_GOODWILL = "must_ignore_goodwill"        # 必定无视友好
    PUPPET_IGNORE_GOODWILL = "puppet_ignore_goodwill"    # 傀儡无视友好（AHR）
    IMMORTAL = "immortal"                                # 不死
    NO_ACTION_CARDS = "no_action_cards"                  # 不可放置行动牌


# ---------------------------------------------------------------------------
# 角色属性标签
# ---------------------------------------------------------------------------
class Attribute(Enum):
    STUDENT = "student"      # 学生
    ADULT = "adult"          # 成人
    BOY = "boy"              # 少年
    GIRL = "girl"            # 少女
    MALE = "male"            # 男性
    FEMALE = "female"        # 女性
    ANIMAL = "animal"        # 动物
    PLANT = "plant"          # 植物
    VIRTUAL = "virtual"      # 虚构
    CREATION = "creation"    # 造物
    SISTER = "sister"        # 妹妹（特殊属性）


# ---------------------------------------------------------------------------
# 行动牌类型
# ---------------------------------------------------------------------------
class CardType(Enum):
    # 剧作家
    INTRIGUE_PLUS_2 = "intrigue_plus_2"
    INTRIGUE_PLUS_1 = "intrigue_plus_1"
    PARANOIA_PLUS_1 = "paranoia_plus_1"
    PARANOIA_MINUS_1 = "paranoia_minus_1"
    MOVE_HORIZONTAL = "move_horizontal"
    MOVE_VERTICAL = "move_vertical"
    MOVE_DIAGONAL = "move_diagonal"
    FORBID_GOODWILL = "forbid_goodwill"
    FORBID_PARANOIA = "forbid_paranoia"

    # 剧作家扩展（AHR/LL）
    DESPAIR_PLUS_1 = "despair_plus_1"
    GOODWILL_PLUS_1_MM = "goodwill_plus_1_mm"  # 剧作家用友好+1（AHR）

    # 主人公
    GOODWILL_PLUS_1 = "goodwill_plus_1"
    GOODWILL_PLUS_2 = "goodwill_plus_2"
    PARANOIA_PLUS_1_P = "paranoia_plus_1_p"     # 主人公用不安+1
    PARANOIA_MINUS_1_P = "paranoia_minus_1_p"   # 主人公用不安-1
    MOVE_HORIZONTAL_P = "move_horizontal_p"
    MOVE_VERTICAL_P = "move_vertical_p"
    FORBID_INTRIGUE = "forbid_intrigue"
    FORBID_MOVEMENT = "forbid_movement"

    # 主人公扩展（AHR/LL）
    HOPE_PLUS_1 = "hope_plus_1"
    PARANOIA_PLUS_2_P = "paranoia_plus_2_p"     # 主人公用不安+2（AHR）


# ---------------------------------------------------------------------------
# 阶段处理器返回信号
# ---------------------------------------------------------------------------
class PhaseResult(Enum):
    COMPLETE = auto()        # 阶段完成，推进
    WAIT_FOR_INPUT = auto()  # 等待玩家输入
    FORCE_LOOP_END = auto()  # 强制结束轮回


# ---------------------------------------------------------------------------
# 终局结果
# ---------------------------------------------------------------------------
class Outcome(Enum):
    NONE = "none"                              # 无终局效果
    PROTAGONIST_DEATH = "protagonist_death"     # 主人公死亡
    PROTAGONIST_FAILURE = "protagonist_failure"  # 主人公失败
    PROTAGONIST_WIN = "protagonist_win"         # 主人公胜利
    MASTERMIND_WIN = "mastermind_win"           # 剧作家胜利


# ---------------------------------------------------------------------------
# 死亡处理结果
# ---------------------------------------------------------------------------
class DeathResult(Enum):
    DIED = "died"                  # 实际死亡
    PREVENTED_BY_GUARD = "guard"   # 护卫指示物代替
    PREVENTED_BY_IMMORTAL = "immortal"  # 不死特性阻止
    PREVENTED_BY_SOLDIER = "soldier"    # 军人能力阻止（仅主人公死亡）
