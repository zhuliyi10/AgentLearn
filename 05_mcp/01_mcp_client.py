"""
01 - MCP Client (Model Context Protocol 客户端)

学习目标:
- 理解 MCP Client 的职责: 连接 Server → 发现能力 → 调用能力
- 掌握 stdio 传输: 把一个 Server 脚本当作子进程拉起并通信
- 理解 MCP 的通信生命周期: 启动 → 初始化握手 → 使用 → 关闭
- 打通「客户端 ⇄ 服务端」的完整闭环

核心思想:
    MCP 采用「客户端 / 服务端」架构, 二者通过 JSON-RPC 消息通信:

        ┌────────────┐   JSON-RPC over stdio   ┌────────────┐
        │  Client    │ ──────请求 (调用工具)──→ │  Server    │
        │ (你的Agent)│ ←─────响应 (工具结果)──── │ (能力提供方)│
        └────────────┘                          └────────────┘

    传输方式 (Transport) 有多种, 最常见的是:
    - stdio:          Client 把 Server 当子进程启动, 通过 标准输入/输出 通信
                      (本地工具、命令行集成的首选)
    - streamable-http: 通过 HTTP 通信 (远程 Server、多客户端共享的首选)

    本课用 stdio 连接我们在 02_mcp_server.py 里写的 Server。

为什么先学 Client?
    因为「使用别人的 Server」是最常见的场景 —— 社区里已经有成百上千的现成
    MCP Server (文件系统、GitHub、数据库、浏览器...)。学会当 Client,
    你的 Agent 就能一键接入这些能力。

运行方式:
    # 需要先有 02_mcp_server.py (本课会把它当子进程自动拉起)
    python 05_mcp/01_mcp_client.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from utils.helpers import print_separator

# 指向同目录下的 Server 脚本, 让 Client 把它当子进程启动。
SERVER_SCRIPT = Path(__file__).resolve().parent / "02_mcp_server.py"


# ============================================================
# 1. 配置如何启动 Server
# ============================================================

def build_server_params() -> StdioServerParameters:
    """
    StdioServerParameters 描述「怎么把 Server 跑起来」:
    - command: 用哪个可执行程序 (这里用当前的 python 解释器)
    - args:    传给它的参数 (脚本路径 + serve 参数, 让 Server 进入服务模式)

    Client 会用这些参数 fork 出一个子进程, 并接管它的 stdin/stdout
    作为 JSON-RPC 通道。
    """
    return StdioServerParameters(
        command=sys.executable,             # 当前虚拟环境的 python
        args=[str(SERVER_SCRIPT), "serve"],  # python 02_mcp_server.py serve
    )


# ============================================================
# 2. 完整的连接 → 发现 → 调用 流程
# ============================================================

async def run_client():
    """演示 MCP Client 的标准工作流程。"""
    params = build_server_params()

    print(f"启动 Server 子进程: {params.command} {' '.join(params.args)}\n")

    # stdio_client 负责启动子进程, 返回一对读写流 (read, write)
    async with stdio_client(params) as (read, write):
        # ClientSession 在读写流之上封装了 MCP 协议 (JSON-RPC + 会话管理)
        async with ClientSession(read, write) as session:

            # ---- 步骤 1: 初始化握手 ----
            # 必须先 initialize(), Client 和 Server 在这一步互换能力信息、
            # 协议版本, 之后才能正常通信。
            print_separator("步骤 1: 初始化握手 (initialize)")
            init = await session.initialize()
            print(f"连接成功! Server: {init.server_info.name} "
                  f"v{init.server_info.version}")
            print(f"协议版本: {init.protocol_version}")
            if init.instructions:
                print(f"使用说明: {init.instructions}")

            # ---- 步骤 2: 发现工具 (list_tools) ----
            print_separator("步骤 2: 发现能力 (list_tools)")
            tools = (await session.list_tools()).tools
            print(f"Server 提供了 {len(tools)} 个工具:\n")
            for t in tools:
                schema = t.input_schema
                props = schema.get("properties", {})
                required = set(schema.get("required", []))
                params_desc = ", ".join(
                    f"{name}{'*' if name in required else ''}: "
                    f"{spec.get('type', 'any')}"
                    for name, spec in props.items()
                ) or "无参数"
                print(f"  • {t.name}({params_desc})")
                print(f"      {t.description}")
            print("\n  (* 表示必填参数)")

            # ---- 步骤 3: 调用工具 (call_tool) ----
            print_separator("步骤 3: 调用工具 (call_tool)")

            print("调用 add(a=10, b=32):")
            result = await session.call_tool("add", {"a": 10, "b": 32})
            print(f"  → {result.content[0].text}\n")

            print("调用 current_time():")
            result = await session.call_tool("current_time", {})
            print(f"  → {result.content[0].text}\n")

            print("调用 divide(a=10, b=0)  —— 演示错误如何返回给 Client:")
            result = await session.call_tool("divide", {"a": 10, "b": 0})
            print(f"  → is_error={result.is_error}")
            print(f"  → {result.content[0].text}")
            print("  (注意: Server 没有崩溃, 错误被包装成结果返回, "
                  "Agent 可据此重试)")

            # ---- 步骤 4: 读取资源 (read_resource) ----
            print_separator("步骤 4: 读取资源 (read_resource)")
            content = await session.read_resource("info://server")
            print("读取 info://server:")
            for line in content.contents[0].text.splitlines():
                print(f"  {line}")

            # ---- 步骤 5: 获取提示词 (get_prompt) ----
            print_separator("步骤 5: 获取提示词 (get_prompt)")
            got = await session.get_prompt(
                "translate", {"text": "模型上下文协议很强大", "target_lang": "英文"}
            )
            print("获取 translate 提示词模板, 填入参数后得到:")
            for msg in got.messages:
                print(f"  [{msg.role}] {msg.content.text}")

    # 退出 async with 时, 子进程会被自动关闭。
    print()
    print("连接已关闭, Server 子进程已退出。")


# ============================================================
# 3. Client / Server 职责对照
# ============================================================

def show_architecture():
    """展示 MCP 客户端 / 服务端的职责划分。"""
    print_separator("MCP 架构: Client vs Server")
    print("""
┌──────────────────────┬──────────────────────────────────────────┐
│ 角色                 │ 职责                                       │
├──────────────────────┼──────────────────────────────────────────┤
│ Server (02 号文件)   │ 拥有能力, 把 Tools/Resources/Prompts       │
│                      │ 暴露成标准接口                             │
│ Client (本文件)      │ 需要能力, 连接 Server、发现并调用          │
├──────────────────────┼──────────────────────────────────────────┤
│ 通信协议             │ JSON-RPC 2.0                               │
│ 传输方式             │ stdio (子进程) / streamable-http (远程)    │
│ 生命周期             │ 启动 → initialize 握手 → 使用 → 关闭       │
└──────────────────────┴──────────────────────────────────────────┘

一句话记住:
    Server 是「插座」, Client 是「插头」, MCP 协议是「插座标准」。
    只要都遵循标准, 任意 Agent 都能即插即用任意 Server 的能力。
""")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  01 - MCP Client")
    print("=" * 60)

    if not SERVER_SCRIPT.exists():
        print(f"\n找不到 Server 脚本: {SERVER_SCRIPT}")
        print("请确认 05_mcp/02_mcp_server.py 存在。")
        sys.exit(1)

    show_architecture()
    asyncio.run(run_client())

    print_separator("总结")
    print("✓ 用 stdio 把 Server 当子进程启动并连接")
    print("✓ 走通了 initialize → list_tools → call_tool 的完整流程")
    print("✓ 读取了资源、获取了提示词模板")
    print("✓ 看到错误如何被安全地包装返回, 而非让 Server 崩溃")
    print()
    print("下一步: 03_mcp_tools/ —— 构建实用工具集, 并让 LLM 通过 MCP 调用它们")
