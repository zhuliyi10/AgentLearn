# 02 - Plan-and-Execute 模式

## 学习目标

- 理解"先规划后执行"的 Agent 设计模式
- 实现 Planner（规划器）+ Executor（执行器）分离架构
- 掌握动态 Replan（重新规划）机制
- 理解 Plan-and-Execute 与 ReAct 的区别和适用场景

## 运行方式

```bash
python 03_agent_patterns/02_plan_and_execute.py
```

---

## 核心概念

### 1. 什么是 Plan-and-Execute？

Plan-and-Execute 的核心思想很直觉：**先想清楚要做什么，再动手**。

```
ReAct:            Thought → Action → Observation → Thought → Action → Observation → ...  (逐步推进)
Plan-and-Execute: [制定完整计划] → 步骤1 → 步骤2 → ... → 步骤N → [汇总报告]              (全局规划)
```

ReAct 像一个**边想边做**的人，每走一步都要停下来思考下一步。Plan-and-Execute 则像一个**项目经理**——先列出完整的工作计划，然后按部就班地执行，遇到问题才调整计划。

**关键认知：** 规划和执行是两个不同的能力，分开后各自可以做得更好。Planner 专注于全局策略，Executor 专注于单步执行。

### 2. 三阶段架构

```
┌─────────────────────────────────────────────────────────┐
│                      整体流程                            │
│                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Planner  │ →  │   Executor   │ →  │  Summarizer  │  │
│  │  规划器   │    │    执行器     │    │   汇总报告    │  │
│  └──────────┘    └──────────────┘    └──────────────┘  │
│       │               │                    │            │
│    输出 Plan      逐步执行步骤         汇总所有结果      │
│   (JSON 结构)    (调用工具或推理)      (生成最终回答)     │
│                                                         │
│                   ┌──────────────┐                      │
│                   │   Replanner  │  ← 步骤失败时触发     │
│                   │   重新规划    │                      │
│                   └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

| 阶段 | 角色 | 输入 | 输出 |
|------|------|------|------|
| **Planner** | 规划专家 | 用户目标 | 结构化的执行计划（JSON） |
| **Executor** | 执行者 | 单个步骤 + 前置结果 | 步骤执行结果 |
| **Replanner** | 调整专家 | 原计划 + 已执行结果 + 问题 | 调整后的新计划 |
| **Summarizer** | 总结者 | 所有步骤结果 | 最终报告 |

### 3. 与 ReAct 的对比

| 对比维度 | ReAct | Plan-and-Execute |
|----------|-------|------------------|
| 决策方式 | 逐步思考 | 先全局规划 |
| 推理深度 | 局部（当前步） | 全局（整体） |
| 适合任务 | 简单多步（2-5步） | 复杂多步（5+步） |
| 灵活性 | 高（随时调整） | 中（需触发 replan） |
| 效率 | 中（每步都调用 LLM 推理） | 高（规划一次，执行可确定性进行） |
| LLM 调用次数 | 每步 1 次 | 规划 1 次 + 每步 0~1 次 + 汇总 1 次 |
| 典型场景 | 问答、搜索、简单计算 | 研究报告、多步分析、复杂报告生成 |

---

## 代码实现详解

### Plan 数据模型（Pydantic）

与 ReAct 用纯文本解析不同，Plan-and-Execute 使用 **Pydantic 结构化输出**来表示计划：

```python
class PlanStep(BaseModel):
    step_id: int                    # 步骤编号
    description: str                # 步骤描述
    tool: str                       # 使用的工具名称，或 "none" 表示纯推理
    depends_on: list[int] = []      # 依赖的步骤编号

class Plan(BaseModel):
    goal: str                       # 总体目标
    steps: list[PlanStep]           # 执行步骤列表
```

**设计要点：**
- `depends_on` 字段描述了步骤间的**依赖关系**，使得执行器知道哪些步骤可以并行、哪些必须串行
- `tool` 可以是 `"none"`，表示这一步不需要工具，纯靠 LLM 推理（如分析、总结）
- 使用 Pydantic 模型让 LLM 输出**结构化 JSON**，而非脆弱的文本解析

### Planner：规划器

```python
def create_plan(goal: str) -> Plan:
    # 1. 将 Pydantic 模型转为 JSON Schema 字符串
    schema_str = json.dumps(Plan.model_json_schema(), ensure_ascii=False, indent=2)

    # 2. 调用 LLM，使用 response_format 强制 JSON 输出
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": PLANNER_PROMPT + f"\n\n请严格按以下 JSON Schema 输出:\n{schema_str}"},
            {"role": "user", "content": f"目标: {goal}\n\n请制定执行计划。"},
        ],
        response_format={"type": "json_object"},  # 关键：强制 JSON 格式
        temperature=0,
    )

    # 3. 用 Pydantic 解析验证
    return Plan.model_validate_json(response.choices[0].message.content)
```

**关键技术点：**
- `response_format={"type": "json_object"}` — 强制 LLM 输出合法 JSON，避免解析失败
- `Plan.model_json_schema()` — 自动生成 JSON Schema 传给 LLM，让它知道输出格式
- `Plan.model_validate_json()` — Pydantic 自动验证字段类型，不合法会报错

**与 ReAct 的对比：** ReAct 用文本解析提取 Action，这里用结构化 JSON 输出。后者更健壮，不会因格式问题导致流程中断。

### Executor：执行器

执行器处理两种类型的步骤：

```python
def execute_step(step: PlanStep, previous_results: dict[int, str]) -> str:
    # 构建上下文：当前步骤描述 + 依赖步骤的结果
    context = f"当前步骤: {step.description}\n"
    if step.depends_on:
        context += "之前步骤的结果:\n"
        for dep_id in step.depends_on:
            context += f"  步骤{dep_id}: {previous_results[dep_id][:200]}\n"

    if step.tool == "none":
        # 纯推理步骤 → 直接调用 LLM
        response = client().chat.completions.create(...)
        return response.choices[0].message.content
    else:
        # 工具步骤 → 提取参数 → 执行工具
        tool_args = extract_tool_args(step)
        result = execute_tool(step.tool, tool_args)
        return result
```

**两种步骤类型：**

| 类型 | `tool` 值 | 行为 | 示例 |
|------|-----------|------|------|
| 工具步骤 | `"search"` / `"calculate"` / `"get_time"` | 调用工具获取数据 | "搜索 Python 3.12 新特性" |
| 推理步骤 | `"none"` | LLM 纯文本推理 | "分析搜索结果，总结关键特性" |

### 参数提取

```python
def extract_tool_args(step: PlanStep) -> dict:
    desc = step.description.lower()
    if step.tool == "search":
        # 从描述中提取关键词：如 "搜索 Python 新特性" → {"query": "python 新特性"}
        for keyword in ["搜索", "查询", "查找"]:
            if keyword in desc:
                query = desc.split(keyword)[-1].strip()
                return {"query": query}
    elif step.tool == "calculate":
        # 用正则提取数学表达式
        ...
```

**注意：** 这是一个**简化实现**。实际项目中，应该让 LLM 根据步骤描述智能提取参数，而非用字符串匹配。这也是本代码的改进空间之一。

### Replan：动态重新规划

当某个步骤执行失败时，Replanner 会根据已有结果调整计划：

```python
def replan(original_plan: Plan, executed_results: dict[int, str], issue: str) -> Plan:
    context = f"原始目标: {original_plan.goal}\n\n"
    context += "已执行的步骤结果:\n"
    for step_id, result in executed_results.items():
        context += f"  步骤{step_id}: {result[:200]}\n"
    context += f"\n遇到的问题: {issue}\n"

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": REPLANNER_PROMPT + f"\n\nJSON Schema:\n{schema_str}"},
            {"role": "user", "content": context + "\n请调整计划。"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return Plan.model_validate_json(response.choices[0].message.content)
```

**Replan 原则：**
1. 保留已完成或有效的步骤
2. 修改失败或需要调整的步骤
3. 添加新步骤（如果需要）
4. 确保计划仍然可行

通过 `max_replans` 参数限制重新规划次数，防止无限循环。

### 主流程：plan_and_execute_agent

```python
def plan_and_execute_agent(goal: str, max_replans: int = 2) -> str:
    # === 阶段1: 规划 ===
    plan = create_plan(goal)

    # === 阶段2: 执行 ===
    executed_results = {}
    for step in plan.steps:
        try:
            result = execute_step(step, executed_results)
            executed_results[step.step_id] = result
        except Exception as e:
            if replan_count < max_replans:
                plan = replan(plan, executed_results, str(e))  # 调整计划
                replan_count += 1

    # === 阶段3: 生成最终报告 ===
    final_answer = client().chat.completions.create(
        messages=[
            {"role": "system", "content": "请根据执行结果，生成完整的最终报告。"},
            {"role": "user", "content": summary_context},
        ],
    )
    return final_answer
```

**三阶段清晰明了：** 规划 → 执行（含 replan） → 汇总。

---

## 完整执行流程示例

以演示问题为例：

```
目标: "了解 Python 3.12 新特性，计算学完需要多少天"

=== 阶段1: Planner 输出 ===
Plan:
  goal: "了解 Python 3.12 新特性并计算学习时间"
  steps:
    1. 搜索 Python 3.12 新特性 [工具: search]     依赖: []
    2. 分析搜索结果，列出主要新特性 [工具: none]    依赖: [1]
    3. 计算学习总时间 [工具: calculate]             依赖: [2]

=== 阶段2: Executor 逐步执行 ===
步骤1: search("Python 3.12 新特性") → 获取搜索结果 ✓
步骤2: LLM 分析 → "Python 3.12 主要有 8 个新特性..." ✓
步骤3: calculate("8 * 5 / 2") → 20.0 ✓

=== 阶段3: Summarizer 汇总 ===
"Python 3.12 包含 8 个主要新特性...如果每天学习2小时，需要约20天。"
```

---

## 结构化输出 vs 文本解析

| 对比维度 | ReAct（文本解析） | Plan-and-Execute（结构化输出） |
|----------|-------------------|-------------------------------|
| 输出格式 | 自由文本 | JSON（由 Pydantic Schema 约束） |
| 解析方式 | 字符串匹配 `line.startswith("Action:")` | `Plan.model_validate_json()` |
| 健壮性 | 较弱（格式容易漂移） | 较强（JSON Schema 强制约束） |
| 灵活性 | 高（LLM 自由表达思考） | 中（受 Schema 限制） |
| API 特性 | 无特殊要求 | `response_format={"type": "json_object"}` |

**选择建议：** 需要 LLM 自由推理时用文本解析（ReAct），需要可靠结构化数据时用 JSON 输出（Plan-and-Execute）。

---

## 实践经验

**Q: 为什么 Planner 和 Executor 要分开？**
A: 职责分离。Planner 用全局视角制定策略，不需要关心工具细节；Executor 专注执行单步，不需要考虑整体方向。分开后各自的 prompt 更简洁，效果更好。

**Q: `response_format={"type": "json_object"}` 是什么？**
A: OpenAI API 的参数，强制模型输出合法 JSON。配合 Pydantic 的 JSON Schema 使用，可以确保输出格式完全符合预期。注意：只有部分模型支持此参数。

**Q: `depends_on` 有什么用？**
A: 描述步骤间的依赖关系。如果步骤 B 的 `depends_on` 是 `[1]`，说明 B 必须在步骤 1 完成后才能执行。未来可以据此实现**并行执行**无依赖的步骤。

**Q: `extract_tool_args` 的简化实现有什么问题？**
A: 用字符串匹配提取参数很脆弱。比如步骤描述是"获取当前时间信息"，匹配"搜索/查询/查找"都命中不了。实际项目中应该让 LLM 根据描述智能提取参数，或使用 function calling 机制。

**Q: Replan 的代价是什么？**
A: 每次 Replan 需要额外一次 LLM 调用，且会丢弃原计划中未执行的步骤。频繁 Replan 说明初始规划质量不够，或者任务本身不确定性太高——这种场景可能更适合 ReAct。

---

## 知识脉络

```
阶段2: 工具循环 (LLM 直接调工具)
  ↓
01_react: ReAct 模式 (逐步思考，白盒推理)
  ↓
02_plan_and_execute 本课: Plan-and-Execute (先全局规划，再逐步执行)
  ├── 核心创新: Planner + Executor 分离
  ├── 关键技术: 结构化输出 (Pydantic + JSON Schema)
  └── 容错机制: Replan 动态调整
  ↓
下一课: 03_reflection.py - Reflection 自我反思模式
```

---

## 下一步

→ [03 - Reflection 自我反思模式](03_reflection.md)
