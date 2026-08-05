"""
02 - MCP Server (Model Context Protocol 服务端)

学习目标:
- 理解 MCP Server 的职责: 把「工具/资源/提示词」以标准协议暴露出去
- 掌握用高层 API (MCPServer 装饰器) 快速开发一个 Server
- 理解 MCP 的三大原语: Tools(工具) / Resources(资源) / Prompts(提示词)
- 理解 stdio 传输: Server 通过 标准输入输出 与 Client 通信

核心思想:
    在阶段2, 我们把工具直接写死在 Agent 代码里 —— 工具和 Agent 强耦合。
    MCP 把这件事「协议化」了:

        Server 端: 谁拥有能力, 谁就把能力暴露成标准接口
        Client 端: 谁需要能力, 谁就按标准接口去发现和调用

    这样一来, 一个 Server 写好后, 任何支持 MCP 的 Agent (Claude Desktop、
    Cursor、你自己的 Agent) 都能直接接入, 无需改代码。这就是「工具生态标准」。

MCP 的三大原语:
    ┌───────────┬──────────────────────────┬────────────────────────┐
    │ 原语      │ 作用                     │ 类比                   │
    ├───────────┼──────────────────────────┼────────────────────────┤
    │ Tools     │ 可被调用、有副作用的动作 │ 函数 / POST 接口       │
    │ Resources │ 可被读取的数据 (只读)    │ 文件 / GET 接口        │
    │ Prompts   │ 预置的提示词模板         │ 可复用的 Prompt 片段   │
    └───────────┴──────────────────────────┴────────────────────────┘

运行方式:
    # 方式一 (推荐先跑这个): 进程内自测, 直接看到 Server 暴露了什么
    python 05_mcp/02_mcp_server.py

    # 方式二: 作为真正的 stdio Server 启动 (会阻塞等待 Client 的 JSON-RPC 输入)
    #         一般不手动运行, 而是由 01_mcp_client.py 作为子进程拉起
    python 05_mcp/02_mcp_server.py serve
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp import Client
from mcp.server.mcpserver import MCPServer

from utils.helpers import print_separator

# ============================================================
# 1. 创建 Server
# ============================================================

# MCPServer 是高层 API: 用装饰器就能把普通 Python 函数暴露成 MCP 能力。
# name / version / instructions 会在 Client 初始化握手时被读到,
# instructions 相当于「这个 Server 的使用说明」, 供 LLM 参考。
server = MCPServer(
    name="learn-mcp-server",
    version="0.1.0",
    instructions=(
        "这是一个用于教学的 MCP Server, 提供基础数学工具、"
        "服务器信息资源, 以及一个翻译提示词模板。"
    ),
)


# ============================================================
# 2. 定义 Tools (工具) —— 可被调用、可能有副作用的动作
# ============================================================

@server.tool(description="计算两个数字的和")
def add(a: float, b: float) -> float:
    """
    工具 = 一个普通函数 + 一个装饰器。

    关键点:
    - 函数的类型注解 (a: float, b: float) 会被自动转成 JSON Schema,
      Client / LLM 据此知道该怎么传参。
    - 函数的返回值会被自动包装成 MCP 的返回内容。
    - docstring 和 description 会作为工具说明暴露给调用方。
    """
    return a + b


@server.tool(description="计算两个数字的商 (演示错误处理)")
def divide(a: float, b: float) -> float:
    """
    如果函数内部抛异常, MCP 不会让整个 Server 崩溃,
    而是把它包装成一个「带 is_error 标记」的结果返回给 Client。
    这让 Client / LLM 有机会看到错误并自我纠正。
    """
    return a / b  # b=0 时会抛 ZeroDivisionError, MCP 会捕获并标记为错误


@server.tool(description="返回当前服务器时间 (ISO 格式)")
def current_time() -> str:
    """无参数工具: 演示「工具不一定需要输入」。"""
    return datetime.now().isoformat(timespec="seconds")


# ============================================================
# 3. 定义 Resources (资源) —— 只读的数据
# ============================================================

@server.resource("info://server", description="服务器自我介绍")
def server_info() -> str:
    """
    资源用 URI 来标识 (这里是 info://server)。
    资源是「只读」的 —— Client 通过 read_resource(uri) 读取内容,
    适合暴露配置、文档、数据快照等不需要「执行」的数据。
    """
    return (
        "learn-mcp-server v0.1.0\n"
        "用途: 演示 MCP 的 Tools / Resources / Prompts 三大原语。"
    )


@server.resource("greeting://{name}", description="按名字生成问候语 (资源模板)")
def greeting(name: str) -> str:
    """
    带参数的资源 = 资源模板 (Resource Template)。
    URI 中的 {name} 是占位符, Client 读取 greeting://小明 时,
    name 会被自动填成 "小明"。类似「参数化的 GET 接口」。
    """
    return f"你好, {name}! 欢迎来到 MCP 的世界。"


# ============================================================
# 4. 定义 Prompts (提示词) —— 可复用的提示词模板
# ============================================================

@server.prompt(description="生成一个翻译任务的提示词")
def translate(text: str, target_lang: str = "英文") -> str:
    """
    Prompt 原语让 Server 把「打磨好的提示词」也变成可复用资产。
    Client 拉取后可以直接喂给 LLM。这样提示词工程的成果也能跨应用共享。
    """
    return (
        f"你是一名专业翻译。请把下面的文本翻译成{target_lang}, "
        f"只输出译文, 不要解释:\n\n{text}"
    )


# ============================================================
# 5. 进程内自测 (方式一) —— 直接看到 Server 暴露了什么
# ============================================================

async def self_test():
    """
    用「进程内 Client」连接本 Server, 打印它对外暴露的全部能力。

    Client(server) 直接传入 MCPServer 对象时, SDK 会用内存传输把
    Client 和 Server 接在一起, 不启动子进程 —— 非常适合开发时自测。
    """
    print_separator("Server 能力自测 (进程内 Client)")

    async with Client(server) as client:
        # --- 握手信息 ---
        info = client.server_info
        print(f"已连接 Server: {info.name} v{info.version}")
        print(f"使用说明: {client.instructions}\n")

        # --- Tools ---
        tools = (await client.list_tools()).tools
        print(f"[Tools] 共 {len(tools)} 个:")
        for t in tools:
            params = ", ".join(t.input_schema.get("properties", {}).keys()) or "无参数"
            print(f"  • {t.name}({params}) —— {t.description}")

        print("\n  调用 add(3, 4):")
        result = await client.call_tool("add", {"a": 3, "b": 4})
        print(f"    → {result.content[0].text}")

        print("\n  调用 divide(1, 0) —— 故意触发错误:")
        result = await client.call_tool("divide", {"a": 1, "b": 0})
        print(f"    → is_error={result.is_error}, 内容: {result.content[0].text}")

        # --- Resources ---
        print()
        resources = (await client.list_resources()).resources
        templates = (await client.list_resource_templates()).resource_templates
        print(f"[Resources] 固定资源 {len(resources)} 个, 资源模板 {len(templates)} 个:")
        for r in resources:
            print(f"  • {r.uri} —— {r.description}")
        for tpl in templates:
            print(f"  • {tpl.uri_template} (模板) —— {tpl.description}")

        print("\n  读取 info://server:")
        content = await client.read_resource("info://server")
        for line in content.contents[0].text.splitlines():
            print(f"    {line}")

        print("\n  读取 greeting://小明 (模板):")
        content = await client.read_resource("greeting://小明")
        print(f"    → {content.contents[0].text}")

        # --- Prompts ---
        print()
        prompts = (await client.list_prompts()).prompts
        print(f"[Prompts] 共 {len(prompts)} 个:")
        for p in prompts:
            print(f"  • {p.name} —— {p.description}")

        print("\n  获取 translate(text='你好世界', target_lang='英文'):")
        got = await client.get_prompt(
            "translate", {"text": "你好世界", "target_lang": "英文"}
        )
        for msg in got.messages:
            print(f"    [{msg.role}] {msg.content.text}")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    # 带 serve 参数 → 作为真正的 stdio Server 启动。
    # 此时 stdout 被用作 JSON-RPC 通道, 所以不能在这里 print 业务信息,
    # 否则会污染协议数据。日志由 SDK 自动输出到 stderr。
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        # 等价写法: asyncio.run(server.run_stdio_async())
        server.run("stdio")
        sys.exit(0)

    print("=" * 60)
    print("  02 - MCP Server")
    print("=" * 60)
    print()
    print("MCP 三大原语:")
    print("  • Tools     可被调用的动作 (add / divide / current_time)")
    print("  • Resources 只读数据 (info://server, greeting://{name})")
    print("  • Prompts   提示词模板 (translate)")
    print()

    asyncio.run(self_test())

    print_separator("总结")
    print("✓ 用 MCPServer 装饰器暴露了 Tools / Resources / Prompts")
    print("✓ 用进程内 Client 验证了 Server 的能力")
    print("✓ 理解了函数注解如何自动变成工具的 JSON Schema")
    print()
    print("下一步: 运行 01_mcp_client.py —— 用 stdio 把本 Server 当子进程连接")
