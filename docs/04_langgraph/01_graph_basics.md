# 01 - LangGraph 图基础

## 学习目标

- 理解 LangGraph 的核心概念: StateGraph、Node、Edge、State
- 掌握如何使用 LangGraph 构建有状态的工作流
- 理解状态驱动的执行模型
- 对比 LangGraph 与手写 Agent 循环的区别

## 运行方式

```bash
python 04_langgraph/01_graph_basics.py
```

---

## 核心概念

### 1. 什么是 LangGraph？

LangGraph 是一个用于构建有状态、多步骤 Agent 的框架。它将 Agent 的工作流抽象为**图结构**，其中：

- **节点 (Node)**: 执行具体操作的函数
- **边 (Edge)**: 连接节点，定义执行流程
- **状态 (State)**: 所有节点共享的数据结构
- **图 (Graph)**: 编译后的可执行工作流

**关键认知：** LangGraph 本质上是把 Agent 的执行流程**显式化**了。不再是隐式的 Python 循环，而是声明式的图结构。

### 2. State: 共享的数据结构

State 是 LangGraph 的核心概念。所有节点都读写同一个 State 对象：

```python
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next_action: str
```

**要点：**
- `Annotated[list[BaseMessage], add_messages]` 是 LangGraph 的 reducer 机制
- `add_messages` 会自动合并新消息，而不是覆盖
- 每次节点返回 `{"messages": [new_msg]}` 时，会自动追加到列表

### 3. Node: 处理函数

节点是普通的 Python 函数，签名固定为 `(state: State) -> dict`：

```python
def chatbot_node(state: AgentState) -> dict:
    # 读取状态
    last_message = state["messages"][-1]
    
    # 处理逻辑
    response = "你好！"
    
    # 返回要更新的状态字段
    return {
        "messages": [AIMessage(content=response)],
        "next_action": "finish",
    }
```

**注意：** 返回的字典只包含要更新的字段，未返回的字段保持不变。

### 4. Edge: 连接节点

边定义了节点间的执行顺序：

```python
from langgraph.graph import START, END, StateGraph

graph = StateGraph(AgentState)

# 添加节点
graph.add_node("chatbot", chatbot_node)

# 添加边
graph.add_edge(START, "chatbot")  # 入口 → chatbot
graph.add_edge("chatbot", END)    # chatbot → 出口

# 编译图
app = graph.compile()
```

---

## 代码实现详解

### 构建简单线性图

```python
def build_simple_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    
    # 1. 添加节点
    graph.add_node("chatbot", chatbot_node)
    graph.add_node("router", router_node)
    
    # 2. 添加边
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", "router")
    graph.add_edge("router", END)
    
    # 3. 编译
    return graph.compile()
```

**流程：** `START → chatbot → router → END`

### 构建带循环的对话图

```python
def build_conversational_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    
    graph.add_node("chatbot", chatbot_node)
    graph.add_node("router", router_node)
    
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", "router")
    
    # 条件边: 根据状态决定下一步
    def should_continue(state: AgentState) -> str:
        if state["next_action"] == "continue":
            return "chatbot"  # 回到 chatbot
        else:
            return END        # 结束
    
    graph.add_conditional_edges(
        "router",
        should_continue,
        {"chatbot": "chatbot", END: END}
    )
    
    return graph.compile()
```

**流程：** `START → chatbot → router → (continue? chatbot : END)`

### 运行图

```python
app = build_simple_graph()

initial_state = {
    "messages": [HumanMessage(content="你好")],
    "next_action": "continue",
}

# 同步执行
final_state = app.invoke(initial_state)

# 流式执行 (可以看到每一步)
for event in app.stream(initial_state):
    node_name = list(event.keys())[0]
    print(f"执行节点: {node_name}")
```

---

## 状态流转可视化

```
初始状态:
  messages: [HumanMessage("你好")]
  next_action: "continue"

↓ START → chatbot

chatbot_node 执行:
  读取: messages[-1] = "你好"
  生成: "你好！我是 LangGraph Agent"
  返回: {
    messages: [AIMessage("你好！...")],
    next_action: "finish"
  }

↓ chatbot → router

router_node 执行:
  读取: next_action = "finish"
  返回: {next_action: "finish"}

↓ router → END

最终状态:
  messages: [HumanMessage("你好"), AIMessage("你好！...")]
  next_action: "finish"
```

---

## 手写 Agent vs LangGraph

| 对比维度 | 手写 Agent (阶段3) | LangGraph |
|----------|-------------------|-----------|
| 定义方式 | 命令式 (Python 循环) | 声明式 (图结构) |
| 状态管理 | 手动维护变量 | 框架自动管理 |
| 控制流 | if/else/while | 条件边、路由函数 |
| 可视化 | 无 | 可生成 Mermaid 图 |
| 持久化 | 需手动实现 | 内置 Checkpoint |
| 人工介入 | 需手动实现 | 内置 interrupt |
| 调试 | print 日志 | LangSmith 集成 |
| 学习曲线 | 低 (纯 Python) | 中 (需理解图概念) |
| 灵活性 | 高 (完全控制) | 中 (受框架约束) |
| 适合场景 | 学习原理、简单场景 | 生产环境、复杂工作流 |

**核心价值：**
- 阶段3 手写: 理解 Agent 原理，掌握底层机制
- 阶段4 LangGraph: 学习工业级框架，为生产环境做准备

---

## 实践经验

**Q: 为什么需要 LangGraph？**

A: 手写 Agent 循环在简单场景下很灵活，但当工作流变复杂时，会遇到：
- 状态管理混乱
- 难以可视化
- 难以持久化和恢复
- 难以加入人工介入
- 难以调试

LangGraph 通过图结构解决了这些问题。

**Q: State 的 reducer 机制是什么？**

A: `Annotated[list[BaseMessage], add_messages]` 中的 `add_messages` 是 reducer。它决定了当节点返回 `{"messages": [new_msg]}` 时，如何合并到现有状态：
- 默认行为: 覆盖
- `add_messages`: 追加新消息

**Q: 如何调试 LangGraph 图？**

A: 
1. 使用 `app.stream()` 而不是 `app.invoke()`，可以看到每一步的执行
2. 在节点函数中添加 `print` 日志
3. 使用 LangSmith 进行可视化调试 (生产环境推荐)

---

## 知识脉络

```
阶段1: 基础对话 (LLM 直接回答)
  ↓
阶段2: 工具循环 (LLM 通过 tool_calls 调工具)
  ↓
阶段3: Agent 模式 (ReAct/Plan/Reflect/Memory)
  ↓
阶段4 本课: LangGraph 图基础 (声明式工作流)
  ↓
下一课: 条件路由 (根据状态动态决策)
```

LangGraph 是工业级 Agent 开发的标准工具。掌握它，你就能构建可靠、可控、可维护的 Agent 系统。

---

## 下一步

→ [02 - 条件路由](02_conditional_edges.md)
