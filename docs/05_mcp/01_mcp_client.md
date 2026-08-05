# 01 - MCP Client

## 学习目标

- 理解 MCP Client 的职责: 连接 Server → 发现能力 → 调用能力
- 掌握 stdio 传输: 把一个 Server 脚本当作子进程拉起并通信
- 理解 MCP 的通信生命周期: 启动 → 初始化握手 → 使用 → 关闭
- 打通「客户端 ⇄ 服务端」的完整闭环

## 运行方式

```bash
# 需要先有 02_mcp_server.py (本课会把它当子进程自动拉起)
python 05_mcp/01_mcp_client.py
```

---

## 核心概念

### 1. 什么是 MCP？

MCP (Model Context Protocol，模型上下文协议) 是一个**开放标准**，用来规范「Agent 如何连接外部能力」。

在阶段 2，我们把工具直接写死在 Agent 代码里 —— 工具和 Agent 强耦合。MCP 把这件事**协议化**了：

- **Server 端**：谁拥有能力，谁就把能力暴露成标准接口
- **Client 端**：谁需要能力，谁就按标准接口去发现和调用

一个 Server 写好后，任何支持 MCP 的 Agent（Claude Desktop、Cursor、你自己的 Agent）都能直接接入，无需改代码。这就是「工具生态标准」。

### 2. 客户端 / 服务端架构

MCP 采用「客户端 / 服务端」架构，二者通过 **JSON-RPC 2.0** 消息通信：

```
┌────────────┐   JSON-RPC over stdio   ┌────────────┐
│  Client    │ ──────请求 (调用工具)──→ │  Server    │
│ (你的Agent)│ ←─────响应 (工具结果)──── │ (能力提供方)│
└────────────┘                          └────────────┘
```

### 3. 传输方式 (Transport)

| 传输方式 | 说明 | 适用场景 |
|----------|------|----------|
| **stdio** | Client 把 Server 当子进程启动，通过标准输入/输出通信 | 本地工具、命令行集成 |
| **streamable-http** | 通过 HTTP 通信 | 远程 Server、多客户端共享 |

本课用 **stdio** 连接我们在 `02_mcp_server.py` 里写的 Server。

!!! tip "为什么先学 Client？"
    因为「使用别人的 Server」是最常见的场景 —— 社区里已经有成百上千的现成 MCP Server（文件系统、GitHub、数据库、浏览器……）。学会当 Client，你的 Agent 就能一键接入这些能力。

---

## 代码实现详解

### 配置如何启动 Server

`StdioServerParameters` 描述「怎么把 Server 跑起来」：

```python
from mcp import StdioServerParameters

params = StdioServerParameters(
    command=sys.executable,              # 当前虚拟环境的 python
    args=[str(SERVER_SCRIPT), "serve"],  # python 02_mcp_server.py serve
)
```

Client 会用这些参数 fork 出一个子进程，并接管它的 stdin/stdout 作为 JSON-RPC 通道。

### 连接 → 发现 → 调用

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        # 1. 初始化握手 (必须最先调用)
        init = await session.initialize()

        # 2. 发现工具
        tools = (await session.list_tools()).tools

        # 3. 调用工具
        result = await session.call_tool("add", {"a": 10, "b": 32})
        print(result.content[0].text)  # → 42.0
```

**三层结构：**

1. `stdio_client(params)` —— 启动子进程，返回读写流 `(read, write)`
2. `ClientSession(read, write)` —— 在流之上封装 MCP 协议（JSON-RPC + 会话管理）
3. `session.xxx()` —— 发现和调用能力

### 通信生命周期

```
启动子进程
   ↓
initialize()  ← 必须最先调用，互换能力信息与协议版本
   ↓
list_tools() / call_tool() / read_resource() / get_prompt()  ← 正常使用
   ↓
退出 async with  ← 子进程被自动关闭
```

!!! warning "initialize 是必须的"
    在调用任何 `list_*` / `call_*` 之前，**必须**先 `await session.initialize()`。握手阶段 Client 和 Server 互换能力信息和协议版本，跳过它后续调用会失败。

---

## 错误如何返回

调用 `divide(10, 0)` 时，Server 端会抛 `ZeroDivisionError`。但 MCP **不会让 Server 崩溃**，而是把错误包装成一个带标记的结果返回：

```python
result = await session.call_tool("divide", {"a": 10, "b": 0})
print(result.is_error)        # True
print(result.content[0].text) # Error executing tool divide: division by zero
```

这一点对 Agent 至关重要：LLM 能「看到」错误，从而有机会自我纠正、重试或换一条路径，而不是整个流程直接中断。

---

## Client vs Server 职责对照

| 角色 | 职责 |
|------|------|
| Server (02 号文件) | 拥有能力，把 Tools/Resources/Prompts 暴露成标准接口 |
| Client (本文件) | 需要能力，连接 Server、发现并调用 |
| 通信协议 | JSON-RPC 2.0 |
| 传输方式 | stdio (子进程) / streamable-http (远程) |

**一句话记住：** Server 是「插座」，Client 是「插头」，MCP 协议是「插座标准」。只要都遵循标准，任意 Agent 都能即插即用任意 Server 的能力。

---

## 实践经验

**Q: MCP 和阶段 2 的 Function Calling 是什么关系？**

A: 互补。Function Calling 是「LLM 如何表达要调用工具」的机制；MCP 是「工具从哪来、如何被发现和调用」的标准。阶段 5 的 `03_mcp_tools/agent.py` 会把两者桥接起来：从 MCP 发现工具 → 转成 Function Calling 格式喂给 LLM。

**Q: 为什么用子进程而不是直接 import Server 的函数？**

A: 因为 MCP 的价值就在于**解耦**。Server 可以用任何语言写、跑在任何地方，Client 完全不需要知道它的内部实现，只通过标准协议通信。子进程 + stdio 是这种解耦最轻量的体现。

**Q: 真实项目里 Client 会连接哪些 Server？**

A: 社区已有大量现成 Server：文件系统、Git/GitHub、PostgreSQL、Slack、浏览器自动化等。你只要改一下 `StdioServerParameters` 的 `command`（比如 `npx @modelcontextprotocol/server-filesystem`），就能接入它们。

---

## 知识脉络

```
阶段2: Function Calling (工具写死在 Agent 里)
  ↓
阶段5 本课: MCP Client (从标准接口动态发现并调用工具)
  ↓
下一课: MCP Server (自己实现能力提供方)
```

---

## 下一步

→ [02 - MCP Server](02_mcp_server.md)
