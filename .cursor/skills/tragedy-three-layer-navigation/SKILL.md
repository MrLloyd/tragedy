---
name: tragedy-three-layer-navigation
description: >-
  Navigates the tragedy repo in three ordered layers—stable map (PLAN.md,
  PLAN_CODE_MAPPING.md), cheap symbol retrieval (ripgrep/grep), then narrow
  reads for behavior. Use when exploring tragedy, finding where rules live,
  tracing call flow, or when the user mentions 三层记忆, 先映射再检索再精读,
  or avoiding whole-file reads.
---

# Tragedy：三层记忆（映射 → 检索 → 精读）

同一任务内按顺序使用；上一层能回答的，不要跳到下一层「整文件重读」。

## 第一层：稳定导航（映射）

**问题**：某类规则/模块「在哪一层、哪个文件」实现？

**工具**：仓库根目录的 [`PLAN.md`](../../../PLAN.md)（架构与目录约定）+ [`PLAN_CODE_MAPPING.md`](../../../PLAN_CODE_MAPPING.md)（计划与真实代码落点）。

先查映射，再动代码。

## 第二层：定位符号（检索）

**问题**：类名、函数名、字符串常量、枚举值出现在哪里？

**工具**：`rg` / `grep`（精确、便宜）。优先精确模式；必要时再用语义搜索补漏。

得到文件路径与行号后，再决定读哪一段。

## 第三层：理解行为（精读）

**问题**：这段逻辑怎么串起来？条件分支与调用关系是什么？

**工具**：小范围 `read_file`（只读相关区间）、或语义搜索定位段落后再局部读。

禁止：映射和检索已经能定锚点时，仍反复 `read_file` 整文件。

## 原则（同一任务）

| 若已足够 | 则避免 |
|-----------|--------|
| 映射回答了「在哪个模块/文件」 | 不先翻遍 `engine/` 大目录盲读 |
| grep 给出了定义与调用点 | 不整文件通读同一文件多次 |
| 只需确认几行上下文 | 不默认读满 500+ 行 |

**升级读法**：从映射/grep 得到的**路径 + 符号**出发，只扩大阅读范围到能回答当前问题为止。
