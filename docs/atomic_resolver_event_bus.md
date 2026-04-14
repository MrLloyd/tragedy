# AtomicResolver 与 EventBus

本文说明 `engine/resolvers/atomic_resolver.py` 与 `engine/event_bus.py` 的职责、关联方式，以及一次 `resolve` 运行时如何与总线交互。

---

## 1. EventBus 是什么

- **作用**：引擎内部的**发布-订阅**总线，用于解耦「状态已发生的事实」与「后续要响应的逻辑」（能力、裁定日志、调试等）。
- **范围**：**纯游戏逻辑事件**，与 UI 层事件无关（见 `event_bus.py` 模块注释）。
- **核心类型**：
  - `GameEventType`：事件种类（角色死亡、指示物变化、身份公开、阶段/轮回等）。
  - `GameEvent`：`event_type` + `data`（`dict`，常用键见 `GameEvent` 的 dataclass 注释）。
- **行为**：
  - `emit(event)`：先把事件追加到内部 **`_log`**，再**同步**调用该类型下所有 `subscribe` 注册的处理器。
  - 无异步队列；调用栈在 `emit` 调用者内部展开。

---

## 2. AtomicResolver 是什么

- **作用**：实现规则里的 **「读 → 写 → 触发」** 三步法（见 `AtomicResolver` 类文档字符串）。
- **输入**：真实 `GameState`（会被修改）、声明式 `Effect` 列表（定义见 `engine/models/identity.py` 的 `Effect`）。
- **输出**：`ResolutionResult`（mutations、终局 `outcome`、公告等）。

`resolve(state, effects, sequential=False)` 为入口：

- `sequential=False`：**同时生效**，走 `_resolve_simultaneous`。
- `sequential=True`：**顺序结算**（含「随后」语义），对每个 effect 再调 `_resolve_simultaneous`。

---

## 3. 二者如何关联

### 3.1 生命周期与依赖注入

- `EventBus` 由 **`GameController`** 在构造时创建：**每局游戏一个实例**。
- 同一实例注入 **`AtomicResolver(event_bus, death_resolver)`**。
- `AtomicResolver` **不创建**总线，只持有引用并在状态写入等时机 **`emit`**。

对应代码：`engine/game_controller.py` 中 `self.event_bus = EventBus()`、`AtomicResolver(self.event_bus, self.death_resolver)`。

### 3.2 角色分工

| 组件 | 角色 |
|------|------|
| `EventBus` | 接收 `emit`，维护事件日志，分发给订阅者。 |
| `AtomicResolver` | **发布方**：在「状态已写入」或「死亡已裁定」等节点调用 `emit`；**不**负责 `subscribe`（其它模块若需监听，在适当时机注册）。 |

---

## 4. 运作方式：一次 `resolve` 与 `emit` 的时机

### 4.1 同时生效路径（`_resolve_simultaneous`）

1. **读（plan）**：`state.snapshot()` 上 `_plan_effect`，得到 `Mutation` 列表；**不修改真实状态，不 `emit`**。
2. **写（apply）**：对每个 `mutation` 调用 `_apply_mutation(state, mutation)`；**此处根据 mutation 类型更新 `GameState`，并在若干分支内 `event_bus.emit(...)`**。
3. **触发（trigger）**：`_process_triggers` 处理死亡连锁等；过程中可能再次 `_apply_mutation`，因此 **`emit` 也可能在触发阶段再次出现**。死亡确认后还会在收集触发时额外 `emit` `CHARACTER_DEATH`（见下表）。

### 4.2 顺序路径（`_resolve_sequential`）

对每个 `effect` 依次调用 `_resolve_simultaneous(state, [effect])`，三步法（含 `emit`）按效果段重复执行。

### 4.3 `AtomicResolver` 当前会 `emit` 的事件（实现位置：`_apply_mutation` / `_collect_triggers_from_mutation`）

| 事件类型 | 典型触发条件 |
|----------|----------------|
| `TOKEN_CHANGED` | 角色或版图指示物增减写入成功 |
| `CHARACTER_MOVED` | 角色区域更新成功 |
| `IDENTITY_REVEALED` | 身份被公开（`revealed`） |
| `EX_GAUGE_CHANGED` | EX 槽数值变更 |
| `CHARACTER_DEATH` | 死亡经 `DeathResolver` 裁定且结果为「已死亡」等（见源码中 `DeathResult.DIED` 分支） |

未列出的 `GameEventType` 可能由引擎其它模块在未来或其它路径 `emit`。

---

## 5. 语义要点

- **`emit` 表示引擎已承认该状态变更或事实**；适合作为裁定记录、回放、测试断言的依据。
- **计划了但未执行的 mutation**（未进入 `_apply_mutation`）**不会产生**对应事件。
- **`event_bus.log`**：每次 `emit` 都会追加，便于完整时间序；与是否有订阅者无关。

---

## 6. 与当前代码库的集成状态（维护时请核对）

- **`AtomicResolver.resolve` 的调用链**：阶段/行动解析若尚未接入，则 **`resolve` 可能尚未被游戏主循环调用**；总线侧 **`subscribe` 也可能尚未在其它模块注册**。以仓库内实际 `grep`/引用为准。
- **`PhaseHandler`** 已接收 `event_bus` / `atomic_resolver` 注入，具体阶段内是否调用 `resolve`，以 `engine/phases/` 与 `phase_base.py` 的实现为准。

若你修改 `emit` 时机或事件 `data` 契约，请同步更新本文档与相关测试/校验。
