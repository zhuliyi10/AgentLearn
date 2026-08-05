# 03 - 实用工具集

## 学习目标

- 把 MCP Server 概念用到「真实、有用」的工具上
- 掌握三类最常见的工具能力: 文件操作 / 数据库 / 外部 API 集成
- 学会给工具做「安全边界」(路径沙箱、参数校验、错误处理)
- 打通 **MCP × Function Calling**: 让 LLM 从 MCP 动态获得能力并自主调用

## 目录结构

```
05_mcp/03_mcp_tools/
├── server.py        # 实用工具集 MCP Server (文件/数据库/HTTP/计算)
├── client_demo.py   # 用 Client 驱动全部工具, 观察一个小工作流
└── agent.py         # 让 LLM 通过 MCP 自动调用工具 (核心！)
```

## 运行方式

```bash
# 1. 用 Client 手动驱动全部工具 (离线可跑)
python 05_mcp/03_mcp_tools/client_demo.py

# 2. 让 LLM 自动编排工具 (需要 .env 中配置 OPENAI_API_KEY)
python 05_mcp/03_mcp_tools/agent.py
```

---

## 第一部分: 一个实用的 Server

`server.py` 暴露了四类工具：

| 类别 | 工具 | 说明 |
|------|------|------|
| 文件操作 | `write_file` / `read_file` / `list_files` | 沙箱在 `sandbox/` 目录内 |
| 数据库 | `add_note` / `list_notes` / `search_notes` | SQLite 笔记本 |
| API 集成 | `http_get` | 发起 HTTP GET 请求 |
| 纯计算 | `calculate` | 计算数学表达式 |

### 安全边界一: 路径沙箱

文件工具最容易被忽视、也最危险的问题是**路径穿越**。如果用户传入 `../../etc/passwd`，直接拼接就会读到系统敏感文件：

```python
def _safe_path(name: str) -> Path:
    target = (SANDBOX_DIR / name).resolve()          # 先解析成绝对路径
    if not target.is_relative_to(SANDBOX_DIR):       # 再校验它确实在沙箱内
        raise ValueError(f"非法路径: {name}")
    return target
```

!!! danger "工具即攻击面"
    每个能操作文件、执行命令、访问网络的工具，都是一个潜在攻击面。开发工具时，「这个参数最坏能被用来干什么」这个问题必须在写功能之前就想清楚。

### 安全边界二: 受限的表达式计算

`calculate` 用了 `eval`，但先做字符白名单，禁止任意代码执行：

```python
@server.tool(description="计算一个数学表达式")
def calculate(expression: str) -> str:
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        raise ValueError("表达式只能包含数字和 + - * / ( ) . % 运算符")
    result = eval(expression, {"__builtins__": {}}, {})  # 已做白名单
    return f"{expression} = {result}"
```

传入 `import os` 会被直接拒绝，而不是执行。

### 数据库工具

每次调用开一个新 SQLite 连接 —— 简单且线程安全（MCP 工具函数可能在不同线程被调用）：

```python
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS notes (...)")
    return conn

@server.tool(description="新增一条笔记")
def add_note(title: str, content: str) -> str:
    conn = _db()
    try:
        cur = conn.execute("INSERT INTO notes (title, content) VALUES (?, ?)",
                           (title, content))
        conn.commit()
        return f"已添加笔记 #{cur.lastrowid}: {title}"
    finally:
        conn.close()
```

---

## 第二部分: 用 Client 驱动 (client_demo.py)

`client_demo.py` 把这些工具串成一个个小场景，验证它们真的能干活：

```
场景 1: 文件读写 → write_file → list_files → read_file → (故意)路径穿越被拒
场景 2: 笔记数据库 → add_note × 2 → list_notes → search_notes
场景 3: 数学计算 → calculate('2*(3+4)') → calculate('import os') 被拒
场景 4: HTTP 请求 → http_get (需要网络)
```

**关键认知：** 多个 MCP 工具组合起来，就是一个工作流。把这些能力交给 LLM，它就能**自己**编排出工作流 —— 这正是下一部分要做的。

---

## 第三部分: 让 LLM 通过 MCP 调用工具 (agent.py)

这是整个阶段 5 的**高潮**：把阶段 2 的 Function Calling 和阶段 5 的 MCP 打通。

### 桥接的核心: Schema 转换

LLM 调用工具靠 Function Calling —— 我们告诉它有哪些工具（名字 + 参数 Schema），它就会在需要时输出「调用请求」。而 MCP 恰好能从远端 Server **动态提供**这份工具清单。桥接逻辑只有三步：

```python
def to_openai_tool(mcp_tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.input_schema,   # MCP 的 Schema 直接就是 JSON Schema
        },
    }
```

!!! tip "两个协议在「工具描述」上是相通的"
    MCP 的 `input_schema` 本身就是标准 JSON Schema，可以直接作为 OpenAI function 的 `parameters`。这正是桥接能如此简洁的原因。

### Agent 主循环

```python
mcp_tools = (await session.list_tools()).tools          # 1. 从 MCP 发现工具
openai_tools = [to_openai_tool(t) for t in mcp_tools]   # 2. 转成 LLM 格式

messages = [{"role": "system", ...}, {"role": "user", ...}]
for turn in range(1, 6):
    response = client.chat.completions.create(
        model=model, messages=messages, tools=openai_tools)
    msg = response.choices[0].message

    if not msg.tool_calls:            # LLM 不再调工具 → 得到最终回答
        print(msg.content)
        break

    messages.append(msg.model_dump(exclude_none=True))
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)
        result = await session.call_tool(tc.function.name, args)  # 3. 转回 MCP 调用
        messages.append({
            "role": "tool", "tool_call_id": tc.id,
            "content": result.content[0].text,
        })
```

### 实际运行效果

给它一个需要**多步 + 多工具**的任务：

> 帮我算一下 128 × 12 等于多少，然后把结果作为一条笔记存起来，标题叫『计算结果』。

LLM 会自主编排：

```
[第 1 轮] LLM 决定调用: calculate({'expression': '128 * 12'})
          MCP 返回 [成功]: 128 * 12 = 1536
[第 2 轮] LLM 决定调用: add_note({'title': '计算结果', 'content': '128 * 12 = 1536'})
          MCP 返回 [成功]: 已添加笔记 #3: 计算结果
[最终回答] 计算结果为 1536，已添加到笔记中。
```

**这就是 MCP 对 Agent 生态的意义：** Agent 不再内置任何工具，接上哪个 MCP Server，就自动拥有哪些能力。

---

## 实践经验

**Q: 为什么这个闭环这么重要？**

A: 它把阶段 2~5 的知识全部串起来了 —— LLM 决策（阶段 1）、工具调用（阶段 2）、Agent 循环（阶段 2/3）、工具标准化（阶段 5）。理解了这个闭环，你就理解了「现代 Agent 是如何工作的」。

**Q: 生产环境要注意什么？**

A: 至少三点：① 每个工具都要有明确的安全边界（本课的沙箱、白名单只是起点）；② 工具描述要写清楚，LLM 靠它决定何时调用；③ 循环要设最大轮次，防止 LLM 陷入反复调用的死循环。

**Q: 换成社区现成的 MCP Server 也能这样用吗？**

A: 完全可以。`agent.py` 的桥接逻辑对任何 MCP Server 都通用 —— 只要改一下启动参数指向别的 Server，LLM 就能用上文件系统、GitHub、数据库等现成能力，桥接代码一行都不用改。

---

## 知识脉络

```
阶段1: LLM 决策
  +
阶段2: Function Calling
  +
阶段5: MCP (工具发现与标准化)
  ↓
本课: LLM 从 MCP 动态获得能力并自主编排  ← 现代 Agent 的完整闭环
  ↓
阶段6: 多 Agent 协作
```

至此，阶段 5 全部完成。你已经能解释 MCP 的设计理念、开发自己的 Server、并让 Agent 通过 MCP 连接外部能力。

---

## 下一步

→ 阶段 6 - 多 Agent 协作
