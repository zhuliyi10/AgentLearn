"""
02 - Plan-and-Execute 模式

学习目标:
- 理解"先规划后执行"的 Agent 设计模式
- 实现 Planner (规划器) + Executor (执行器) 分离架构
- 掌握动态 Replan (重新规划) 机制
- 理解 Plan-and-Execute 与 ReAct 的区别和适用场景

核心思想:
    ReAct:          每步都思考 → 行动 → 观察 → 再思考... (逐步推理)
    Plan-and-Execute: 先制定完整计划 → 逐步执行 → 根据结果调整计划 (全局规划)

    适用场景: 复杂多步任务，需要全局视角的问题

运行方式:
    python 03_agent_patterns/02_plan_and_execute.py
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field
from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 工具定义 (与前面相同，简化版)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "搜索互联网获取信息",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "数学表达式"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """执行工具"""
    if name == "search":
        try:
            import httpx
            from bs4 import BeautifulSoup
            resp = httpx.get(
                "https://cn.bing.com/search",
                params={"q": args["query"]},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.b_algo")[:3]
            results = [{"title": i.select_one("h2").get_text(),
                        "snippet": (i.select_one(".b_caption p") or type("", (), {"get_text": lambda: ""})()).get_text()[:200]}
                       for i in items if i.select_one("h2")]
            return json.dumps({"results": results}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    elif name == "calculate":
        try:
            allowed = {"abs": abs, "round": round, "min": min, "max": max,
                       "pow": pow, "sqrt": math.sqrt, "pi": math.pi}
            result = eval(args["expression"], {"__builtins__": {}}, allowed)
            return json.dumps({"result": result})
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    elif name == "get_time":
        now = datetime.now()
        return json.dumps({
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        }, ensure_ascii=False)
    return json.dumps({"error": f"未知工具: {name}"})


# ============================================================
# Plan 数据模型
# ============================================================

class PlanStep(BaseModel):
    """计划步骤"""
    step_id: int = Field(description="步骤编号")
    description: str = Field(description="步骤描述")
    tool: str = Field(description="使用的工具名称，或 'none' 表示纯推理")
    depends_on: list[int] = Field(default_factory=list, description="依赖的步骤编号")


class Plan(BaseModel):
    """执行计划"""
    goal: str = Field(description="总体目标")
    steps: list[PlanStep] = Field(description="执行步骤列表")


# ============================================================
# Planner: 规划器
# ============================================================

PLANNER_PROMPT = """你是一个任务规划专家。给定一个目标，你需要制定详细的执行计划。

## 输出要求
请严格按照 JSON 格式输出计划:
{
    "goal": "总体目标描述",
    "steps": [
        {
            "step_id": 1,
            "description": "步骤描述",
            "tool": "工具名称或 none",
            "depends_on": []
        }
    ]
}

## 可用工具
- search(query): 搜索互联网
- calculate(expression): 数学计算
- get_time(): 获取当前时间

## 规划原则
1. 步骤要具体、可执行
2. 明确每步使用什么工具
3. 标注步骤间的依赖关系
4. 计划要合理，不要过多或过少步骤
"""


def create_plan(goal: str) -> Plan:
    """规划器: 根据目标生成执行计划"""
    schema_str = json.dumps(Plan.model_json_schema(), ensure_ascii=False, indent=2)

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": PLANNER_PROMPT + f"\n\n请严格按以下 JSON Schema 输出:\n{schema_str}"},
            {"role": "user", "content": f"目标: {goal}\n\n请制定执行计划。"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return Plan.model_validate_json(response.choices[0].message.content)


# ============================================================
# Executor: 执行器
# ============================================================

EXECUTOR_PROMPT = """你是一个任务执行者。你需要根据当前步骤执行任务，并返回结果。

## 输出要求
1. 先简要说明你打算怎么做
2. 执行工具 (如果需要)
3. 总结执行结果

如果你需要调用工具，请使用 function calling 机制。
"""


def execute_step(step: PlanStep, previous_results: dict[int, str]) -> str:
    """执行器: 执行单个步骤"""
    # 构建上下文
    context = f"当前步骤: {step.description}\n"
    if step.depends_on:
        context += "之前步骤的结果:\n"
        for dep_id in step.depends_on:
            if dep_id in previous_results:
                context += f"  步骤{dep_id}: {previous_results[dep_id][:200]}\n"

    if step.tool == "none":
        # 纯推理步骤
        response = client().chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "你是一个助手。请根据以下信息进行分析并给出结论。"},
                {"role": "user", "content": context},
            ],
        )
        return response.choices[0].message.content
    else:
        # 需要调用工具
        # 从步骤描述中提取工具参数 (简化处理)
        tool_args = extract_tool_args(step)

        print(f"  → 调用工具: {step.tool}({tool_args})")
        result = execute_tool(step.tool, tool_args)
        print(f"  ← 结果: {result[:150]}{'...' if len(result) > 150 else ''}")
        return result


def extract_tool_args(step: PlanStep) -> dict:
    """从步骤描述中提取工具参数 (简化版)"""
    # 实际项目中应该用 LLM 来提取，这里做简单处理
    desc = step.description.lower()

    if step.tool == "search":
        # 尝试从描述中提取搜索关键词
        for keyword in ["搜索", "查询", "查找", "搜索"]:
            if keyword in desc:
                query = desc.split(keyword)[-1].strip().rstrip("。.")
                return {"query": query}
        return {"query": step.description}

    elif step.tool == "calculate":
        # 尝试提取数学表达式
        import re
        expr_match = re.search(r'[\d+\-*/().\s]+', step.description)
        if expr_match:
            return {"expression": expr_match.group().strip()}
        return {"expression": step.description}

    elif step.tool == "get_time":
        return {}

    return {}


# ============================================================
# Replan: 重新规划
# ============================================================

REPLANNER_PROMPT = """你是一个任务规划专家。原计划执行过程中遇到了一些情况，你需要根据实际情况调整计划。

## 输出要求
请严格按照 JSON 格式输出调整后的计划:
{
    "goal": "总体目标描述",
    "steps": [...]
}

## 原则
1. 保留已完成或有效的步骤
2. 修改失败或需要调整的步骤
3. 添加新的步骤 (如果需要)
4. 确保计划仍然可行
"""


def replan(original_plan: Plan, executed_results: dict[int, str], issue: str) -> Plan:
    """重新规划: 根据执行情况调整计划"""
    schema_str = json.dumps(Plan.model_json_schema(), ensure_ascii=False, indent=2)

    context = f"原始目标: {original_plan.goal}\n\n"
    context += "已执行的步骤结果:\n"
    for step_id, result in executed_results.items():
        context += f"  步骤{step_id}: {result[:200]}\n"
    context += f"\n遇到的问题: {issue}\n"

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": REPLANNER_PROMPT + f"\n\n请严格按以下 JSON Schema 输出:\n{schema_str}"},
            {"role": "user", "content": context + "\n请调整计划。"},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    return Plan.model_validate_json(response.choices[0].message.content)


# ============================================================
# Plan-and-Execute Agent
# ============================================================

def plan_and_execute_agent(goal: str, max_replans: int = 2) -> str:
    """
    Plan-and-Execute Agent 主流程

    1. Planner 生成计划
    2. Executor 逐步执行
    3. 遇到问题时 Replan (重新规划)
    4. 所有步骤完成后，生成最终报告
    """
    print(f"\n[目标]: {goal}")

    # === 阶段1: 规划 ===
    print(f"\n{'='*50}")
    print("  阶段1: 制定计划")
    print(f"{'='*50}")

    plan = create_plan(goal)
    print(f"\n[计划]:")
    print(f"  目标: {plan.goal}")
    for step in plan.steps:
        deps = f" (依赖: {step.depends_on})" if step.depends_on else ""
        print(f"  {step.step_id}. {step.description} [工具: {step.tool}]{deps}")

    # === 阶段2: 执行 ===
    print(f"\n{'='*50}")
    print("  阶段2: 执行计划")
    print(f"{'='*50}")

    executed_results: dict[int, str] = {}
    replan_count = 0

    for step in plan.steps:
        print(f"\n[执行步骤 {step.step_id}]: {step.description}")

        try:
            result = execute_step(step, executed_results)
            executed_results[step.step_id] = result
            print(f"  ✓ 完成")
        except Exception as e:
            print(f"  ✗ 失败: {e}")

            # 尝试重新规划
            if replan_count < max_replans:
                print(f"\n[Replan {replan_count + 1}]: 调整计划...")
                plan = replan(plan, executed_results, str(e))
                replan_count += 1
                print(f"  新计划包含 {len(plan.steps)} 个步骤")
            else:
                print(f"  已达最大重规划次数，跳过此步骤")

    # === 阶段3: 生成最终报告 ===
    print(f"\n{'='*50}")
    print("  阶段3: 生成报告")
    print(f"{'='*50}")

    summary_context = f"目标: {goal}\n\n执行结果:\n"
    for step_id, result in executed_results.items():
        summary_context += f"步骤{step_id}: {result[:300]}\n"

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": "你是一个助手。请根据执行结果，生成完整的最终报告。"},
            {"role": "user", "content": summary_context},
        ],
    )

    final_answer = response.choices[0].message.content
    print(f"\n[最终报告]:\n{final_answer}")
    return final_answer


# ============================================================
# 演示
# ============================================================

def demo_plan_and_execute():
    """演示: Plan-and-Execute 解决复杂问题"""
    print_separator("Plan-and-Execute 演示")

    goal = "帮我了解一下 Python 3.12 有什么新特性，并计算如果每天学习2小时，学完所有新特性需要多少天（假设每个特性需要5小时学习）"

    plan_and_execute_agent(goal)


def demo_comparison():
    """演示: ReAct vs Plan-and-Execute 对比"""
    print_separator("ReAct vs Plan-and-Execute 对比")

    print("""
┌─────────────────┬──────────────────┬──────────────────┐
│                 │ ReAct            │ Plan-and-Execute │
├─────────────────┼──────────────────┼──────────────────┤
│ 决策方式        │ 逐步思考         │ 先全局规划       │
│ 推理深度        │ 局部 (当前步)    │ 全局 (整体)      │
│ 适合任务        │ 简单多步         │ 复杂多步         │
│ 可解释性        │ 高 (每步可见)    │ 高 (计划可见)    │
│ 灵活性          │ 高 (随时调整)    │ 中 (需 replan)   │
│ 效率            │ 中 (每步都推理)  │ 高 (规划后执行)  │
│ 典型场景        │ 问答、搜索       │ 研究、报告生成   │
└─────────────────┴──────────────────┴──────────────────┘

选择建议:
- 简单任务 (2-3步): 用 ReAct 或阶段2的工具循环
- 复杂任务 (5+步): 用 Plan-and-Execute
- 需要实时交互: 用 ReAct
- 需要全局视角: 用 Plan-and-Execute
""")


if __name__ == "__main__":
    print("=== 02 Plan-and-Execute 模式 ===\n")

    demo_comparison()
    demo_plan_and_execute()

    print_separator("完成")
    print("下一步: 03_reflection.py - Reflection 自我反思模式")
