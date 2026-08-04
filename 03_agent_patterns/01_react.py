"""
01 - ReAct 模式 (Reasoning + Acting)

学习目标:
- 理解 ReAct 论文的核心思想: 推理与行动交替进行
- 手动实现一个不依赖框架的 ReAct Agent
- 掌握 Thought → Action → Observation 循环
- 理解 ReAct 相比纯工具循环的优势 (可解释性)

核心思想:
    传统工具循环: LLM 直接决定调用工具 (黑盒)
    ReAct:        LLM 先思考(Thought) → 再行动(Action) → 观察结果(Observation) → 再思考...
    
    优势: 推理过程可见，便于调试和理解 Agent 的决策逻辑

运行方式:
    python 03_agent_patterns/01_react.py
"""

import sys
import json
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 工具定义
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "搜索互联网获取信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                },
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
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"},
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "获取当前日期和时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """执行工具并返回结果"""
    if name == "search":
        try:
            import httpx
            from bs4 import BeautifulSoup
            resp = httpx.get(
                "https://cn.bing.com/search",
                params={"q": args["query"]},
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
                timeout=10,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("li.b_algo")[:3]
            results = []
            for item in items:
                title = item.select_one("h2")
                snippet = item.select_one(".b_caption p")
                results.append({
                    "title": title.get_text() if title else "",
                    "snippet": snippet.get_text()[:200] if snippet else "",
                })
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
        from datetime import datetime
        now = datetime.now()
        return json.dumps({
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        }, ensure_ascii=False)

    return json.dumps({"error": f"未知工具: {name}"})


# ============================================================
# ReAct Agent 实现
# ============================================================

REACT_SYSTEM_PROMPT = """你是一个使用 ReAct (Reasoning + Acting) 模式的智能助手。

## 工作流程
每次收到用户问题后，你必须按以下格式输出:

Thought: [你的思考过程 - 分析问题，决定下一步做什么]
Action: [工具名称]
Action Input: [工具参数，JSON 格式]

当你获得足够信息可以回答时:
Thought: [总结思考过程]
Final Answer: [你的最终回答]

## 可用工具
- search(query): 搜索互联网
- calculate(expression): 数学计算
- get_time(): 获取当前时间

## 重要规则
1. 每次只输出一个 Thought + Action 对 (或 Final Answer)
2. Action 必须是可用工具之一
3. 思考要清晰，说明你为什么选择这个工具
4. 不要编造工具结果，等待 Observation 返回

## 示例
用户: 北京和上海今天温差多少度？

Thought: 我需要知道北京和上海的温度。先搜索北京的天气。
Action: search
Action Input: {"query": "北京今天天气"}

(等待 Observation 返回后继续)

Thought: 已获取北京天气，现在搜索上海的。
Action: search
Action Input: {"query": "上海今天天气"}

(等待 Observation 返回后)

Thought: 两个城市的温度都有了。北京28°C，上海31°C，温差3°C。
Final Answer: 北京和上海今天温差约3°C，上海更热一些。
"""


def react_agent(user_question: str, max_steps: int = 10) -> str:
    """
    ReAct Agent 实现

    与阶段2的工具循环的区别:
    - 阶段2: LLM 直接输出 tool_calls (黑盒决策)
    - ReAct: LLM 先输出 Thought 文本，再决定 Action (白盒推理)

    实现方式: 使用文本解析来提取 Thought/Action/Action Input
    """
    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_question},
    ]

    print(f"\n[用户]: {user_question}")

    for step in range(max_steps):
        print(f"\n{'='*50}")
        print(f"  步骤 {step + 1}")
        print(f"{'='*50}")

        # 调用 LLM
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            temperature=0,  # ReAct 需要确定性输出
        )

        llm_output = response.choices[0].message.content
        print(f"\n[LLM 输出]:\n{llm_output}")

        # 将 LLM 输出加入历史
        messages.append({"role": "assistant", "content": llm_output})

        # 解析输出: 检查是否有 Final Answer
        if "Final Answer:" in llm_output:
            # 提取 Final Answer
            answer = llm_output.split("Final Answer:")[-1].strip()
            print(f"\n[最终回答]: {answer}")
            return answer

        # 解析 Action 和 Action Input
        action = None
        action_input = None

        for line in llm_output.split("\n"):
            line = line.strip()
            if line.startswith("Action:"):
                action = line.replace("Action:", "").strip()
            elif line.startswith("Action Input:"):
                input_str = line.replace("Action Input:", "").strip()
                try:
                    action_input = json.loads(input_str)
                except json.JSONDecodeError:
                    action_input = {}

        # 执行工具
        if action and action_input is not None:
            print(f"\n[执行工具]: {action}({action_input})")
            observation = execute_tool(action, action_input)
            print(f"[Observation]: {observation[:200]}{'...' if len(observation) > 200 else ''}")

            # 将 Observation 作为 user 消息返回给 LLM
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}\n\n请继续推理 (Thought → Action 或 Final Answer)",
            })
        else:
            # LLM 没有输出有效的 Action，提示重试
            messages.append({
                "role": "user",
                "content": "请按照格式输出: Thought → Action → Action Input，或 Thought → Final Answer",
            })

    return "[达到最大步数，强制停止]"


# ============================================================
# 演示
# ============================================================

def demo_react():
    """演示: ReAct Agent 解决多步问题"""
    print_separator("ReAct Agent 演示")

    # 需要多步推理的问题
    question = "现在几点了？帮我算一下距离今天结束还有多少小时？"

    answer = react_agent(question, max_steps=6)

    print(f"\n{'='*50}")
    print("ReAct 模式的优势:")
    print("  1. 推理过程可见 (Thought 步骤)")
    print("  2. 便于调试 (能看到 Agent 为什么这么做)")
    print("  3. 可追溯 (出问题时能回溯到具体步骤)")
    print("  4. 更接近人类解决问题的方式")


if __name__ == "__main__":
    print("=== 01 ReAct 模式 ===\n")
    print("ReAct = Reasoning + Acting")
    print("论文: 'ReAct: Synergizing Reasoning and Acting in Language Models' (2022)\n")

    demo_react()

    print_separator("完成")
    print("下一步: 02_plan_and_execute.py - Plan-and-Execute 模式")
