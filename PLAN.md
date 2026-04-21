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
  - ✅ 修复日期推进逻辑（TURN_END → TURN_START 时推进 current_day）
- [x] `engine/resolvers/atomic_resolver.py`：原子结算框架（读-写-触发）骨架
- [x] `engine/resolvers/death_resolver.py`：死亡处理链基础（护卫/不死/死亡）
- [x] `engine/phases/phase_base.py`：PhaseHandler / PhaseSignal 框架
- [x] 打通 `WaitForInput` 回填闭环：`provide_input` 后稳定续跑后续阶段
- [x] `engine/game_state.py`：新增 `create_minimal_test_state()` 便于测试
- [x] `INCIDENT` 最小业务闭环：触发判定 + 效果执行 + ForceLoopEnd ✅ 2026-04-14
- [x] 完成最小阶段业务闭环：`ACTION_RESOLVE`、`TURN_END`、`LOOP_END_CHECK` ✅ 2026-04-14
- [x] 将 `has_final_guess` 从控制器硬编码改为读取模组配置（`GameState.module_def` + `apply_loaded_module`）✅ 2026-04-18
- [x] 接通事件触发链与身份能力触发到 `event_bus` ✅ 2026-04-14
- [x] 补充 Phase 1 核心测试：状态机分支、同时裁定、死亡/失败优先级、跨阶段 loop_end 跳转 ✅ 2026-04-19

#### Phase 1 实施进度

**已完成（P1-0 输入闭环）：** ✅
- 实现 `WaitForInput.callback` 生命周期：挂起、回填、续跑、防重复输入
- 验证 “一次输入 -> 正常推进到下一阶段”

**已完成（P1-1 最小业务闭环）：** ✅ 2026-04-14
- [x] `INCIDENT`：最小事件触发判定与执行路径 ✅ 2026-04-14
- [x] `ACTION_RESOLVE`：CardType→Effect 映射，FORBID 预处理，移动计算，ForceLoopEnd 检查 ✅ 2026-04-14
- [x] `TURN_END`：框架通（身份能力待 Phase 2 数据层后补充）✅
- [x] `LOOP_END_CHECK`：三分支已通，failure_flags 由 game_controller 传入 ✅

**已完成（P1-2 模组配置接线）：** ✅ 2026-04-18
- `GameState.module_def` 承载 `ModuleDef`；`apply_loaded_module()` 写入 defs 与 `script.module_id`；`game_controller` 使用 `state.has_final_guess` 驱动状态机
- 开局需调用 `load_module` + `apply_loaded_module`（或等价装配）；未装配时 `has_final_guess` 默认 `True`（兼容旧行为）

**已完成（P1-3 事件总线接线）：** ✅ 2026-04-19
- 统一发布死亡、失败、轮回终止等关键触发到 `event_bus`
- 接入能力触发入口：身份 `ON_DEATH` 触发时发布 `ABILITY_DECLARED`

**已完成（P1-4 测试兜底 + DoD-4）：** ✅ 2026-04-14
- 同时裁定逻辑（`atomic_resolver._adjudicate`）：死亡/失败优先级、军人阻止分流 ✅
- 关键分支自动化回归测试（`tests/test_incident_handler.py` 6条，`tests/test_wait_for_input_loop.py` 4条）✅

#### Phase 1 完成标准（Definition of Done）

- [x] DoD-1：从 `GAME_PREPARE` 可稳定跑到 `LOOP_END_CHECK`（至少 1 条最小路径）✅ 2026-04-14
- [x] DoD-2：`WaitForInput` 至少完成 1 次 “输入 -> 回调 -> 继续执行” 且无重复消费
- [x] DoD-3：`LOOP_END_CHECK` 三分支可验证（胜利 / NEXT_LOOP / 最后一轮失败分支）✅ 验证于 test 3
- [x] DoD-4：关键同时裁定正确（主人公死亡 vs 主人公失败，军人阻止死亡后的分流）✅ 2026-04-14
- [x] DoD-5：`has_final_guess` 来源于模组配置，不再在控制器硬编码 ✅ 2026-04-18
- [x] DoD-6：具备最小自动化回归测试并可本地通过 ✅ 2026-04-14

---

**📋 文档更新规则：**
每次代码更新时，同步更新本文档中对应的进度标记与日期戳。这确保计划与实际代码状态保持一致。
### Phase 2（优先，与 Phase 1-2/1-3 并行）: 数据层完善（loader / registry / 契约联动）

**⚠️ 关联说明：** Phase 2 是 Phase 1 DoD-5（has_final_guess 配置化）的前置依赖。建议 Phase 2-P2-1 完成后，立即回过来做 Phase 1-P1-2。

- [x] 新增 `engine/rules/module_loader.py`：将 `data/modules/*.json` 装配为运行时结构 ✅ 2026-04-14
- [x] 新增 `engine/rules/identity_registry.py`：身份定义注册与按 id 查询 ✅ 2026-04-14
- [x] 新增 `engine/rules/incident_registry.py`：事件定义注册与按 id 查询 ✅ 2026-04-14
- [x] `game_controller` / phase 逻辑接入 module 配置（含 `has_final_guess`、模组差异）✅ 2026-04-18
- [x] 数据校验与加载链路打通（校验通过后可被 loader 消费）✅ 2026-04-18

#### Phase 2 实施进度

**已完成（P2-0 注册表先行）：** ✅ 2026-04-14
- `IdentityRegistry` / `IncidentRegistry`：`register(defs)` + `get(id)` + `all()` 只读接口
- 纯数据层，无业务逻辑

**已完成（P2-1 模块加载器）：**
- 实现 `module_loader`：读取 `data/modules/*.json`，生成 `Script` + 规则/身份/事件定义对象
- 先支持 `first_steps` 与 `basic_tragedy_x` 两个模组
- 完成后转接回 Phase 1-P1-2（has_final_guess 配置化）✅

**已完成（P2-2～P2-4）：** ✅ 2026-04-18
- **控制器接线**：`build_game_state_from_module()`、`GameController.start_game(module_id, ...)`；`apply_loaded_module` 同步 `script.special_rules_text`
- **校验联动**：`tests/test_validation_loader_integration.py`（`validate_data_root` 通过后加载两模组）
- **回归测试**：`tests/test_registry_loader.py`；`test_module_apply` 增补装配与开局冒烟

#### Phase 2 完成标准（Definition of Done）

- [x] DoD-1：`first_steps`、`basic_tragedy_x` 均可由 loader 成功加载为运行时结构 ✅ 2026-04-18
- [x] DoD-2：`identity_registry` / `incident_registry` 支持按 id 查询且覆盖模组定义 ✅ 2026-04-18
- [x] DoD-3：`game_controller` 不再硬编码 `has_final_guess`，改为读模组配置 ✅ 2026-04-18
- [x] DoD-4：数据校验通过后，loader 消费同一份数据不抛结构性错误 ✅ 2026-04-18
- [x] DoD-5：存在最小自动化测试（registry + loader + 一条加载集成路径）并本地通过 ✅ 2026-04-18

### Phase 3（已完成）: 行动牌系统 ✅ 2026-04-18
- [x] 定义 `PlacementIntent` 数据类（cards.py）
- [x] 修复 `MastermindActionHandler`：真实目标选择 + 恰好 3 张
- [x] 修复 `ProtagonistActionHandler`：3 名主人公递归 callback 链
- [x] 统一 `once_per_loop` 标记到 `ActionResolveHandler`
- [x] 编写 11 个完整测试用例（T1-T11），全部通过
- [x] 回归测试：兼容旧测试，31/31 通过

#### Phase 3 完成标准（Definition of Done）
- [x] DoD-1：剧作家恰好放 3 张牌，每张含真实目标（不再硬编码 school）✅
- [x] DoD-2：3 名主人公各放 1 张牌（递归 callback 链通过）✅
- [x] DoD-3：`is_used_this_loop` 仅在 `ActionResolveHandler` 中标记一次✅
- [x] DoD-4：`NO_ACTION_CARDS` 角色作为 character target 时抛出 ValueError✅
- [x] DoD-5：T1-T11 测试全部通过✅
- [x] DoD-6：回归测试全部通过（31/31）✅

### Phase 4: 身份与能力系统（FS+BTX 全部身份）+ 事件系统

**⚠️ 现状核实（2026-04-19）：**
- `build_game_state_from_module()` 当前仅装配模组定义、身份/事件 defs 与主人公手牌，**未装配角色模板、剧本角色列表、规则 Y/X、事件日程**。
- Phase 4 当前范围按“先做数据层”执行：本局实例输入链路后续由 UI 提供，Phase 4 仅在最后测试阶段做“测试导入实例”验证。
- `TurnEndHandler`、`PlaywrightAbilityHandler`、`ProtagonistAbilityHandler`、`LoopStartHandler` 仍为空骨架；`AtomicResolver` 仅支持部分 target selector 与 effect primitive。
- `data/characters.json` 已补全附录 C 角色表 ✅ 2026-04-18，但 `data/modules/basic_tragedy_x.json` 目前只覆盖部分 BTX 身份/事件，需继续补齐到附录定义。

#### P4-0（已完成）：角色数据加载（前置，实例导入后置）✅ 2026-04-19

`data/characters.json` 已含角色特性、属性、不安限度、初始区域与友好能力元数据；当前运行时未消费这些信息，导致 `CharacterState.base_traits` / `attributes` / `paranoia_limit` 等字段在真实开局链路中无法完整落地。

- [x] 新建 `engine/rules/character_loader.py`：读取 `data/characters.json`，返回 `dict[str, CharacterDef]` ✅ 2026-04-19
- [x] 新增 `CharacterDef` 运行时模型：`character_id, name, initial_area, forbidden_areas, attributes, paranoia_limit, base_traits, goodwill_ability_*` ✅ 2026-04-19
- [x] 从 `CharacterDef + CharacterSetup` 初始化 `CharacterState`，正确填充 `base_traits`、`attributes`、`paranoia_limit`、`forbidden_areas` ✅ 2026-04-19
- [x] 平民身份兼容：支持 `"commoner"` 输入并归一化为 `"平民"`（保留现有运行时写法）✅ 2026-04-19
- [x] `build_game_state_from_module()` 在 Phase 4 只保持数据层兼容，不承担本局实例输入职责 ✅ 2026-04-19
- [x] 在 `data/characters.json` 补全附录 C 全表角色（含 `trait_rule`、`goodwill_ability_texts`、`goodwill_ability_goodwill_costs`、`goodwill_ability_once_per_loop`、`initial_area_candidates` 等）✅ 2026-04-18

> **为何是前置**：P4-1/P4-2/P4-3 需要依赖真实的角色 traits / attributes / paranoia_limit；P4-5 的身份派生与变更也依赖“原始身份 + 当前身份”的双轨状态。实例导入流程本身后置到 UI 阶段。

> **Phase 4 架构原则（2026-04-19 调整）**：
> 1. 能力实现统一由 `engine/resolvers/ability_resolver.py` 作为入口协调，**不按模组拆分 resolver**。
> 2. `ability_resolver` 内部按**能力来源**分层：`角色友好能力`、`身份能力`、`规则 Y/X 能力`、`常驻派生能力`。
> 3. FS / BTX / 后续模组差异优先体现在数据定义上，避免写 `module_specific` 分叉逻辑。
> 4. Phase 4 顺序固定为：**先简易角色层 → 再统一能力层与身份/规则能力接入 → 最后阶段接线**。

#### P4-1：简易角色系统（先接能力所需最小闭环）

本步只做“角色层进入能力系统”所必需的部分，**不在 Phase 4 前半一次性完成完整角色系统**。角色复杂特性、需要新增原语的角色能力，后置到专门条目逐步补齐。

- [x] 将 `CharacterDef.goodwill_ability_*` 接入运行时能力候选，形成“角色友好能力”数据入口 ✅ 2026-04-19
- [x] 在 `ability_resolver` 中新增 `collect_goodwill_abilities()`，与身份/规则能力分层收集 ✅ 2026-04-19
- [x] 主人公能力阶段所需字段打通：`goodwill_cost`、`once_per_loop`、`can_be_refused` ✅ 2026-04-19
- [x] `base_traits`、`attributes`、`paranoia_limit` 仅先服务于能力条件判断与拒绝逻辑 ✅ 2026-04-19
- [x] 暂不把全部 `trait_rule` 做成完整机制；仅把 Phase 4 主线所需的角色侧最小能力链先接通 ✅ 2026-04-19

#### P4-2：能力与目标解析框架（统一入口，按来源分层）

当前 `AtomicResolver` 适合做“纯结算”，但不适合同时承担“收集可用能力 + 交互选目标 + 推导动态能力”职责。Phase 4 需把这层拆清，并把现有 `ability_resolver` 从基础框架提升为统一协调入口。

- [x] 新建 `engine/resolvers/ability_resolver.py` ✅ 2026-04-19
- [x] 按 `timing`、`ability_type`、存活状态收集可生效能力（基础版）✅ 2026-04-19
- [x] `Condition` 求值：不安阈值、同区域、密谋阈值、最终日、身份判定、trait 判定、事件发生判定（基础版）✅ 2026-04-19
- [x] 拒绝逻辑：`Trait.IGNORE_GOODWILL`、`Trait.MUST_IGNORE_GOODWILL`（判断入口）✅ 2026-04-19
- [x] 将现有 `collect_character_abilities()` 语义收束为“身份能力收集”，避免与“角色友好能力”混名 ✅ 2026-04-19
- [x] 明确统一收集入口分层：`collect_goodwill_abilities()`、`collect_identity_abilities()`、`collect_rule_abilities()`、`collect_derived_abilities()` ✅ 2026-04-19
- [x] 常驻派生能力统一走 `collect_derived_abilities()`：不安定因子及未来同类身份都走同一入口 ✅ 2026-04-19
- [x] once-per-loop / once-per-day 使用限制在能力层统一处理 ✅ 2026-04-19
- [x] 新增 target 解析层（可为 `target_resolver` 或收进 `ability_resolver`）：支持 `same_area_any`、`any_character`、`any_board`、`condition_target`、`hospital_all` 等 selector ✅ 2026-04-19
- [x] 保持 `AtomicResolver` 为“已具体化 effects 的纯结算器”，不要把 `WaitForInput` 混入 resolver ✅ 2026-04-19

#### P4-3：FS / BTX 身份与规则能力补齐

在统一能力入口稳定后，再补齐 FS / BTX 身份与规则能力；按附录真实 timing 落地，不按模组写分叉 resolver，也不再把 `PLAYWRIGHT_ABILITY` 的能力误放到 `TURN_END`。

- [ ] First Steps 身份：
  - [x] `key_person`：`ON_DEATH` → 主人公失败 + 强制结束轮回 ✅ 2026-04-20
  - [x] `killer`：`TURN_END` 任意能力（关键人物死亡 / 自身 4+ 密谋导致主人公死亡）✅ 2026-04-20
  - [x] `mastermind`：`PLAYWRIGHT_ABILITY` 任意能力（同区域角色或版图 +1 密谋）✅ 2026-04-20
  - [x] `rumormonger`：`PLAYWRIGHT_ABILITY` 任意能力（同区域任意角色 +1 不安）✅ 2026-04-20
  - [x] `serial_killer`：`TURN_END` 强制能力（恰好 1 名同区域角色 → 其死亡）✅ 2026-04-20
  - [x] `friend` / `commoner`：按规则 Y/X 存在性补齐；亲友的 `LOOP_END` / `LOOP_START` 行为接通 ✅ 2026-04-20
- [ ] Basic Tragedy X 新增身份：
  - [x] `cultist`：`ACTION_RESOLVE` 无效化同区域禁止密谋；具 `MUST_IGNORE_GOODWILL` ✅ 2026-04-20
  - [x] `time_traveler`：`ACTION_RESOLVE` 无视自身禁止友好；`FINAL_DAY_TURN_END` 任意失败能力；具 `IMMORTAL` ✅ 2026-04-20
  - [x] `lover` / `beloved`：死亡互相触发的 +6 不安链与求爱者 `TURN_END` 任意能力 ✅ 2026-04-20
  - [x] `unstable_factor`：常驻获得传谣人 / 关键人物能力，但身份本身不变 ✅ 2026-04-20
  - [x] `friend`、`serial_killer`、`rumormonger` 复用 FS 能力，不再重复写分叉实现 ✅ 2026-04-20
- [ ] 规则附加能力：
  - [x] FS / BTX `rules_y`、`rules_x` 中已有或缺失的失败条件、剧作家额外能力一并接入能力收集链 ✅ 2026-04-20

#### P4-4：阶段接线（Playwright / Protagonist / TurnEnd / LoopStart）

阶段 handler 只负责声明顺序、输入交互与公告，不承担能力来源判断；能力来源统一回到 `ability_resolver`。

- [x] `PlaywrightAbilityHandler`：实现剧作家能力阶段的任意能力声明循环（主谋、传谣人、规则能力等） ✅ 2026-04-20
- [x] `ProtagonistAbilityHandler`：实现队长声明友好能力 → 剧作家拒绝 / 不拒绝 → 支付与结算 ✅ 2026-04-20
- [x] `TurnEndHandler`：分两段执行 ✅ 2026-04-20
  - [x] 第一段：同步结算全部强制 `TURN_END` 能力 ✅ 2026-04-20
  - [x] 第二段：剧作家逐个声明任意 `TURN_END` / `FINAL_DAY_TURN_END` 能力，每次后检查 `ForceLoopEnd` ✅ 2026-04-20
- [x] `LoopStartHandler`：实现轮回开始触发（因果线、亲友身份公开后的 +1 友好等） ✅ 2026-04-20
- [x] `LoopEndHandler`：先处理 `LOOP_END` 能力与失败条件公开，再保存 `LoopSnapshot` ✅ 2026-04-20

#### P4-5：身份变更、特性与重置

这一层是 BTX 的关键风险点，必须明确在计划中单列。

- [x] 支持 `EffectType.CHANGE_IDENTITY` ✅ 2026-04-20
- [x] 妄想扩大病毒：满足条件时将平民变为杀人狂；条件解除时恢复原身份 ✅ 2026-04-20
- [x] `CharacterState.reset_for_new_loop()` 恢复 `identity_id = original_identity_id` ✅ 2026-04-20
- [x] `DeathResolver` 的 active traits 来源改为：`base_traits + 当前身份 traits + 常驻派生 traits` ✅ 2026-04-20
- [x] 时间旅者的不死、邪教徒/主谋/杀手的不视友好，都通过统一 active traits 生效 ✅ 2026-04-20

#### P4-6：GAME_PREPARE 剧本校验

`SCRIPT_CREATION` / “剧本制作时”类规则与特性，不进入轮回内能力声明 / 结算管线；统一在 `GAME_PREPARE` 阶段、剧本输入完成后做合法性校验，失败则阻止开局并返回错误。

> 当前进度：**统一入口已完成，FS / BTX 已接入**；其他模组保留扩展点，后续按模组逐步补具体约束。

- [x] 建立剧本校验入口（建议 `script_validator` 或等价层），在 `build_game_state_from_module()` 完成规则 / 角色 / 事件装配后执行 ✅ 2026-04-20
- [x] 角色剧本制作约束统一收口：角色 `trait_rule` / `script_constraints` 中的“剧本制作时”条件不再散落在运行时 handler ✅ 2026-04-20
- [x] 规则 Y / X 的 `SCRIPT_CREATION` 约束接入校验层，不走 `ability_resolver`（FS / BTX） ✅ 2026-04-20
- [x] 身份槽与人数放宽 / 变更类规则校验：统一入口已预留，其他模组后续扩展 ✅ 2026-04-20
  - [ ] 后续扩展：`最黑暗的剧本`：允许暴徒人数为 0-2，需覆盖默认身份槽数量校验
- [x] 角色属性 / 身份匹配类规则校验：统一入口已预留，FS / BTX 当前范围已完成 ✅ 2026-04-20
  - [x] `和我签订契约吧`：关键人物对应角色必须带有少女属性 ✅ 2026-04-20
  - [ ] 后续扩展：`男子汉的战争`：忍者对应角色必须带有男性属性
  - [ ] 后续扩展：`高贵的血族`：吸血鬼与关键人物必须互为异性
- [x] 事件配置类规则校验：统一入口已预留，其他模组后续扩展 ✅ 2026-04-20
  - [ ] 后续扩展：`灭亡讴歌`：剧本必须引入 1 个或以上自杀事件
  - [ ] 后续扩展：“必须成为某事件当事人” / “不可成为事件当事人” 类角色约束统一校验
- [x] 校验错误输出标准化：明确返回 rule / character / incident 级别的错误来源，便于 UI 在剧本输入阶段直接提示 ✅ 2026-04-20

#### P4-7：事件系统完善（FS + BTX 全量）

当前事件基础链路已通，但 target selector、事件全集与公开信息边界仍不完整。

- [x] 补齐 FS / BTX 事件定义：`不安扩散`、`谋杀`、`邪气污染`、`医院事故`、`自杀`、`散播`、`蝴蝶效应`、`失踪`、`远距离杀人` ✅ 2026-04-20
- [x] 支持事件中“任意角色 / 任意版图 / 同区域任意角色 / 与当事人不同角色”等选择型 target（通过 `IncidentSchedule` 隐藏目标字段 + `IncidentResolver` 具体化）✅ 2026-04-20
- [x] `谋杀`、`远距离杀人` 等无合法目标时：事件视为发生，但无现象 ✅ 2026-04-20
- [x] `NO_EFFECT` 事件与“发生但无合法目标”统一走同一公开结果语义（`public_result.has_phenomenon=False`）✅ 2026-04-20
- [x] 事件信息边界：记录“是否发生 + 是否有现象 + 公开结果”，不泄露当事人；UI 公告通路后续实现 ✅ 2026-04-20
- [x] 拆出 `incident_resolver.py`：事件触发判定 / 事件上下文 / 公开结果语义独立于 `IncidentHandler`，后续承接公开事件、密谋代替不安判定等特殊机制 ✅ 2026-04-20

#### P4-8：跨轮回效果与快照利用

- [x] `LoopStartHandler`：因果线 → 上轮结束时有友好的角色（含尸体/被移除）本轮开始 +2 不安 ✅ 2026-04-20
- [x] `LoopStartHandler`：亲友身份曾公开 → 本轮开始该角色 +1 友好 ✅ 2026-04-20
- [x] `LoopSnapshot` 继续复用现有 `character_snapshots`，无需新增第二套跨轮回结构 ✅ 2026-04-20
- [x] Phase 4 当前无需扩展 `LoopSnapshot`；若后续模组需要更多跨轮回信息再最小扩展 ✅ 2026-04-20

#### P4-9：测试覆盖与调试入口

调试入口只服务 P4 能力验证与后续 UI 调试面板，不进入正式游戏流程；允许构造前置状态，但核心验证必须通过“手动触发能力 / 事件 → 走正式 resolver → 检查状态变化”完成，避免把任意改状态当作能力测试。

实现策略：**先提供引擎侧 debug API，再由后续 UI 调试面板接入**。调试面板不直接操作内部状态字段，只调用受控接口；这样 CLI、单测与未来 UI 可复用同一套调试能力。

调试 / 测试入口：
- [x] 新增受控调试模块 `engine/debug/`，与正式 Phase Handler / GAME_PREPARE 流程隔离 ✅ 2026-04-20
- [x] `build_debug_state(...)`：支持跳过剧本校验创建测试局，仅用于能力测试与 UI 调试模式 ✅ 2026-04-20
- [x] `apply_debug_setup(...)`：支持受控设置前置状态（角色位置、指示物、生死、公开状态、当前阶段等），禁止任意字段直改接口 ✅ 2026-04-20
- [x] `list_debug_abilities(state, ...)`：列出当前可发动能力，支持按 actor / timing / ability_type 过滤 ✅ 2026-04-20
- [x] `trigger_debug_ability(...)`：手动触发指定能力，指定 actor / ability_id / targets / 可选忽略 timing，但结算仍走 `AbilityResolver + AtomicResolver` ✅ 2026-04-20
- [x] `trigger_debug_incident(...)`：手动触发指定事件，指定 incident_id / perpetrator_id / 隐藏目标选择，结算仍走 `IncidentResolver` ✅ 2026-04-20
- [x] `get_debug_snapshot(state)`：读取角色、版图、事件结果、失败/死亡标志、event_bus 日志摘要，便于 UI 层展示与自动化断言 ✅ 2026-04-20
- [x] 记录调试触发日志：阶段、actor、ability / incident、targets、结果状态摘要 ✅ 2026-04-20
- [x] 预留 UI adapter 层：后续 UI 调试面板只调用 debug API，不直接依赖 resolver 内部实现 ✅ 2026-04-20

关键边界案例（对应 §3.x）：
- [x] Loader / 数据层：`character_loader`、`build_game_state_from_module` 数据兼容、身份默认值兼容 ✅ 2026-04-19
- [x] 简易角色系统：角色友好能力收集、费用、次数限制与拒绝链路（框架闭环；真实友好能力效果后续按角色补）✅ 2026-04-20
- [ ] 剧作家能力阶段：主谋/传谣人/规则能力的逐次声明与 `pass`
- [x] 主人公能力阶段：友好能力声明、拒绝、`IGNORE_GOODWILL` / `MUST_IGNORE_GOODWILL`（框架闭环）✅ 2026-04-20
- [ ] 杀人狂强制能力边界（§3.4）
- [ ] 不安定因子实时派生（§3.7）
- [ ] 妄想扩大病毒身份切换 + 跨轮回恢复（§3.8）
- [x] 因果线跨轮回（§3.9）✅ 2026-04-20
- [ ] TURN_END 任意能力执行顺序（§3.12）
- [ ] 事件无目标但发生（§3.13）
- [x] 时间旅者最终日判定与不死特性（§3.15）✅ 2026-04-20
- [x] Phase 4 最后一步：通过测试路径导入最小本局实例（非 UI），验证数据层与能力链可联动 ✅ 2026-04-19
- [x] 跑通 `python3 -m engine.validation` + 全量 `pytest` ✅ 2026-04-19

#### Phase 4 完成标准（Definition of Done）

- [x] DoD-0：`characters.json` 角色数据可由 `character_loader` 加载，并正确填充 `CharacterState` ✅ 2026-04-19
- [x] DoD-1：数据层可支持本局实例字段（`rule_y/rules_x/characters/incidents`）并通过测试导入验证；正式实例输入链路由 UI 阶段实现 ✅ 2026-04-19
- [x] DoD-2：简易角色系统接入完成；角色友好能力框架可被收集、声明、拒绝、计次与结算（真实友好能力效果后续按角色补）✅ 2026-04-20
- [x] DoD-3：P4 范围内能力闭环完成；角色友好能力框架 / 身份 / 规则 / 常驻派生能力可通过 `ability_resolver`（统一入口、按来源分层）收集并正确结算 ✅ 2026-04-20
- [x] DoD-4：`PLAYWRIGHT_ABILITY`、`PROTAGONIST_ABILITY`、`TURN_END`、`LOOP_START` 四类阶段接线完成
- [x] DoD-5：`CHANGE_IDENTITY`、active traits、跨轮回身份恢复正确 ✅ 2026-04-20
- [x] DoD-6：FS + BTX 事件系统完整（含无现象情形与信息边界）
- [x] DoD-7：关键边界案例（§3.4 / §3.7 / §3.8 / §3.9 / §3.12 / §3.13 / §3.15）有自动化测试并本地通过
- [x] DoD-8：P4 调试入口可跳过校验、构造前置状态、手动触发能力并返回状态快照，且不影响正式流程

### Phase 5 : 测试第一个模组

    模组 first step，3轮回，每轮回三天，无特殊规则。规则X谋杀计划，规则Y开膛者的魔影。登场角色，男学生（平民），女学生(关键人物)，偶像（传谣人），职员（杀手），医生（主谋）。 事件：第三天 自杀

### Phase 6（暂缓）: 基础 UI（待数据层与核心规则闭环后再启动）

### Phase 7: 端到端可玩

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

## 3.5 整合优先级与依赖关系图

```
Phase 1-P1-1 (最小业务闭环)
├─ INCIDENT ................................. 下一个 ⭐
├─ ACTION_RESOLVE
├─ TURN_END
└─ LOOP_END_CHECK (框架已通)

Phase 2 (数据层) ........................... 并行或 P1-1 后
├─ P2-0: identity_registry / incident_registry
├─ P2-1: module_loader (first_steps + basic_tragedy_x)
└─ P2-2/P2-3: 控制器接线

Phase 1-P1-2 (模组配置接线) .............. P2-1 完成后
└─ has_final_guess 配置化 (解决 DoD-5)

Phase 1-P1-3 (事件总线接线)
├─ 发布死亡/失败/轮回终止事件
└─ 接入能力触发链

Phase 1-P1-4 (测试兜底 + DoD-4)
├─ 同时裁定逻辑（军人阻止死亡分流）
└─ 关键分支回归测试
```

**建议开始顺序：**
1. **Phase 1-P1-1 INCIDENT** (独立，易验证) → **Action Resolve** → **TURN_END** → **LOOP_END_CHECK**
2. **Phase 2 (并行或串行)** → P2-1 完成后马上做 Phase 1-P1-2
3. **Phase 1-P1-3/P1-4** (后续)

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

**C-1. 角色特性（trait_rule）**

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
| **UP主** | 首次事件当天turn_end放EX牌 | `PLACE_EX_CARD` 已有，但触发条件"本轮首次事件发生当天"需新增 Condition 类型 `first_incident_day` | |
| **黑猫** | 当事人事件效果变为无现象 | 无需新原语 | 事件resolver执行效果前检查当事人角色特性，黑猫时将效果列表替换为 `[NO_EFFECT]`（已有该EffectType） |
| **御神木** | 主人公能力阶段可将自身1枚指示物移动至同区域另1名角色；带无视友好时改为剧作家强制使用 | `MOVE_TOKEN` — 跨角色指示物移动（enums.py 已预留，无实现） | 新增 mutation type；需区分主人公/剧作家发起方 |

**C-2. 友好能力（goodwill_ability）**

| 角色 | 能力描述 | 缺失原语 | 建议 |
|---|---|---|---|
| **仙人** 友好1 | 复活同一区域1具尸体 | `REVIVE_CHARACTER` | DeathResolver / GameState 增加复活路径；复活时放置X枚友好（X为剧本设定值） |
| **异界人** 友好2 | 复活同一区域1具尸体 | `REVIVE_CHARACTER`（同上） | 同上 |
| **军人** 友好2 | 本轮回中主人公不会死亡 | `PROTAGONIST_PROTECT` | 写入 `state.soldier_protection_active = True`（字段已预留）；DeathResolver 检查此标志 |
| **刑警** 友好1 | 公开本轮已发生事件的当事人 | `REVEAL_INCIDENT_PERPETRATOR` | 新增 EffectType；读取 `state.incidents_occurred_this_loop` 匹配 perpetrator |
| **神灵** 友好1 | 公开1个事件的当事人（含未发生的） | `REVEAL_INCIDENT_PERPETRATOR`（同上，但范围含未发生事件） | 同上，扩展 target 范围 |
| **手下** 友好1 | 本轮回中该角色为当事人的事件不会发生 | `SUPPRESS_INCIDENT` | 新增 EffectType；写入 `IncidentSchedule.suppressed` 标志；IncidentHandler 检查 |
| **情报商** 友好1 | 公开1条主人公未声明的规则X | `REVEAL_RULE_X` | 新增 EffectType；需维护"已公开规则X列表"状态（GameState 新增字段） |
| **医生** 友好2 | 本轮回住院患者不再拥有禁行区域 | `LIFT_FORBIDDEN_AREAS` | 新增 EffectType；写入临时状态（`state.lifted_forbidden_areas: set[str]`）；移动resolver检查 |
| **小女孩** 友好1 | 本轮回中该角色不再拥有禁行区域 | `LIFT_FORBIDDEN_AREAS`（同上，针对单角色） | 同上，target 为角色 ID |
| **AI** 友好1 | 选择1个已公开事件，立即处理其效果（当事人默认为AI） | `TRIGGER_INCIDENT_EFFECT` | 新增 EffectType；重入 IncidentHandler 的效果执行路径 |
| **UP主** 友好1 | 同区域另1名角色+1友好-1不安；可将其EX牌转移至同区域另1名角色 | `MOVE_EX_CARD` | 新增 EffectType；需 EX牌数据结构（MZ/AHR 模组依赖） |
| **幻想** 友好2 | 将该角色从版图上移除 | `REMOVE_FROM_BOARD` | 新增 EffectType；设置 `ch.is_removed = True`（字段已存在），区别于死亡 |
| **妹妹** 友好1 | 强制同区域1名成人使用1个友好能力，无视友好数与无视友好特性 | `FORCE_ABILITY_USE` | 需新建"触发另一角色能力"的连锁机制；ability_resolver 需支持被动触发模式 |
| **从者** 友好1 | 将另1名角色追加为本轮回特性适用对象（等效为大人物/大小姐） | `EXTEND_TRAIT_TARGET` | 新增运行时状态 `state.trait_target_overrides: dict`；`FOLLOW_MOVEMENT`/`SUBSTITUTE_DEATH` 检查此表 |
| **模仿犯** 友好1 | 公开场上与该角色身份相同的所有角色名 | 查询型输出操作 | 新增 EffectType 或特殊信息输出路径；读取所有角色 identity_id 匹配 |
| **班长** 友好1 | 队长回收1张已使用完毕的行动牌至手牌 | `RETURN_CARD`（enums.py 已预留，无实现） | 新增 mutation type；从 `placed_cards` 或已用标记中找回目标牌 |
| **鉴别员** 友好1 | 在同区域2名角色之间移动1枚任意指示物 | `MOVE_TOKEN`（enums.py 已预留，无实现） | 新增 mutation type；需三目标选择（源角色A、目标角色B、指示物类型） |
| **鉴别员** 友好2 | 公开1具尸体的身份 | `REVEAL_IDENTITY` 对死亡角色的扩展 | 当前 REVEAL_IDENTITY 只对存活角色；扩展为允许 target 为死亡角色 |
| **转校生** 友好1 | 将同区域另1名角色身上1枚密谋替换为友好 | `MOVE_TOKEN`（跨类型，同上） | 同上，特化为密谋→友好转换 |
| **上位存在** 友好1 | 往同区域任意1名角色放置1枚希望**或**绝望（二选一） | chooser 需支持选择指示物类型 | 扩展 `Effect.chooser` 机制，支持 `choose_token_type`；与学者 trait_rule 同一机制 |

#### D. 剧本制作约束（非运行时效果）

以下约束在剧本制作阶段校验，不进入结算管线；角色侧写入 `script_constraints`，规则侧由规则定义直接驱动 `GAME_PREPARE` 校验：

| 角色 | 约束 |
|---|---|
| 妹妹 | 不可分配带有无视友好身份特性的身份 |
| AI | 不能分配为平民 |
| 局外人 | 不参与规则身份分配，分配模组中存在且规则未使用的身份 |
| 模仿犯 | 不参与规则身份分配，复制剧本中另一角色的身份（无视上限） |
| 临时工? | 身份与事件配置与临时工一致 |

#### 小结

- A+B 类覆盖了约 **10 个**角色特性，可完全数据驱动
- C-1 类（角色特性）需新增约 **12 个**机制（新 EffectType / resolver 钩子 / Condition 类型）
- C-2 类（友好能力）需新增约 **20 个**机制，其中部分（`MOVE_TOKEN`、`RETURN_CARD`）与C-1共享
- D 类约 **5 个**剧本制作约束，在脚本校验层处理
- **FS+BTX 优先实现**：`REVIVE_CHARACTER`（仙人/异界人）、`PROTAGONIST_PROTECT`（军人）、`SUPPRESS_INCIDENT`（手下）、`LIFT_FORBIDDEN_AREAS`（医生/小女孩）、`MOVE_TOKEN`（转校生/御神木/鉴别员）、`RETURN_CARD`（班长）
- **后续模组才需要**：`TRIGGER_INCIDENT_EFFECT`（AI）、`MOVE_EX_CARD`（UP主）、`FORCE_ABILITY_USE`（妹妹）、`EXTEND_TRAIT_TARGET`（从者）

---

## 5. 验证方式

- **单元测试**：每个 resolver 独立测试，覆盖上述边界案例
- **集成测试**：预设剧本完整走通，验证状态机流转
- **边界案例回归测试**：3.1-3.20 每条至少1个 test case
- **运行**：`python main.py` 启动 PySide6
