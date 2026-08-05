"""
03 / agent.py - 让 LLM 通过 MCP 调用工具 (MCP × Function Calling)

学习目标:
- 把阶段2 的 Function Calling 和阶段5 的 MCP 打通
- 理解「桥接」的关键: 把 MCP 工具的 Schema 转成 LLM 认识的工具格式
- 看清一个完整的 Agent 闭环: LLM 决策 → 调用 MCP 工具 → 观察结果 → 继续

核心思想:
    LLM 本身只会「说话」, 它调用工具的方式是 Function Calling:
    我们告诉它有哪些工具 (名字 + 参数 Schema), 它就会在需要时
    输出一个「调用请求」, 由我们代为执行并把结果喂回去。

    MCP 恰好能提供这份「工具清单 + Schema」, 而且是从远端 Server 动态发现的。
    于是桥接逻辑就三步:

        1. 从 MCP Server 发现工具  → session.list_tools()
        2. 转成 OpenAI 工具格式    → 见 to_openai_tool()
        3. LLM 要调用时, 转回 MCP → session.call_tool(name, args)

    这样, 你的 Agent 不需要预先内置任何工具 —— 接上哪个 MCP Server,
    就自动拥有哪些能力。这就是 MCP 对 Agent 生态的意义。

运行方式:
    # 需要在 .env 中配置好 OPENAI_API_KEY (可用兼容 API)
    python 05_mcp/03_mcp_tools/agent.py

    # 没有配置 Key 时, 仍会打印「工具发现 + Schema 转换」的过程 (离线可看)
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from utils.helpers import print_separator

SERVER_SCRIPT = Path(__file__).resolve().parent / "server.py"

SYSTEM_PROMPT = (
    "你是一个能使用工具的助手。你可以读写文件、操作笔记数据库、做数学计算。"
    "当用户的请求需要用到工具时, 请调用合适的工具; 拿到结果后, 用简洁的中文回答用户。"
)


# ============================================================
# 桥接核心: MCP 工具 Schema → OpenAI Function Calling 格式
# ============================================================

def to_openai_tool(mcp_tool) -> dict:
    """
    把一个 MCP Tool 描述转成 OpenAI Chat Completions 的 tools 项。

    MCP 的 input_schema 本身就是标准 JSON Schema, 可以直接作为
    OpenAI function 的 parameters —— 两个协议在「工具描述」上是相通的,
    这正是桥接能如此简洁的原因。
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.input_schema,
        },
    }


# ============================================================
# Agent 主循环: LLM 决策 ⇄ MCP 工具执行
# ============================================================

async def run_agent(session: ClientSession, user_query: str) -> None:
    from utils.llm import get_client, get_model

    # 1. 发现 MCP 工具并转成 LLM 能理解的格式
    mcp_tools = (await session.list_tools()).tools
    openai_tools = [to_openai_tool(t) for t in mcp_tools]

    print_separator("工具发现 + Schema 转换")
    print(f"从 MCP Server 发现 {len(mcp_tools)} 个工具, 转成 OpenAI 格式。")
    print("示例 (第一个工具转换后的样子):")
    print(json.dumps(openai_tools[0], ensure_ascii=False, indent=2))

    # 2. 准备 LLM 客户端 (没有 Key 就优雅退出)
    try:
        client = get_client()
        model = get_model()
    except ValueError as e:
        print_separator("跳过实时 LLM 调用")
        print(f"未配置 API Key, 无法进行实时对话:\n  {e}")
        print("\n但你已经看到了最关键的一步: MCP 工具是如何被转成 LLM 工具的。")
        print("配置好 .env 中的 OPENAI_API_KEY 后, 再运行即可看到完整对话。")
        return

    # 3. Agent 循环: 决策 → 调用 → 观察 → 继续
    print_separator(f"用户提问: {user_query}")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    for turn in range(1, 6):  # 最多 5 轮, 防止死循环
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=openai_tools,
        )
        msg = response.choices[0].message

        # LLM 不再调用工具 → 得到最终回答
        if not msg.tool_calls:
            print(f"\n[最终回答] {msg.content}")
            return

        # LLM 要求调用一个或多个工具
        messages.append(msg.model_dump(exclude_none=True))
        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"\n[第 {turn} 轮] LLM 决定调用: {name}({args})")

            # 转回 MCP 调用
            result = await session.call_tool(name, args)
            output = result.content[0].text if result.content else ""
            status = "错误" if result.is_error else "成功"
            print(f"           MCP 返回 [{status}]: {output}")

            # 把工具结果喂回给 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": output,
            })

    print("\n[提示] 达到最大轮次限制。")


# ============================================================
# 主程序
# ============================================================

async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT), "serve"],
    )
    # 一个需要「多步 + 多工具」才能完成的任务, 用来展示 Agent 的自主编排
    user_query = (
        "帮我算一下 128 * 12 等于多少, "
        "然后把结果作为一条笔记存起来, 标题叫『计算结果』。"
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await run_agent(session, user_query)


if __name__ == "__main__":
    print("=" * 60)
    print("  03 - LLM 通过 MCP 调用工具")
    print("=" * 60)
    print()
    asyncio.run(main())

    print_separator("总结")
    print("✓ 把 MCP 工具 Schema 转成了 OpenAI Function Calling 格式")
    print("✓ 打通了 LLM 决策 → 调用 MCP 工具 → 观察结果 → 继续 的闭环")
    print("✓ Agent 不再内置工具, 而是从 MCP Server 动态获得能力")
    print()
    print("恭喜! 你已完成阶段 5。下一步: 阶段 6 - 多 Agent 协作")
