# 引擎重要类、`Mutation` 与 `Enum` 说明

本文整理自引擎相关问答，共三部分：**重要类（数据 / 执行）**、`Mutation` 与 **`Enum` 的关系**、**为何要使用 `Mutation`**。便于与 `docs/atomic_resolver_event_bus.md` 对照阅读。

---

## 1. 引擎中重要的类：数据储存 vs 实际执行

以下覆盖 `engine` 包内与对局直接相关、较重要的类型（**不含**纯校验用的 `engine/validation/*`）。

### 1.1 数据储存（状态与规则模型）

这些类主要**承载**对局状态、剧本与规则数据；多数是可变 dataclass，随游戏推进被读写。

| 类 | 作用简述 | 主要储存内容 |
|----|----------|----------------|
| **`GameState`** | 对局**聚合根**，单一权威运行时状态 | 当前剧本 `Script`、轮回/天/阶段、队长、`characters`、`board`、手牌与 `placed_cards`、失败/死亡标记、`ex_gauge`、世界线等扩展位、事件追踪、`loop_history` 等（见 `game_state.py`） |
| **`LoopSnapshot`** | 单轮结束时的**跨轮回快照**条目 | 轮回号、EX、本轮回发生事件 id、各角色 `CharacterEndState` |
| **`Script`** | **剧本**（公开表 + 非公开表） | 模组 id、轮回/天数、公开事件列表与特殊规则文本、规则 Y/X、`CharacterSetup` 列表、`IncidentSchedule` 等 |
| **`ModuleDef` / `RuleDef` / `CharacterSetup`** | 模组、规则条、角色开局配置 | 模组元数据、规则身份槽与 `Ability`、角色 id 与分配身份、是否当事人等 |
| **`CharacterState`** | **单角色**运行时状态 | id、区域、指示物 `TokenSet`、生死/移除、身份与是否公开、特性/属性、不安限度、禁区、EX 牌与各类预留字段、能力使用计数等 |
| **`CharacterEndState`** | 轮回结束时的**精简角色快照** | 用于 `LoopSnapshot`：生死、指示物、是否公开身份、区域等 |
| **`TokenSet`** | 指示物**数值容器** | 六种指示物计数及增减查询 |
| **`BoardState` / `BoardArea`** | **版图**网格与区域状态 | 各 `AreaId` 的 `TokenSet`、诅咒/封锁等预留字段 |
| **`CardHand` / `ActionCard` / `CardPlacement`** | 手牌与**当回合放置** | 牌类型、归属、使用限制、放置目标与暗置/无效标记 |
| **`IncidentDef`** | **事件定义**（模组级，偏静态） | 事件 id、`Effect` 列表与是否顺序结算、额外 `Condition`、标签与 EX 相关字段 |
| **`IncidentSchedule`** | 剧本里**第几天、谁**触发哪条事件 | `incident_id`、`day`、当事人 id、运行时 `occurred` |
| **`Condition`** | 声明式**条件**（不求值结构本身） | `condition_type` + `params`，供规则引擎将来求值 |
| **`Effect`** | 声明式**效果原语** | `EffectType`、`target`、token/amount、`value`、可选 `Condition` |
| **`Ability`** | **身份/规则能力** | `AbilityType`/`AbilityTiming`、条件、`Effect` 列表、是否顺序、使用限制、是否可拒绝 |
| **`IdentityDef`** | **身份定义** | id、特性、`Ability` 列表、数量上限等 |
| **`VisibleCharacter` / `VisibleGameState`** | 给 UI/玩家的**可见子集**（不是权威状态） | 按角色过滤后的区域、指示物、身份显示字符串、公开属性、版图指示物摘要等（由 `Visibility` 生成） |

**说明**：`engine/models/enums.py` 中为大量 **`Enum`**（阶段、区域、牌类型、`EffectType` 等），属于**类型与常量**，贯穿上述模型。

### 1.2 实际执行（流程、结算与副作用）

这些类主要**驱动**游戏推进、改状态或产生副作用；不替代 `GameState` 作为唯一权威存储，但会**读写**它。

| 类 | 作用简述 | 「执行」什么 / 注意 |
|----|----------|---------------------|
| **`GameController`** | **调度中枢**：状态机 + 阶段 + UI 回调 | `start_game`、`provide_input`、按阶段 `execute`、处理 `PhaseSignal`、轮回重置与游戏结束等 |
| **`StateMachine`** | **纯流程**：当前阶段 → 下一阶段 | `advance` 的线性表与 `TURN_END` / `LOOP_END_CHECK` 分支、`force_loop_end` 虚线跳转；**不含**业务规则细节 |
| **`PhaseHandler`**（及各具体子类） | **每个 `GamePhase` 一段逻辑** | `execute(state)` 返回 `PhaseComplete` / `WaitForInput` / `ForceLoopEnd`；内部可逐步接入打牌、结算、事件等 |
| **`PhaseComplete` / `WaitForInput` / `ForceLoopEnd`** | 阶段与控制器之间的**控制流信号** | 非持久状态，表达「推进 / 挂起 / 强制结束轮回」 |
| **`AtomicResolver`** | **原子结算**：读快照 → 写状态 → 触发链 | `resolve(state, effects, ...)`：**传入的 `state` 为真实 `GameState`，会被原地修改**；`resolve` → `_plan_effect` / `_apply_mutation` / `_process_triggers`；消费 `Effect`，产出 `ResolutionResult` |
| **`DeathResolver`** | **死亡责任链** | `process_death`：不死/护卫等 → 返回 `DeathResult`；与 `AtomicResolver` 的触发阶段衔接 |
| **`EventBus`** | **引擎内事件总线** | `emit` / `subscribe`；记录 `log`；**与 UI 事件无关** |
| **`GameEvent` + `GameEventType`** | 事件**载体与类型** | `AtomicResolver` 等在状态写入后 `emit` |
| **`Mutation` / `Trigger` / `ResolutionResult`** | 结算管道中的**中间结构** | 规划变更、排队触发、汇总结果；随一次 `resolve` 产生，通常不单独作为长期存储 |
| **`Visibility`** | **信息边界**（静态方法集合） | `filter_for_role`：从 `GameState` 生成剧作家/主人公可见的 `VisibleGameState` |
| **`UICallback`** | **UI 钩子接口** | `on_phase_changed`、`on_wait_for_input`、`on_game_over` 等；引擎调用，实现由外层提供 |

### 1.3 如何记不容易混

- **「这一局权威数据在哪」** → **`GameState`** 及其嵌套的 **`CharacterState` / `BoardState` / 手牌 / `Script`**。
- **「阶段怎么往下走」** → **`StateMachine` + `GameController` + `PhaseHandler`**。
- **「效果/死亡怎么落地」** → **`AtomicResolver` + `DeathResolver`，并通过 `EventBus` 发已发生事实**。
- **「玩家能看到什么」** → **`Visibility` → `VisibleGameState`**，不是第二份完整存档。

---

## 2. `Mutation` 具体做什么？`Enum`（`enums.py`）和它是什么关系？

### `Mutation` 的作用

`Mutation` 是 **`AtomicResolver` 内部的「单条待执行状态变更」**，把高层的 `Effect` 落成可执行、可遍历的小步操作。

字段大意：

- **`mutation_type: str`**：如 `"token_change"`、`"character_death"`、`"character_move"` 等（约定标签）。
- **`target_id`**：角色 id 或版图 id。
- **`details`**：该条变更的附加参数（如指示物类型、增量、移动目标等）。

**在流程里：**

1. **读（plan）**：`_plan_effect` 根据 `Effect` 与快照**不修改真实 `GameState`**，只生成若干 `Mutation`。
2. **写（apply）**：`_apply_mutation(state, mutation)` 按 `mutation_type` 分支，**真正修改 `GameState`**，并可能 `event_bus.emit`。
3. **触发（trigger）**：`_process_triggers` 基于已产生的 `Mutation` 收集死亡等连锁，可能再产生新 mutation 并再次 `_apply_mutation`。

**小结**：`Mutation` = 规划/记录「要改什么、改谁、细节参数」，连接声明式 `Effect` 与对 `GameState` 的原地修改；`ResolutionResult.mutations` 也会携带本批 `Mutation`，便于结果与调试。

注意：**`mutation_type` 是普通 `str`，不是 `enums.py` 里的枚举类型。**

### `enums.py` 里的 `Enum` 是什么？

`engine/models/enums.py` 集中定义 **`Enum`**，作为全引擎的固定取值集合，例如：

- **`GamePhase`**：状态机阶段。
- **`TokenType` / `AreaId` / `PlayerRole`**：指示物、区域、玩家侧。
- **`EffectType`**：声明式效果 `Effect.effect_type` 使用哪一种效果（放置/移除指示物、击杀、公开身份等）。
- 另有 **`AbilityTiming`、`AbilityType`、`DeathResult`** 等。

### 二者分工（与 `Mutation` 的关系）

| 层级 | 类型 | 作用 |
|------|------|------|
| 规则/数据输入 | `Effect` + **`EffectType`（Enum）** | 「规则上要执行哪种效果」 |
| 结算内部中间表示 | **`Mutation`（`mutation_type: str`）** | 「引擎里要落哪一类状态补丁」 |

`_plan_effect` 里对 **`EffectType`（Enum）** 做分支，再 `append(Mutation(mutation_type="token_change", ...))` 等——**Enum 管输入分类，`Mutation` 管内部补丁形状**。

---

## 3. 为何要使用 `Mutation`？

使用 `Mutation` 是为了把「先想清楚再动手」和「效果长什么样」拆开，让原子结算可控、可扩展。结合三步法，原因可概括为：

### 读与写分离（先规划，再改真实状态）

`_plan_effect` 只在 **`state.snapshot()`** 上计算，**不碰真实 `GameState`**，产出 `Mutation` 列表。写阶段再 `for m in planned: _apply_mutation(state, m)`。  
若没有中间结构，容易在规划阶段误改状态，或把解析与写入搅在同一套分支里。

### 支持「同时生效」语义

同时结算时，先在**同一份快照**上为所有效果生成 `Mutation`，再批量写入真实状态，规划依据一致；顺序结算则走 `sequential` 路径逐步调用。

### `Effect` 与 `GameState` 之间的中间表示（IR）

`Effect` + `EffectType` 偏声明式规则；真正改 `CharacterState` / `BoardState` / 死亡链时，用少量 **`mutation_type` + `target_id` + `details`** 表示「引擎补丁」，`_apply_mutation` 只认这一套。

### 触发链与结果汇总

`_process_triggers` 可基于 **`planned_mutations`** 收集触发；`ResolutionResult.mutations` 便于调试、日志或日后回放。

### 一句话

**`Mutation` 是在 `Effect`（规则层）与 `GameState`（权威状态）之间的一层稳定、可列举的补丁格式**，专门服务「读—写—触发」管线；不用也能写，但更难维护同时结算、快照规划与清晰的触发收集。

---

## 相关源码位置

- `engine/resolvers/atomic_resolver.py`：`Mutation`、`resolve`、`_plan_effect`、`_apply_mutation`、`_process_triggers`
- `engine/models/enums.py`：`EffectType` 等枚举
- `engine/models/identity.py`：`Effect`、`Ability`
- `engine/game_state.py`：`GameState`
- `engine/event_bus.py`：`EventBus`、`GameEvent`
- `engine/phases/phase_base.py`：`PhaseHandler`、`PhaseSignal`

与 **EventBus** 的配合见：`docs/atomic_resolver_event_bus.md`。
