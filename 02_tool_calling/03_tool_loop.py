"""
03 - 工具调用循环 (Agent 核心循环)

学习目标:
- 实现完整的 Agent Loop: 决策 → 调用 → 观察 → 继续
- 理解这是所有 Agent 框架的底层原理
- 掌握循环终止条件与最大迭代保护
- 实现一个可交互的命令行 Agent

核心思想:
    Agent = LLM + Tools + Loop

    while True:
        response = LLM(messages, tools)
        if response 包含 tool_calls:
            执行工具，将结果加入 messages
            continue  # 继续循环，让 LLM 看到结果后决定下一步
        else:
            输出最终回答
            break

运行方式:
    python 02_tool_calling/03_tool_loop.py
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 工具定义与实现
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "搜索互联网获取信息。用于查询事实、新闻、技术文档等。",
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
            "description": "计算数学表达式。支持加减乘除、幂运算、取模等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如 '(3+5)*2'"},
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
    {
        "type": "function",
        "function": {
            "name": "take_note",
            "description": "记录一条笔记到内存中。用于保存重要信息供后续使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "笔记内容"},
                    "tag": {"type": "string", "description": "标签，用于分类"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_notes",
            "description": "回忆之前记录的所有笔记",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "按标签过滤，不填则返回全部"},
                },
                "required": [],
            },
        },
    },
]


# 工具实现
notes_store: list[dict] = []  # 简单的内存笔记存储


def tool_search(query: str) -> str:
    """搜索工具 (使用 Bing 搜索)"""
    try:
        import httpx
        from bs4 import BeautifulSoup

        resp = httpx.get(
            "https://cn.bing.com/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.b_algo")

        if not items:
            return json.dumps({"results": [], "note": "未找到结果"}, ensure_ascii=False)

        formatted = []
        for item in items[:3]:
            title_el = item.select_one("h2")
            snippet_el = item.select_one(".b_caption p")
            formatted.append({
                "title": title_el.get_text() if title_el else "",
                "snippet": snippet_el.get_text()[:200] if snippet_el else "",
            })
        return json.dumps({"query": query, "results": formatted}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"搜索失败: {str(e)}"}, ensure_ascii=False)


def tool_calculate(expression: str) -> str:
    """计算工具"""
    try:
        allowed = {"abs": abs, "round": round, "min": min, "max": max,
                   "pow": pow, "sqrt": math.sqrt, "pi": math.pi, "e": math.e}
        result = eval(expression, {"__builtins__": {}}, allowed)
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"error": f"计算失败: {e}"}, ensure_ascii=False)


def tool_get_time() -> str:
    """时间工具"""
    now = datetime.now()
    weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return json.dumps({
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": weekdays[now.weekday()],
    }, ensure_ascii=False)


def tool_take_note(content: str, tag: str = "general") -> str:
    """记录笔记"""
    note = {"content": content, "tag": tag, "time": datetime.now().strftime("%H:%M:%S")}
    notes_store.append(note)
    return json.dumps({"status": "已记录", "total_notes": len(notes_store)}, ensure_ascii=False)


def tool_recall_notes(tag: str = "") -> str:
    """回忆笔记"""
    filtered = notes_store if not tag else [n for n in notes_store if n["tag"] == tag]
    return json.dumps({"notes": filtered, "count": len(filtered)}, ensure_ascii=False)


# 工具名称 → 函数映射
TOOL_MAP = {
    "search": tool_search,
    "calculate": tool_calculate,
    "get_time": tool_get_time,
    "take_note": tool_take_note,
    "recall_notes": tool_recall_notes,
}


# ============================================================
# Agent 核心循环
# ============================================================

def agent_loop(user_message: str, system_prompt: str = "", max_iterations: int = 10, verbose: bool = True, history: list = None) -> str:
    """
    Agent 核心循环 - 这是整个项目最重要的函数

    流程:
        1. 将用户消息发给 LLM (附带工具定义)
        2. 如果 LLM 返回 tool_calls → 执行工具 → 将结果加入消息 → 回到步骤1
        3. 如果 LLM 返回普通文本 → 作为最终回答返回

    参数:
        user_message: 用户输入
        system_prompt: 系统提示词
        max_iterations: 最大循环次数 (防止无限循环)
        verbose: 是否打印中间过程
        history: 外部消息历史 (传入则复用，实现多轮对话记忆)

    返回:
        Agent 的最终回答
    """
    # 初始化消息列表
    if history is not None:
        messages = history
        messages.append({"role": "user", "content": user_message})
    else:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

    if verbose:
        print(f"\n[用户]: {user_message}")

    # === Agent 循环 ===
    for iteration in range(max_iterations):
        if verbose:
            print(f"\n--- 迭代 {iteration + 1} ---")

        # 调用 LLM
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=TOOLS,
        )

        msg = response.choices[0].message

        # 终止条件: LLM 没有调用工具 → 输出最终回答
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content})
            if verbose:
                print(f"[Agent 最终回答]: {msg.content}")
            return msg.content

        # LLM 决定调用工具
        if verbose:
            print(f"[LLM 决策]: 调用 {len(msg.tool_calls)} 个工具")

        # 将 assistant 消息 (含 tool_calls) 加入历史
        messages.append(msg)

        # 执行每个工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            if verbose:
                print(f"  → 执行: {func_name}({func_args})")

            # 查找并执行工具
            if func_name in TOOL_MAP:
                result = TOOL_MAP[func_name](**func_args)
            else:
                result = json.dumps({"error": f"未知工具: {func_name}"})

            if verbose:
                display = result[:100] + "..." if len(result) > 100 else result
                print(f"  ← 结果: {display}")

            # 将工具结果加入消息历史
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        # 继续循环 → LLM 会看到工具结果，决定下一步

    # 超过最大迭代次数
    return "[Agent 达到最大迭代次数，强制停止]"


# ============================================================
# 演示
# ============================================================

SYSTEM_PROMPT = """你是一个智能助手 Agent。你可以搜索信息、进行计算、记录笔记。

工作原则:
1. 需要外部信息时，主动使用搜索工具
2. 需要精确计算时，使用计算工具而不是心算
3. 重要信息用笔记工具记录
4. 综合所有工具结果给出完整回答
"""


def demo_multi_step():
    """演示: 需要多步工具调用的复杂问题"""
    print_separator("演示1: 多步工具调用")

    # 这个问题需要: 搜索 + 计算 + 记录
    agent_loop(
        "帮我查一下 Python 最新版本号，然后计算该版本号乘以 2 的结果，并把结论记为笔记",
        system_prompt=SYSTEM_PROMPT,
    )


def demo_single_step():
    """演示: 简单问题可能不需要工具"""
    print_separator("演示2: 简单问题 (可能不用工具)")

    agent_loop(
        "用一句话解释什么是递归",
        system_prompt=SYSTEM_PROMPT,
    )


def demo_interactive():
    """交互式 Agent - 支持多轮对话记忆"""
    print_separator("演示3: 交互式 Agent")
    print("输入 'quit' 退出\n")

    # 维护跨轮次的消息历史 (Agent 的“记忆”)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        user_input = input("[你]: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break
        if not user_input:
            continue

        answer = agent_loop(user_input, history=history, verbose=False)
        print(f"\n[Agent]: {answer}\n")


if __name__ == "__main__":
    print("=== 03 工具调用循环 (Agent 核心) ===\n")
    print("这是整个 Agent 学习项目最核心的概念！")
    print("所有 Agent 框架 (LangChain/LangGraph/AutoGen) 的底层都是这个循环。\n")

    # demo_multi_step()
    # demo_single_step()

    # 取消下行注释可进入交互模式
    demo_interactive()

    print_separator("阶段 2 完成!")
    print("你已掌握:")
    print("  1. Function Calling 的完整协议流程")
    print("  2. 工具注册与管理的设计模式")
    print("  3. Agent 核心循环 (Loop) 的实现")
    print("\n核心理解: Agent = LLM(大脑) + Tools(手脚) + Loop(决策循环)")
    print("\n下一阶段: 03_agent_patterns/ - 经典 Agent 设计模式")
