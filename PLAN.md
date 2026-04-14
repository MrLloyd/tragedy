# 惨剧轮回 电子版 - 实现计划

## Context

基于两份规则文档（`tragedy_loop_game_rules.md` + `tragedy_loop_appendix.md`），开发"惨剧轮回"桌游的电子版单机游戏。Python + PySide6（6.11.0），热座模式，先实现 First Steps + Basic Tragedy X 模组，架构预留 EX 牌/EX 槽等后续模组空间。

---

## 1. 项目目录结构

```
traged/
├── main.py
├── requirements.txt
├── data/                            # JSON 数据配置
│   ├── board.json                   # 版图 2x2 + 远方
│   ├── cards.json                   # 手牌表（剧作家+主人公+扩展）
│   ├── characters.json              # 角色表（附录C）
│   └── modules/
│       ├── first_steps.json
│       └── basic_tragedy_x.json
├── engine/                          # 核心引擎（无 UI 依赖）
│   ├── state_machine.py             # 状态机（15阶段 + 条件跳转）
│   ├── game_state.py                # 游戏状态聚合根 + 快照/恢复
│   ├── game_controller.py           # 协调状态机、结算、玩家输入
│   ├── event_bus.py                 # 事件总线（死亡/失败/轮回结束触发）
│   ├── visibility.py                # 信息边界过滤
│   ├── models/
│   │   ├── enums.py                 # GamePhase, TokenType, PlayerRole 等枚举
│   │   ├── character.py             # CharacterState, TokenSet
│   │   ├── board.py                 # BoardArea, BoardState
│   │   ├── cards.py                 # ActionCard, CardPlacement, CardHand
│   │   ├── script.py                # Script（公开/非公开信息表）
│   │   ├── incident.py              # IncidentDef, IncidentSchedule
│   │   └── identity.py              # IdentityDef, Ability, Effect
│   ├── resolvers/
│   │   ├── atomic_resolver.py       # 原子结算（读-写-触发）
│   │   ├── action_resolver.py       # 行动牌结算
│   │   ├── ability_resolver.py      # 能力结算（强制/任意/拒绝）
│   │   ├── incident_resolver.py     # 事件结算
│   │   └── death_resolver.py        # 死亡处理链
│   ├── rules/
│   │   ├── rule_base.py             # RuleY/RuleX 基类
│   │   ├── identity_registry.py     # 身份注册表
│   │   ├── incident_registry.py     # 事件注册表
│   │   └── module_loader.py         # JSON→模组实例
│   └── phases/                      # 每阶段逻辑
│       ├── phase_base.py            # 阶段基类 → PhaseComplete|WaitForInput|ForceLoopEnd
│       ├── game_prepare.py
│       ├── loop_start.py
│       ├── turn_phases.py           # turn_start ~ turn_end
│       ├── loop_end.py
│       └── final_guess.py
├── ui/                              # PySide6
│   ├── app.py
│   ├── main_window.py
│   ├── screens/
│   │   ├── title_screen.py
│   │   ├── script_setup_screen.py
│   │   ├── game_screen.py
│   │   ├── transition_screen.py
│   │   └── result_screen.py
│   ├── widgets/
│   │   ├── board_widget.py
│   │   ├── character_widget.py
│   │   ├── card_hand_widget.py
│   │   ├── phase_indicator.py
│   │   └── log_widget.py
│   └── controllers/
│       └── ui_game_controller.py
└── tests/
```

---

## 2. 开发阶段

### Phase 0（已完成）: 基础设施 + 数据
- [x] `models/enums.py` — GamePhase, TokenType, AreaId 等
- [x] `models/character.py` — TokenSet, CharacterState
- [x] `models/board.py` — BoardArea, BoardState（2x2网格+远方+相邻关系）
- [x] `models/cards.py` — ActionCard, CardHand, CardPlacement
- [x] `models/script.py` — Script（当前以 `Script` 聚合公开/非公开信息）
- [x] `models/identity.py` — IdentityDef, Ability, Effect, Condition
- [x] `models/incident.py` — IncidentDef, IncidentSchedule
- [x] `data/board.json`
- [x] `data/cards.json`（含扩展牌位：绝望+1、希望+1）
- [x] `data/characters.json`（FS+BTX 所需角色）
- [x] `data/modules/first_steps.json`
- [x] `data/modules/basic_tragedy_x.json`
- [x] 数据契约与校验：`engine/validation/`、`python -m engine.validation`、`tests/test_data_validation.py`

### Phase 1（进行中）: 状态机 + 核心引擎
- [x] `engine/state_machine.py`：实现 15 阶段主流程、条件分支与虚线跳转
- [x] `engine/game_controller.py`：实现调度主循环（phase execute → signal handle → advance）
- [x] `engine/resolvers/atomic_resolver.py`：原子结算框架（读-写-触发）骨架
- [x] `engine/resolvers/death_resolver.py`：死亡处理链基础（护卫/不死/死亡）
- [x] `engine/phases/phase_base.py`：PhaseHandler / PhaseSignal 框架
- [x] 打通 `WaitForInput` 回填闭环：`provide_input` 后稳定续跑后续阶段
- [ ] 完成最小阶段业务闭环：`ACTION_RESOLVE`、`INCIDENT`、`TURN_END`、`LOOP_END_CHECK`
- [ ] 将 `has_final_guess` 从控制器硬编码改为读取 `Script.module`/模组配置
- [ ] 接通事件触发链与身份能力触发到 `event_bus`
- [ ] 补充 Phase 1 核心测试：状态机分支、同时裁定、死亡/失败优先级、跨阶段 loop_end 跳转

#### Phase 1 实施顺序（建议）

1. **输入闭环先行（P1-0）**
   - 实现 `WaitForInput.callback` 生命周期：挂起、回填、续跑、防重复输入。
   - 先保证 “一次输入 -> 正常推进到下一阶段”。
2. **最小业务闭环（P1-1）**
   - `ACTION_RESOLVE`：先实现最小可运行结算入口（可先覆盖少量 effect）。
   - `INCIDENT`：最小事件触发判定与执行路径。
   - `TURN_END`：强制效果 -> 任意效果声明 -> 每次后检查是否应结束轮回。
   - `LOOP_END_CHECK`：三分支闭环（胜利 / NEXT_LOOP / FINAL_GUESS|GAME_END）。
3. **模组配置接线（P1-2）**
   - `has_final_guess` 改为读取 `Script`/module 配置，不再硬编码。
4. **事件总线接线（P1-3）**
   - 将死亡、失败、轮回终止等关键触发统一发布到 `event_bus`，并接入能力触发入口。
5. **测试兜底（P1-4）**
   - 覆盖状态机关键分支、同时裁定、跨阶段终止、输入续跑回归。

#### Phase 1 完成标准（Definition of Done）

- [ ] DoD-1：从 `GAME_PREPARE` 可稳定跑到 `LOOP_END_CHECK`（至少 1 条最小路径）
- [x] DoD-2：`WaitForInput` 至少完成 1 次 “输入 -> 回调 -> 继续执行” 且无重复消费
- [ ] DoD-3：`LOOP_END_CHECK` 三分支可验证（胜利 / NEXT_LOOP / 最后一轮失败分支）
- [ ] DoD-4：关键同时裁定正确（主人公死亡 vs 主人公失败，军人阻止死亡后的分流）
- [ ] DoD-5：`has_final_guess` 来源于模组配置，不再在控制器硬编码
- [ ] DoD-6：具备最小自动化回归测试并可本地通过
### Phase 2（优先）: 数据层完善（loader / registry / 契约联动）
- [ ] 新增 `engine/rules/module_loader.py`：将 `data/modules/*.json` 装配为运行时结构
- [ ] 新增 `engine/rules/identity_registry.py`：身份定义注册与按 id 查询
- [ ] 新增 `engine/rules/incident_registry.py`：事件定义注册与按 id 查询
- [ ] `game_controller` / phase 逻辑接入 module 配置（含 `has_final_guess`、模组差异）
- [ ] 数据校验与加载链路打通（校验通过后可被 loader 消费）

#### Phase 2 实施顺序（建议）

1. **注册表先行（P2-0）**
   - 先落地 `identity_registry` / `incident_registry` 的最小只读查询接口（按 id 获取定义）。
   - 保持纯数据层，不引入业务结算逻辑。
2. **模块加载器（P2-1）**
   - 实现 `module_loader`：读取 `data/modules/*.json`，生成 `Script` + 规则/身份/事件定义对象。
   - 先支持 `first_steps` 与 `basic_tragedy_x` 两个模组。
3. **控制器接线（P2-2）**
   - 用加载结果驱动 `GameState.script` 与关键配置（如 `has_final_guess`），移除硬编码依赖。
4. **校验联动（P2-3）**
   - 保证“校验通过的数据”可被 loader 无异常消费；loader 错误信息复用数据路径语义（便于定位）。
5. **回归测试（P2-4）**
   - 为 loader/registry 增加最小单元测试 + 一条集成冒烟（加载模组 -> 构造初始状态）。

#### Phase 2 完成标准（Definition of Done）

- [ ] DoD-1：`first_steps`、`basic_tragedy_x` 均可由 loader 成功加载为运行时结构
- [ ] DoD-2：`identity_registry` / `incident_registry` 支持按 id 查询且覆盖模组定义
- [ ] DoD-3：`game_controller` 不再硬编码 `has_final_guess`，改为读模组配置
- [ ] DoD-4：数据校验通过后，loader 消费同一份数据不抛结构性错误
- [ ] DoD-5：存在最小自动化测试（registry + loader + 一条加载集成路径）并本地通过

### Phase 3: 行动牌系统
### Phase 4: 身份与能力系统（FS+BTX 全部身份）+ 事件系统
### Phase 5（暂缓）: 基础 UI（待数据层与核心规则闭环后再启动）
### Phase 6: 端到端可玩

---

## 3. 规则边界案例（必须在引擎中正确处理）

### 3.1 原子结算与同时裁定

**规则原文**（rules.md:178-179）：
- 原子结算内部按文字顺序执行；无"随后"的效果视为**同时生效**
- 同时生效时：先读状态→一次性写入→处理触发
- 同时产生"主人公死亡"+"主人公失败"时：**仅报送死亡**
- 死亡被阻止（军人）且有失败 → 报送失败
- 死亡被阻止且无失败 → 无终局效果

**6种原子类型**：①同阶段全部强制能力 ②一张行动牌 ③一次剧作家任意能力 ④一次主人公友好能力 ⑤一个事件完整效果 ⑥回合结束强制能力

### 3.2 医院事故多人死亡（用户提出的示例）

**场景**：医院有2+密谋，医院内有关键人物+杀人狂+普通角色+带护卫的角色

结算流程（单个原子结算⑤）：
1. **读**：医院1+密谋 → 条件1成立（全员死亡）；2+密谋 → 条件2成立（主人公死亡）
2. **写**：全部角色标记死亡（护卫角色消耗护卫代替死亡）+ 主人公死亡标记
3. **触发**：
   - 关键人物死亡 → "主人公失败+轮回立即结束"
   - 同时裁定：主人公死亡 + 主人公失败 → **仅报送主人公死亡**
   - 若军人能力阻止了主人公死亡 → **报送主人公失败**
4. **跨阶段跳转**：跳过后续阶段 → loop_end

### 3.3 杀手双能力冲突（turn_end 阶段）

**场景**：杀手与关键人物同区域，关键人物有2+密谋，杀手自身有4+密谋

- 能力1（任意）：关键人物死亡
- 能力2（任意）：主人公死亡
- 若剧作家声明能力1先 → 关键人物死亡 → 触发"主人公失败+轮回结束" → 能力2不执行
- 若剧作家声明能力2先 → 主人公死亡 → 轮回结束
- **实现要点**：任意能力由剧作家逐个声明，每次声明后检查是否触发轮回结束

### 3.4 杀人狂强制能力边界

- 条件："仅有1名角色与该角色位于同一区域"（恰好1名同伴，不是0不是2+）
- 杀人狂死亡后不执行（尸体无能力）
- 杀人狂移走后条件重新判定（用 turn_end 时的状态）
- 其他角色在事件阶段死亡导致只剩1人 → turn_end 时条件成立

特例：一个区域

### 3.5 护卫指示物与批量死亡

- 每次死亡消耗1枚护卫代替
- 同一原子结算中多次死亡：护卫数 ≥ 死亡次数 → 存活；否则死亡
- 多人批量死亡（医院事故）：每人独立判定护卫

### 3.6 心上人/求爱者互相死亡触发（BTX）

**场景A - 同时死亡**（如医院事故）：
1. 读状态：两人都将死亡
2. 写：两人死亡
3. 触发：心上人死亡→求爱者+6不安；求爱者死亡→心上人+6不安
4. 两者已是尸体，不安放到尸体上
5. 求爱者 turn_end 能力（1+密谋且3+不安→主人公死亡）不触发（已死）

**场景B - 先后死亡**（如杀人狂先杀心上人）：
1. 心上人死亡 → 求爱者+6不安
2. 求爱者若已有1+密谋且现在3+不安 → turn_end 时可触发主人公死亡
3. **这是剧作家的重要策略路线**

### 3.7 不安定因子动态能力（BTX）

- 常驻效果，实时判定：学校2+密谋→获得传谣人能力；都市2+密谋→获得关键人物能力
- 死亡时若持有关键人物能力 → 触发主人公失败
- 条件消失（密谋被移除）→ 能力立即失去
- **关键**：死亡触发时，需检查死亡**瞬间**的条件是否满足

### 3.8 妄想扩大病毒（BTX）

- 常驻：平民3+不安 → 身份变为杀人狂；不安降到3以下 → 变回平民
- 身份变化是实时的，turn_end 时如果已变回平民则杀人狂能力不触发
- 尸体不执行能力（即使不安仍≥3）
- 不影响非公开信息表的原始身份配置

### 3.9 因果线跨轮回效果（BTX）

- 轮回开始时：上轮结束时所有带友好的角色（含尸体+移除对象）放置2不安
- "带有"= ≥1枚友好，0枚不算
- 跨轮回累积：每轮结束时有友好 → 下轮开始+2不安
- **实现**：LoopSnapshot 需保存结束时每个角色的友好数

### 3.10 邪教徒无效化禁止密谋

- 触发窗口严格为**行动结算阶段**
- 邪教徒的"必定无视友好"影响的是友好能力的拒绝，与此能力无关
- 两张禁止密谋同时打出 → 互相无效化（两张都失效），此时邪教徒无需介入

### 3.11 禁止类卡牌交互

- **两张禁止密谋互消**：protagonist 打出2张 → 两张都失效
- 禁止友好 + 禁止密谋可同时存在于同一位置，互不影响
- 禁止移动每轮回限1次
- 时间旅者（BTX）：强制无视自身的禁止友好（仅行动结算阶段）

### 3.12 turn_end 阶段能力执行顺序

1. EX 槽更新（AHR 等模组，预留）
2. **全部强制能力同步结算**（杀人狂、临时工死亡判定等）
3. **剧作家逐个声明任意能力**（杀手、求爱者等）
4. 每次结算后检查是否触发轮回结束

### 3.13 事件发生判定

- 当事人存活 + 不安 ≥ 不安限度 → 事件可发生
- 黑猫当事人：不安限度=0 但特性规定"效果变为无现象"
- 仙人当事人：可视为相邻版图位置（仅事件判定时）
- 谋杀事件无其他角色在同区域 → 事件发生但无现象
- **信息边界**：必须告知事件是否发生 + 有无现象

### 3.14 跨阶段轮回终止

- 任何阶段中关键人物死亡 → 主人公失败 → 立即结束轮回
- 跳过当日后续所有阶段（含 turn_end）→ 直接进入 loop_end
- 杀人狂等 turn_end 能力**不会执行**

### 3.15 军人能力与同时裁定

- 军人友好能力："本轮回中主人公不会死亡"（每轮回限1次）
- 阻止的是"主人公死亡"，不阻止"主人公失败"
- 时间旅者最终日能力触发的是"主人公失败"→ 军人无法阻止

### 3.16 医生特殊规则

- 医生身份为无视友好 + 身上2+友好 → 剧作家可在**剧作家能力阶段**使用医生的友好能力
- 这是"剧作家使用主人公角色能力"的特例，需在 playwright_ability 阶段支持

更新：某些特殊情况和能力可以使剧作家可以使用角色能力，预留位置，后续补充即可

### 3.17 妹妹强制能力

- 妹妹能力：强制同区域成人使用一个友好能力，无视友好阈值
- 即使成人有"无视友好"特性，也**不能拒绝**
- 但能力仍受次数限制（每轮回限1次）

### 3.18 文本冲突（"能"vs"不能"）

- rules.md:82 说"不能优先于能"
- rules.md:262 说"不能不优先于能"
- **裁定**：采用"不能不优先于能"，即"能"优先。当规则文本中"能"与"不能"冲突时，"能"的描述胜出

### 3.19 技能/能力/事件发动条件与指示物不足

- **发动条件**：所有技能、能力、事件只要存在合法目标即可发动，不要求目标当前持有相关指示物。例如：女学生指定另一名学生时，即使该学生不安为 0 也合法
- **指示物不足**：移除指示物时按实际可移除数量执行（移除 min(拥有数, 要求数) 枚）。例如：要求移除 2 枚友好但目标只有 1 枚 → 移除 1 枚

### 3.20 信息边界

- **必须告知**：指示物增减结果、移动、死亡（区分死亡/失败）、事件是否发生+现象
- **不告知**：身份、当事人、能力触发原因、拒绝的具体特性
- **拒绝时必须告知**：技能发动失败（rules.md:221 更新）
- **亲友死亡**：轮回结束时若死亡 → 此时告知身份
- **裁定日志**：服务端保留完整日志，客户端按边界过滤

---

## 4. 数据模型预留（全模组）

Phase 0 只实现 FS + BTX，但数据模型必须为全部 8 个模组预留字段，避免后续重构。

### 4.1 TokenSet — 指示物（6种，全部预留）

```
paranoia: int   # 不安 — FS/BTX 起即用
intrigue: int   # 密谋 — FS/BTX 起即用
goodwill: int   # 友好 — FS/BTX 起即用
hope: int       # 希望 — WM/AHR/LL 用，默认0
despair: int    # 绝望 — WM/AHR/LL 用，默认0
guard: int      # 护卫 — 刑警友好能力产生，默认0
```

### 4.2 CharacterState — 角色状态预留

```
# 基础（FS/BTX 即用）
character_id, name, area, tokens, is_alive, is_removed
identity_id              # 当前生效身份
original_identity_id     # 非公开信息表配置的原始身份
revealed: bool           # 身份是否已公开
base_traits: set         # 基础特性（无视友好/必定无视友好/不死）
paranoia_limit: int      # 不安限度
attributes: list         # 属性标签（少女/少年/成人/男性/女性/学生/动物/植物/虚构/造物）
initial_area: str        # 初始区域（登场时所处区域，多初始区域时以剧本设定为准；手下以特性说明为准）
forbidden_areas: list[str]    # 禁行区域（不能通过任何方式到达；某些技能可取消）

# EX 牌相关（MZ/MC/HSA/AHR/LL 用）
ex_cards: list[str]      # 身上的 EX 牌（A/B/C/D）
curse_state: str|None    # 诅咒牌状态：None / "on_character" / "on_board"（HSA）

# 双身份（AHR 表/里世界）
surface_identity: str|None   # 表世界身份
inner_identity: str|None     # 里世界身份

# 角色特殊标记
action_card_restricted: bool  # 不可放置行动牌（狼人/预言家/幻想）
forbidden_areas: list[str]    # 禁行区域
entry_loop: int|None          # 第几轮登场（神灵）
entry_day: int|None           # 第几天登场（转校生）
```

### 4.3 GameState — 全局状态预留

```
# 基础（FS/BTX 即用）
current_loop, max_loops, current_day, max_days
current_phase: GamePhase
leader_index: int (0-2)
characters: dict[str, CharacterState]
board: BoardState
mastermind_hand, protagonist_hands
placed_cards: list[CardPlacement]
script: Script
incidents: list[IncidentSchedule]
failure_flags: set[str]
protagonist_dead: bool
loop_history: list[LoopSnapshot]

# EX 槽（MC/WM/AHR/LL 用）
ex_gauge: int = 0
ex_gauge_resets_per_loop: bool = True   # MC/AHR 每轮清零，WM 不清零

# 世界线（AHR 用）
world_line: int = 0          # 偶=表世界，奇=里世界
world_moved_today: bool = False  # 当天是否进行过世界移动

# 标志计数（LL 用）
communicated_flags: int = 0  # 已沟通标志
death_flags: int = 0         # 已死亡标志

# 背叛者（LL 用）
betrayer_map: dict = {}      # {protagonist_index: "A"/"B"/"C"}
betrayer_conditions: dict = {}

# 诅咒牌位置（HSA 用）
curse_cards_on_board: dict[str, list] = {}  # {area_id: [curse_card_ids]}

# 通用事件追踪
incidents_occurred_this_loop: list[str] = []  # 本轮发生过的事件名（MC的EX槽/BTX改变未来等）
soldier_protection_active: bool = False       # 军人能力是否生效
```

### 4.4 CardHand — 手牌预留

```
# 基础牌（FS/BTX 即用）
剧作家：密谋+2, 密谋+1, 不安+1(×2), 不安-1, 横移, 竖移, 斜移, 禁止友好, 禁止不安
主人公：友好+1, 友好+2, 不安+1, 不安-1, 横移, 竖移, 禁止密谋, 禁止移动

# 扩展牌（预留字段，按模组启用）
剧作家扩展：绝望+1（AHR/LL 用，第一轮额外获得）
主人公扩展：希望+1（AHR/LL 用，特定条件获得）
AHR 额外：主人公额外获得 不安+2，剧作家额外获得 友好+1
```

### 4.5 BoardState — 版图预留

```
# 基础（FS/BTX 即用）
areas: dict[str, BoardArea]  # hospital/school/shrine/city
faraway: FarawayState
adjacency: dict              # 相邻关系（横/竖/斜）

# 版图指示物（FS/BTX 即用）
BoardArea.tokens: TokenSet   # 主要是密谋，但预留全部类型

# 诅咒牌（HSA 用）
BoardArea.curse_cards: list[str] = []

# 尸体计数（HSA 群众事件用）
BoardArea.corpse_count: int  # 由 characters 派生，含"密谋视作尸体"规则

# 封锁状态（MC 封锁事件用）
BoardArea.lockdown_until_day: int|None = None
```

### 4.6 LoopSnapshot — 跨轮回快照

```
loop_number: int
ex_gauge: int                          # 轮回结束时的 EX 槽值
incidents_occurred: list[str]          # 本轮发生过的事件
character_snapshots: dict[str, CharacterEndState]

CharacterEndState:
    is_alive: bool
    is_removed: bool
    tokens: TokenSet                   # 结束时的指示物（因果线需要友好数）
    identity_revealed: bool            # 身份是否被公开（亲友需要）
    area: str                          # 结束时所在区域
```

### 4.7 各模组需要的特殊机制索引

| 模组 | 需要的预留字段 |
|---|---|
| **First Steps** | 基础即可，无额外 |
| **Basic Tragedy X** | 基础即可（身份变化用runtime派生） |
| **Midnight Zone** | ex_cards, EX牌状态, 忍者身份宣称历史 |
| **Mystery Circle** | ex_gauge(每轮清零), lockdown_until_day |
| **Haunted Stage Again** | curse_state, curse_cards_on_board, corpse_count, 群众事件 |
| **Weird Mythology** | ex_gauge(不清零), 旧日魔术分级效果 |
| **Another Horizon Revised** | world_line, surface/inner_identity, 心境反转, 扩展手牌 |
| **Last Liar** | betrayer_map, communicated/death_flags, 特殊胜利条件 |

### 4.8 角色特性实现方案（数据驱动）

角色特性来自角色表（appendix C），是角色固有的被动/触发规则，与身份特性（`Trait`枚举）完全不同层次。
实现思路：尽量复用现有 `Ability`（timing + condition）+ `Effect` 原语组合，写入 `characters.json` 的 `traits` 字段，运行时与身份能力走同一条结算管线。

#### A. 已由 CharacterState 字段覆盖（无需额外处理）

| 角色特性 | 对应字段 | 说明 |
|---|---|---|
| 初始区域 | `initial_area` | 含多初始区域（从者、手下、仙人等） |
| 禁行区域 | `forbidden_areas` | 小女孩：医院/神社/都市；巫女：都市等 |
| 不安限度 | `paranoia_limit` | 黑猫=0, 临时工=1 等 |
| 属性标签 | `attributes` | 学生/成人/少年/少女/动物/虚构等 |
| 延迟登场 | `entry_loop` / `entry_day` | 神灵：指定轮回登场 |
| 不可放置行动牌 | `action_card_restricted` | 幻想 |

#### B. 可用现有 Ability + Effect 原语表达

| 角色 | 特性描述 | 数据驱动表达 |
|---|---|---|
| 黑猫 | 轮回开始→神社+1密谋 | `Ability(timing=LOOP_START, type=MANDATORY)` + `Effect(PLACE_TOKEN, target="shrine", token=INTRIGUE, amount=1)` |
| 临时工 | 3+指示物→turn_end死亡 | `Ability(timing=TURN_END, type=MANDATORY, condition={token_total_check, >=3})` + `Effect(KILL_CHARACTER, target="self")` |
| 手下 | 轮回开始由剧作家决定区域 | `Ability(timing=LOOP_START, type=MANDATORY)` + `Effect(MOVE_CHARACTER, target="self", chooser="mastermind")` |
| 学者 | 轮回开始放1枚指示物（三选一） | `Ability(timing=LOOP_START, type=MANDATORY)` + `Effect(PLACE_TOKEN, target="self", chooser="mastermind")` — 需扩展 chooser 支持选择指示物类型 |

#### C. 现有原语无法覆盖（需新增机制）

| 角色 | 特性描述 | 缺失原语 | 建议 |
|---|---|---|---|
| **从者** | 大人物/大小姐移动时跟随移动 | `FOLLOW_MOVEMENT` — 移动结算时的联动钩子 | 新增 EffectType 或移动resolver内置钩子 |
| **从者** | 大人物/大小姐死亡时代替死亡 | `SUBSTITUTE_DEATH` — 死亡处理链中的替身机制 | DeathResolver 中新增替身检查步骤 |
| **AI** | 事件判定时所有指示物视作不安 | `TOKEN_REINTERPRET` — 事件判定时的指示物重解释 | 事件resolver中增加修饰器接口 |
| **仙人** | 事件判定外不安限度视为0 | `PARANOIA_LIMIT_OVERRIDE` — 条件性限度覆盖 | Condition 求值时查询角色修饰器 |
| **仙人** | 事件结算时可视为顺时针相邻版图 | `AREA_OVERRIDE` — 事件判定时的区域替换 | 事件resolver中增加区域覆盖接口 |
| **幻想** | 版图上行动牌同时作用于自身 | `BOARD_CARD_REDIRECT` — 行动牌结算时的额外目标 | 行动牌resolver中增加重定向钩子 |
| **教主** | 当事人事件结算2次 | `INCIDENT_REPEAT` — 事件结算重复修饰 | 事件resolver中增加重复计数接口 |
| **临时工** | 死亡时→配置临时工?上场 | `SPAWN_CHARACTER` — 运行时动态添加角色 | 新增 EffectType + GameState 动态角色管理 |
| **UP主** | EX牌角色所在区域视为同区域 | `AREA_EXTEND` — 能力使用时区域扩展 | 能力resolver中增加区域扩展查询 |
| **UP主** | 首次事件当天turn_end放EX牌 | `PLACE_EX_CARD` 已有，但触发条件"本轮首次事件发生当天"需新增 Condition 类型 `first_incident_day` |
| **黑猫** | 当事人事件效果变为无现象 | 无需新原语 — 事件发生但效果为空，与谋杀无目标相同处理 | 事件resolver执行效果前检查当事人角色特性，黑猫时将效果列表替换为 `[NO_EFFECT]`（已有该EffectType） |

#### D. 剧本制作约束（非运行时效果）

以下特性在剧本制作阶段校验，不进入结算管线，写入角色定义的 `script_constraints` 字段：

| 角色 | 约束 |
|---|---|
| 妹妹 | 不可分配带有无视友好身份特性的身份 |
| AI | 不能分配为平民 |
| 局外人 | 不参与规则身份分配，分配模组中存在且规则未使用的身份 |
| 模仿犯 | 不参与规则身份分配，复制剧本中另一角色的身份（无视上限） |
| 临时工? | 身份与事件配置与临时工一致 |

#### 小结

- A+B 类覆盖了约 **10 个**角色特性，可完全数据驱动
- C 类需新增约 **10 个**机制（新 EffectType / resolver 钩子 / Condition 类型），建议按模组优先级逐步实现
- D 类约 **5 个**剧本制作约束，在脚本校验层处理
- FS+BTX 模组中涉及的角色特性较少（黑猫、小女孩的禁行、仙人），优先实现这些

---

## 5. 验证方式

- **单元测试**：每个 resolver 独立测试，覆盖上述边界案例
- **集成测试**：预设剧本完整走通，验证状态机流转
- **边界案例回归测试**：3.1-3.20 每条至少1个 test case
- **运行**：`python main.py` 启动 PySide6
