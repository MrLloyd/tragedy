# 惨剧轮回：计划与代码映射（开发导航）

本文件把 **`PLAN.md` 中的阶段与主题** 映射到**仓库里的真实路径**，便于从「计划」跳到「代码」、从「代码」反查「计划」。  
**单一事实源**：里程碑与勾选状态以 [`PLAN.md`](PLAN.md) 为准；本文侧重**落点与缺口**。

---

## 路径速查（代码 → `PLAN.md`）

| 路径 / 区域 | 主要对应 `PLAN.md` |
|-------------|-------------------|
| `data/*.json`、`data/modules/*.json` | §2 Phase 0（数据与契约） |
| `engine/validation/__main__.py`, `runner.py`, `static_data.py`, `modules.py`, `common.py` | §2 Phase 0（校验入口：`python -m engine.validation`） |
| `tests/test_data_validation.py` | §2 Phase 0（数据校验回归测试） |
| `engine/models/board.py`, `cards.py`, `character.py`, `enums.py` | §2 Phase 0（基础领域模型）|
| `engine/models/effects.py`, `ability.py` | §2 Phase 4（通用声明式条件/效果/能力模型） |
| `engine/models/identity.py`, `incident.py` | §2 Phase 4（身份与事件定义模型） |
| `engine/rules/character_loader.py` | §2 Phase 4（角色数据层 / 简易角色系统前置） |
| `engine/models/script.py` | §2 Phase 2（模组脚本对象，与 `module_loader` 配套） |
| `engine/state_machine.py` | §2 Phase 1（阶段流转与分支） |
| `engine/game_state.py` | §2 Phase 1（聚合根、`module_def` / `has_final_guess`、测试工厂等） |
| `engine/game_controller.py` | §2 Phase 1（调度循环）；§2 Phase 2（`start_game(module_id, ...)`） |
| `engine/phases/phase_base.py` | §2 Phase 1（各阶段 handler）；内含行动/事件等最小闭环 |
| `engine/resolvers/atomic_resolver.py` | §2 Phase 1；`PLAN.md` §3.1 同时裁定 |
| `engine/resolvers/death_resolver.py` | §2 Phase 1；`PLAN.md` §3.4 / §3.5 等 |
| `engine/event_bus.py` | §2 Phase 1（触发总线）；与身份/事件扩展相关 |
| `engine/visibility.py` | `PLAN.md` §3.20 信息边界 |
| `engine/rules/module_loader.py` | §2 Phase 2（`load_module`、`apply_loaded_module` → `GameState`） |
| `engine/rules/identity_registry.py` | §2 Phase 2（身份定义注册） |
| `engine/rules/incident_registry.py` | §2 Phase 2（事件定义注册） |
| `engine/rules/rule_base.py`（**尚未创建**） | `PLAN.md` 目录规划；待 Phase 2+ 按需落地 |
| `engine/resolvers/action_resolver.py`（**尚未创建**） | `PLAN.md` 目录规划；当前行动结算主要在 `atomic_resolver` + `phase_base` |
| `engine/resolvers/ability_resolver.py` | §2 Phase 4（统一能力入口：按角色友好 / 身份 / 规则 / 派生来源收集） |
| `engine/resolvers/incident_resolver.py`（**尚未创建**） | `PLAN.md` 目录规划；事件最小路径在 `phase_base` / `INCIDENT` |
| `tests/test_wait_for_input_loop.py` | §2 Phase 1 DoD（输入闭环） |
| `tests/test_incident_handler.py` | §2 Phase 1（事件阶段与裁定等） |
| `tests/test_module_apply.py` | §2 Phase 2（`build_game_state_from_module`、`start_game` 模组开局入口等） |
| `tests/test_validation_loader_integration.py` | §2 Phase 2（校验 + loader 联动） |
| `tests/test_registry_loader.py` | §2 Phase 2（registry + `load_module`） |
| `tests/test_character_loader.py`, `tests/test_ability_resolver.py` | §2 Phase 4（数据层与能力层回归） |
| `ui/widgets/`, `ui/controllers/`, `ui/screens/`（基础结构已有） | §2 Phase 5（UI 框架启动中） |

---

## 1) 当前代码基线（与仓库一致）

- **已有**：`engine/`（状态机、控制器、7 个模型文件、部分 resolver、`phases/phase_base.py`）、`data/`（board/cards/characters、modules）、`engine/rules/`（`module_loader`、`identity_registry`、`incident_registry`）、`engine/validation/`（6 个校验模块）、`tests/`（含 `test_module_apply` 等）、`ui/`（目录结构）。
- **规则文档**：`tragedy_loop_game_rules.md`、`tragedy_loop_appendix.md`。
- **风格**：dataclass + `atomic_resolver` + `phase_base` 阶段处理器；与 `PLAN.md` 架构一致。

### 相对 `PLAN.md` 的常见缺口（维护时核对）

- **`has_final_guess`**：由 `GameState.module_def`（经 `apply_loaded_module` 装配）与 `game_controller` 读取；开局须显式装配模组数据。
- **独立 resolver 文件**：`ability_resolver` 已建立统一入口；`action_resolver` / `incident_resolver` 仍未从 `phase_base` + `atomic_resolver` 中拆出（见上表）。
- **UI**：未启动。

---

## 2) `PLAN.md` Phase 与代码映射

章节编号与 [`PLAN.md`](PLAN.md) **§2 开发阶段**一致。

### Phase 0：基础设施 + 数据

| PLAN 主题 | 代码落点 |
|-----------|----------|
| 基础模型 | `engine/models/board.py`、`cards.py`、`character.py`、`enums.py` |
| 静态数据 | `data/board.json`、`data/cards.json`、`data/characters.json`、`data/modules/first_steps.json`、`data/modules/basic_tragedy_x.json` |
| 校验框架 | `engine/validation/__main__.py`、`runner.py`、`static_data.py`、`modules.py`、`common.py` |
| 校验测试 | `tests/test_data_validation.py` |

**结论**：数据与校验链路已落地；后续变更需保持与 `PLAN.md` Phase 0 勾选一致。

### Phase 1：状态机 + 核心引擎

| PLAN 主题 | 代码落点 |
|-----------|----------|
| 状态机 | `engine/state_machine.py` |
| 控制器主循环 | `engine/game_controller.py` |
| 游戏状态 | `engine/game_state.py` |
| 阶段逻辑 | `engine/phases/phase_base.py` |
| 原子结算、同时裁定 | `engine/resolvers/atomic_resolver.py` |
| 死亡链 | `engine/resolvers/death_resolver.py` |
| 事件总线 | `engine/event_bus.py` |
| 信息过滤 | `engine/visibility.py` |
| 回归测试 | `tests/test_wait_for_input_loop.py`、`tests/test_incident_handler.py` |

**缺口（见 `PLAN.md` Phase 1 未完成项）**：例如更多 Phase 1 核心测试等。

### Phase 2：数据层完善（loader / registry / 与控制器联动）

| PLAN 主题 | 代码落点 |
|-----------|----------|
| 脚本模型 | `engine/models/script.py`（模组脚本对象） |
| 模组加载 | `engine/rules/module_loader.py`（`load_module` → `LoadedModule`） |
| 身份 / 事件注册表 | `engine/rules/identity_registry.py`、`engine/rules/incident_registry.py` |
| 配置接线 | `build_game_state_from_module` / `apply_loaded_module` + `GameState.module_def`；`GameController.start_game(module_id, ...)`；`game_controller` 使用 `state.has_final_guess`；各 phase 读 `state.identity_defs` / `incident_defs` |

**缺口**：更完整的剧本装配（角色表、`Script.rule_y` / `rules_x` 自模组等）可在后续 Phase 继续接；更多「模组差异」字段若需可继续从 `ModuleDef` 下放到运行时。

### Phase 3：行动牌系统

| PLAN 主题 | 代码落点 |
|-----------|----------|
| 行动牌模型 | `engine/models/cards.py` |
| 行动阶段与最小结算 | `engine/phases/phase_base.py`（如 `ACTION_RESOLVE` 相关 handler）、`engine/resolvers/atomic_resolver.py` |
| 专用行动 resolver | 规划中：`engine/resolvers/action_resolver.py`（**未建**） |

### Phase 4：身份与能力 + 事件系统

| PLAN 主题 | 代码落点 |
|-----------|----------|
| P4-1 角色数据层 / 简易角色系统 | `engine/models/character.py`、`engine/rules/character_loader.py` |
| 身份 / 能力 / 效果模型 | `engine/models/identity.py` |
| P4-2 能力统一入口 | `engine/resolvers/ability_resolver.py`（统一入口，按角色友好 / 身份 / 规则 / 常驻派生分层） |
| P4-3 身份 / 规则能力补齐 | `data/modules/*.json`、`engine/rules/module_loader.py`、`identity_registry.py` |
| 事件模型 | `engine/models/incident.py` |
| 定义加载与注册 | `engine/rules/module_loader.py`、`identity_registry.py`、`incident_registry.py` |
| P4-4 阶段接线 | `engine/phases/phase_base.py`、`event_bus.py` |
| 纯结算层 | `engine/resolvers/atomic_resolver.py` |
| 专用 resolver | `ability_resolver.py`（已建，待 Phase 4 继续扩展）、`incident_resolver.py`（**未建**） |
| Phase 4 测试 | `tests/test_character_loader.py`、`tests/test_ability_resolver.py` |

### Phase 5：基础 UI

| PLAN 主题 | 代码落点 |
|-----------|----------|
| UI 框架结构 | `ui/widgets/`、`ui/controllers/`、`ui/screens/`（目录结构已建，awaiting 实现） |
| 与引擎协作接口 | `game_controller.py` 中预留的 UI 协作接口 |

- **规划**：见 `PLAN.md` 目录树中 `ui/`。
- **现状**：目录结构已建立；具体 widget、screen、controller 实现待补充。

### Phase 6：端到端可玩

- 依赖 Phase 1–4 闭环 + Phase 5（若需要图形界面）；当前以引擎与测试为主要验证手段。

---

## 3) `PLAN.md` §3 规则边界案例 → 代码锚点

| §3 小节 | 主题 | 优先代码落点 |
|---------|------|----------------|
| 3.1 | 原子结算与同时裁定 | `engine/resolvers/atomic_resolver.py` |
| 3.2 | 医院事故多人死亡 | `atomic_resolver` + 未来 `incident_resolver` / 事件效果 |
| 3.3 | turn_end 能力顺序 | `phase_base.py`（`TURN_END`）、未来 `ability_resolver.py` |
| 3.4 / 3.5 | 杀人狂与护卫 | `death_resolver.py`、`phase_base.py` |
| 3.20 | 信息边界 | `engine/visibility.py` |

---

## 4) 建议开发顺序（与 `PLAN.md` 一致时可对齐）

1. **Phase 2 接线**：`game_controller` / `Script` / 模组与 `has_final_guess`、注册表贯通（满足 `PLAN.md` Phase 1 DoD-5 与 Phase 2 DoD）。
2. **P4-1 简易角色层**：先让角色友好能力与必要字段进入能力系统，不在此步完成完整角色系统。
3. **P4-2 统一能力层**：以 `ability_resolver` 为统一入口，按角色友好 / 身份 / 规则 / 派生来源分层。
4. **P4-3 / P4-4**：先补 FS / BTX 身份与规则能力，再接 `Playwright` / `Protagonist` / `TurnEnd` / `LoopStart` handler。
5. **Phase 5 UI**：数据与引擎稳定后再接 PySide6。
6. **测试**：随功能扩展补充 `tests/`，与 `PLAN.md` Phase DoD 对齐。

---

## 5) 按文件开工的 TODO 入口（快速跳转）

| 文件 | 典型任务（详见 `PLAN.md`） |
|------|---------------------------|
| `engine/game_controller.py` | 模组配置、`has_final_guess`、与 UI/输入的长期协作 |
| `engine/phases/phase_base.py` | 各阶段业务完整度、与 resolver 拆分 |
| `engine/resolvers/atomic_resolver.py` | Effect 与公告、与 visibility 对齐 |
| `engine/resolvers/death_resolver.py` | 规则边界案例（护卫、批量死亡等） |
| `engine/rules/module_loader.py` | 新模组字段、与 validation 一致 |
| `engine/rules/identity_registry.py` / `incident_registry.py` | 与加载器、运行时查询一致 |
| `tests/*.py` | 新回归用例 |

---

## 6) 文档维护

- 修改架构或新增核心文件时：**同步更新本节路径表与 Phase 映射**，并核对 [`PLAN.md`](PLAN.md) 中的勾选与日期。
- 若 `PLAN.md` 调整 Phase 含义，以 `PLAN.md` 为准更新本文件章节 **§2** 的对应关系。
