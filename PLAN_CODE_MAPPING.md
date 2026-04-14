# 惨剧轮回：计划与代码映射（开发导航）

本文件用于把 `PLAN.md` 的目标拆解到当前代码库的真实落点，方便后续按模块推进。

---

## 1) 当前代码基线（截至当前仓库）

- 已有核心目录：`engine/`、`ui/`、`tests/`
- 已有规则文档：`tragedy_loop_game_rules.md`、`tragedy_loop_appendix.md`
- 已有实现风格：以 dataclass + resolver + phase handler 为主，架构方向与 `PLAN.md` 一致

### 完成度概览

- **已搭建骨架**
  - 状态机骨架：`engine/state_machine.py`
  - 游戏状态聚合根：`engine/game_state.py`
  - 控制器调度骨架：`engine/game_controller.py`
  - 阶段处理器骨架：`engine/phases/phase_base.py`
  - 原子结算骨架：`engine/resolvers/atomic_resolver.py`
  - 死亡处理骨架：`engine/resolvers/death_resolver.py`
  - 事件总线：`engine/event_bus.py`
  - 信息边界过滤：`engine/visibility.py`
  - 核心模型：`engine/models/*.py`
- **未落地/待补**
  - 多数阶段业务规则（TODO）
  - 规则/身份/事件注册体系（`engine/rules/` 基本空）
  - 输入回调闭环（`WaitForInput.callback` 目前未形成完整链）
  - tests 基本空白

---

## 2) PLAN Phase 与现有代码映射

## Phase 0：基础设施 + 数据

### PLAN 对应项

- `models/enums.py`、`character.py`、`board.py`、`cards.py`、`script.py`、`identity.py`、`incident.py`
- `data/*.json`（board/cards/characters/modules）

### 当前代码映射

- 已实现（代码模型层）
  - `engine/models/enums.py`
  - `engine/models/character.py`
  - `engine/models/board.py`
  - `engine/models/cards.py`
  - `engine/models/script.py`
  - `engine/models/identity.py`
  - `engine/models/incident.py`
- 未实现（数据层）
  - `data/` 目录不存在
  - `module_loader`、registry 未实现

### 结论

- **模型层：基本可用（约 70%）**
- **数据驱动层：未开始（0%）**

---

## Phase 1：状态机 + 核心引擎

### PLAN 对应项

- 状态机流转、分支、虚线跳转
- GameController 调度循环
- 原子结算三步法（读-写-触发）
- 死亡链与终局裁定

### 当前代码映射

- 状态机：`engine/state_machine.py`（已实现主流程）
- 控制器：`engine/game_controller.py`（已实现主循环）
- 原子结算：`engine/resolvers/atomic_resolver.py`（已实现框架 + 部分效果）
- 死亡链：`engine/resolvers/death_resolver.py`（护卫/不死/死亡）
- 阶段入口：`engine/phases/phase_base.py`（handler 和 signal 框架）

### 关键缺口

- `WaitForInput` 没有完整 callback 回填机制，输入后无法稳定继续推进
- `phase_base.py` 多阶段为 TODO（action/ability/incident/turn_end/loop_end_check）
- `has_final_guess` 在控制器中写死为 `True`，未接 `Script.module`
- 事件触发链与身份能力触发尚未注册到 event bus

### 结论

- **Phase 1 骨架完成，业务未闭环（约 45%~55%）**

---

## Phase 2：行动牌系统

### PLAN 对应项

- 行动牌放置合法性
- 翻牌结算顺序（先移动后其他）
- 禁止类卡牌交互

### 当前代码映射

- 数据模型：`engine/models/cards.py`（有 card/placement/hand）
- 阶段入口：`MastermindActionHandler`、`ProtagonistActionHandler`、`ActionResolveHandler`（在 `phase_base.py`）
- 结算执行：尚无 `action_resolver.py`

### 关键缺口

- 放置规则未实现（3+3 放置、叠放限制、尸体目标限制）
- 移动与禁止类交互未实现
- 每轮一次牌回收/弃置完整规则未实现

### 结论

- **Phase 2 仅模型与入口，核心逻辑未实现（约 15%）**

---

## Phase 3：身份与能力系统（FS + BTX）

### PLAN 对应项

- 身份能力声明、强制/任意能力
- 拒绝逻辑
- 触发窗口与次数限制

### 当前代码映射

- 能力/效果模型：`engine/models/identity.py`
- 触发入口：`PlaywrightAbilityHandler`、`ProtagonistAbilityHandler`
- 事件总线可承载触发：`engine/event_bus.py`

### 关键缺口

- `ability_resolver.py` 不存在
- `identity_registry.py` 不存在
- 身份定义数据未落地到 JSON/注册表
- 拒绝逻辑与信息边界公告未打通

### 结论

- **Phase 3 模型预留到位，机制未实现（约 20%）**

---

## Phase 4：事件系统

### PLAN 对应项

- 事件发生判定
- 事件效果结算
- 当事人/群众事件/无现象处理

### 当前代码映射

- 事件模型：`engine/models/incident.py`
- 调度入口：`IncidentHandler`

### 关键缺口

- `incident_resolver.py` 不存在
- 发生判定（当事人存活 + 不安阈值）未实现
- 事件文本效果未映射到 Effect 列表

### 结论

- **Phase 4 仅模型准备（约 10%）**

---

## Phase 5：基础 UI

### PLAN 对应项

- 标题、剧本配置、游戏主界面、阶段切换、结果页
- board/character/card/log 组件

### 当前代码映射

- `ui/` 目录仅 `__init__.py` 和空子包
- `UICallback` 接口在 `engine/game_controller.py` 已预留

### 结论

- **Phase 5 尚未开始（约 5%）**

---

## Phase 6：端到端可玩

### 当前状态

- 缺乏最小可玩链路（从开局到至少一个轮回完成）
- `tests/` 无回归测试保证

### 结论

- **Phase 6 未开始（0%）**

---

## 3) 规则边界案例与代码落点（PLAN 3.x 对照）

## 3.1 原子结算与同时裁定

- 代码落点：
  - `engine/resolvers/atomic_resolver.py`
  - `engine/resolvers/death_resolver.py`
- 现状：
  - 同时裁定框架存在（死亡 vs 失败优先级）
  - 触发收集机制缺“身份触发注入”

## 3.2 医院事故多人死亡

- 代码落点：
  - 未来应在 `incident_resolver.py` + `atomic_resolver.py`
- 现状：
  - 可通过 EffectType 组合表达
  - 事件层尚未实现，无法跑通

## 3.3 / 3.12 turn_end 能力顺序

- 代码落点：
  - `TurnEndHandler`（`phase_base.py`）
  - 未来 `ability_resolver.py`
- 现状：
  - 只有注释，无执行逻辑

## 3.4 / 3.5 杀人狂与护卫

- 代码落点：
  - `death_resolver.py`（护卫已实现）
  - `TurnEndHandler`（杀人狂触发未实现）

## 3.20 信息边界

- 代码落点：
  - `engine/visibility.py`
- 现状：
  - 主体过滤已实现，公告机制已预留
  - 公告与真实 mutation 管道尚未全接

---

## 4) 建议开发顺序（按“最小可玩闭环”）

1. **打通输入回调闭环（P0）**
   - 让 `WaitForInput.callback` 能被 `provide_input()` 正常续跑
2. **完成最小阶段链路（P0）**
   - `ActionResolve` / `Incident` / `LoopEndCheck` 先做最小规则
3. **接入模块配置（P0）**
   - 用 `Script.module_id` 控制 `has_final_guess`、EX 槽策略
4. **补规则注册层（P1）**
   - `engine/rules/module_loader.py`、`identity_registry.py`、`incident_registry.py`
5. **补 resolver（P1）**
   - `action_resolver.py`、`ability_resolver.py`、`incident_resolver.py`
6. **测试先行（P0/P1 同步）**
   - 状态机流转、同时裁定、护卫/军人、loop_end_check 分支

---

## 5) 文件级 TODO 入口（可直接按文件开工）

- `engine/game_controller.py`
  - 接入 `WaitForInput.callback` 完整生命周期
  - `has_final_guess` 改为读 `state.script`/module 配置
- `engine/phases/phase_base.py`
  - 拆分/补全各阶段业务逻辑（至少最小可跑）
- `engine/resolvers/atomic_resolver.py`
  - 补齐 Phase1 必需 EffectType；将公告输出与 visibility 对接
- `engine/resolvers/death_resolver.py`
  - 增加运行时特性派生（不安定因子、纸老虎等）入口
- `engine/rules/`（新增实现）
  - `rule_base.py`
  - `module_loader.py`
  - `identity_registry.py`
  - `incident_registry.py`
- `tests/`（新增）
  - `test_state_machine.py`
  - `test_atomic_adjudication.py`
  - `test_turn_end_killer.py`
  - `test_loop_end_check.py`

---

## 6) 快速判断“是否可进入 Phase 2+”的门槛

满足以下 5 条即可进入动作/能力大规模开发：

- 能从 `GAME_PREPARE` 跑到 `LOOP_END_CHECK`
- `WaitForInput` 能至少完成一次“输入 -> 继续执行”
- `LoopEndCheck` 能正确三分支
- 同时裁定（死亡/失败/军人）有单测
- 至少 1 个最小剧本可跑通单轮回

