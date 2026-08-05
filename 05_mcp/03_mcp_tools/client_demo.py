"""
03 / client_demo.py - 用 MCP Client 驱动实用工具集

学习目标:
- 复习 Client 的完整流程, 这次面对的是「有实际用途」的工具
- 观察一个工具调用序列如何完成一件真实的事 (记笔记、读写文件)
- 体会 MCP 工具的组合能力: 多个工具串起来就是一个小工作流

运行方式:
    python 05_mcp/03_mcp_tools/client_demo.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from utils.helpers import print_separator

SERVER_SCRIPT = Path(__file__).resolve().parent / "server.py"


async def call(session: ClientSession, name: str, args: dict | None = None) -> str:
    """调用工具并返回文本结果 (顺带打印, 方便观察)。"""
    result = await session.call_tool(name, args or {})
    text = result.content[0].text if result.content else "(无返回内容)"
    flag = " [错误]" if result.is_error else ""
    arg_str = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
    print(f"  → {name}({arg_str}){flag}")
    for line in text.splitlines() or [""]:
        print(f"      {line}")
    return text


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT), "serve"],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"已连接: {init.server_info.name} v{init.server_info.version}")

            tools = (await session.list_tools()).tools
            print(f"可用工具 ({len(tools)} 个): "
                  f"{', '.join(t.name for t in tools)}")

            # --- 场景 1: 文件操作 ---
            print_separator("场景 1: 文件读写 (沙箱)")
            await call(session, "write_file",
                       {"name": "todo.txt", "content": "1. 学习 MCP\n2. 构建 Agent"})
            await call(session, "list_files")
            await call(session, "read_file", {"name": "todo.txt"})
            print("\n  演示安全边界 —— 尝试路径穿越:")
            await call(session, "read_file", {"name": "../../../etc/passwd"})

            # --- 场景 2: 数据库 ---
            print_separator("场景 2: 笔记数据库 (SQLite)")
            await call(session, "add_note",
                       {"title": "MCP 是什么", "content": "一个 Agent 工具生态标准"})
            await call(session, "add_note",
                       {"title": "MCP 三原语", "content": "Tools / Resources / Prompts"})
            await call(session, "list_notes")
            await call(session, "search_notes", {"keyword": "原语"})

            # --- 场景 3: 计算 ---
            print_separator("场景 3: 数学计算")
            await call(session, "calculate", {"expression": "2 * (3 + 4)"})
            await call(session, "calculate", {"expression": "import os"})  # 会被拒绝

            # --- 场景 4: 外部 API (需要网络, 失败不影响演示) ---
            print_separator("场景 4: HTTP 请求 (需要网络)")
            try:
                await call(session, "http_get",
                           {"url": "https://example.com", "max_chars": 120})
            except Exception as e:  # noqa: BLE001
                print(f"  (网络不可用或请求失败, 已跳过: {e})")

    print()
    print("演示结束。sandbox/ 目录和 notes.db 已生成, 可自行查看。")


if __name__ == "__main__":
    print("=" * 60)
    print("  03 - 用 Client 驱动实用工具集")
    print("=" * 60)
    print()
    asyncio.run(main())

    print_separator("总结")
    print("✓ 用真实工具走通了「文件 / 数据库 / 计算 / HTTP」四类能力")
    print("✓ 验证了路径沙箱与表达式白名单等安全边界")
    print("✓ 体会到多个 MCP 工具组合起来就是一个工作流")
    print()
    print("下一步: agent.py —— 把这些工具交给 LLM, 让它自己决定何时调用哪个")
