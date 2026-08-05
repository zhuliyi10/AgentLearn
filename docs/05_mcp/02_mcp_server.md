# 02 - MCP Server

## 学习目标

- 理解 MCP Server 的职责: 把「工具/资源/提示词」以标准协议暴露出去
- 掌握用高层 API (`MCPServer` 装饰器) 快速开发一个 Server
- 理解 MCP 的三大原语: Tools(工具) / Resources(资源) / Prompts(提示词)
- 理解 stdio 传输: Server 通过标准输入输出与 Client 通信

## 运行方式

```bash
# 方式一 (推荐先跑这个): 进程内自测，直接看到 Server 暴露了什么
python 05_mcp/02_mcp_server.py

# 方式二: 作为真正的 stdio Server 启动 (会阻塞等待 Client 的输入)
python 05_mcp/02_mcp_server.py serve
```

---

## 核心概念

### MCP 三大原语

MCP Server 能对外暴露三类东西：

| 原语 | 作用 | 类比 |
|------|------|------|
| **Tools** | 可被调用、有副作用的动作 | 函数 / POST 接口 |
| **Resources** | 可被读取的数据（只读） | 文件 / GET 接口 |
| **Prompts** | 预置的提示词模板 | 可复用的 Prompt 片段 |

理解这个划分很重要：**Tools 是「做事」，Resources 是「读数据」，Prompts 是「给提示词」**。三者共同构成 Server 对 Agent 的完整供给。

---

## 代码实现详解

### 创建 Server

```python
from mcp.server.mcpserver import MCPServer

server = MCPServer(
    name="learn-mcp-server",
    version="0.1.0",
    instructions="这是一个用于教学的 MCP Server ...",  # 相当于 Server 的使用说明
)
```

`name` / `version` / `instructions` 会在 Client 初始化握手时被读到。`instructions` 相当于「这个 Server 的使用说明」，供 LLM 参考。

### 定义 Tools

工具 = **一个普通函数 + 一个装饰器**：

```python
@server.tool(description="计算两个数字的和")
def add(a: float, b: float) -> float:
    return a + b
```

**关键点：**

- 函数的类型注解 `(a: float, b: float)` 会被**自动转成 JSON Schema**，Client / LLM 据此知道该怎么传参
- 函数的返回值会被自动包装成 MCP 的返回内容
- `docstring` 和 `description` 会作为工具说明暴露给调用方

无参数工具也完全没问题：

```python
@server.tool(description="返回当前服务器时间")
def current_time() -> str:
    return datetime.now().isoformat(timespec="seconds")
```

### 定义 Resources

资源用 **URI** 来标识，是**只读**数据：

```python
@server.resource("info://server", description="服务器自我介绍")
def server_info() -> str:
    return "learn-mcp-server v0.1.0 ..."
```

带参数的资源就是**资源模板 (Resource Template)**：

```python
@server.resource("greeting://{name}", description="按名字生成问候语")
def greeting(name: str) -> str:
    return f"你好, {name}!"
```

URI 中的 `{name}` 是占位符，Client 读取 `greeting://小明` 时，`name` 会被自动填成 `"小明"`。类似「参数化的 GET 接口」。

### 定义 Prompts

Prompt 原语让 Server 把「打磨好的提示词」也变成可复用资产：

```python
@server.prompt(description="生成一个翻译任务的提示词")
def translate(text: str, target_lang: str = "英文") -> str:
    return f"你是一名专业翻译。请把下面的文本翻译成{target_lang}...\n\n{text}"
```

Client 拉取后可以直接喂给 LLM，提示词工程的成果也能跨应用共享。

### 启动 Server

```python
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        server.run("stdio")   # 作为 stdio Server 启动
```

!!! warning "serve 模式下不要 print 业务信息"
    stdio 模式下，**stdout 被用作 JSON-RPC 通道**。如果在这里 `print` 业务内容，会污染协议数据导致 Client 解析失败。日志请交给 SDK 输出到 stderr。这也是我们用 `serve` 参数区分「自测模式」和「服务模式」的原因。

---

## 进程内自测: 最快的验证方式

开发 Server 时，不必每次都起子进程。把 `MCPServer` 对象直接传给 `Client`，SDK 会用**内存传输**把两者接在一起，不启动子进程：

```python
from mcp import Client

async with Client(server) as client:      # 直接传 server 对象
    tools = (await client.list_tools()).tools
    result = await client.call_tool("add", {"a": 3, "b": 4})
    print(result.content[0].text)          # → 7.0
```

这是开发调试阶段最快的验证方式；等确认无误，再用 `01_mcp_client.py` 走真正的 stdio 子进程路径。

---

## 函数注解 → JSON Schema

MCP 会把工具函数的签名自动转成 Client 可读的 Schema。例如 `add(a: float, b: float)` 会变成：

```json
{
  "type": "object",
  "properties": {
    "a": {"type": "number", "title": "A"},
    "b": {"type": "number", "title": "B"}
  },
  "required": ["a", "b"]
}
```

这意味着：**你写好类型注解，就等于写好了工具接口文档**，无需手动维护 Schema。

---

## 实践经验

**Q: Tools、Resources、Prompts 该怎么选？**

A: 看这个能力「会不会改变世界状态」：

- 会执行动作、有副作用（写文件、发请求、改数据库）→ **Tool**
- 只是读取已有数据、幂等无副作用 → **Resource**
- 是一段供复用的提示词 → **Prompt**

**Q: 工具里抛异常会怎样？**

A: MCP 会捕获它，包装成一个 `is_error=True` 的结果返回给 Client，Server 本身不会崩溃。所以工具里可以放心地对非法输入 `raise`，把校验逻辑写清楚即可。

**Q: `MCPServer` 和常见教程里的 `FastMCP` 是一回事吗？**

A: 是同一套「装饰器风格」的高层 API 在不同 SDK 版本中的名字。用法几乎一致（`@server.tool` / `@server.resource` / `@server.prompt` / `server.run()`），迁移成本很低。本项目使用的 SDK 版本导出的类名是 `MCPServer`。

---

## 知识脉络

```
阶段2: 工具写死在 Agent 里
  ↓
阶段5 上一课: MCP Client (学会消费别人的能力)
  ↓
阶段5 本课: MCP Server (学会生产、暴露自己的能力)
  ↓
下一课: 实用工具集 (文件/数据库/API + 让 LLM 自动调用)
```

---

## 下一步

→ [03 - 实用工具集](03_mcp_tools.md)
