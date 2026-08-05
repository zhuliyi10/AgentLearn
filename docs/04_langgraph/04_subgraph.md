# 04 - LangGraph 子图模块化

## 学习目标

- 掌握子图 (Subgraph) 的概念和用法
- 理解图嵌套: 在图中嵌入子图
- 实现模块复用: 将通用逻辑封装为子图
- 掌握关注点分离: 用子图组织复杂工作流

## 运行方式

```bash
python 04_langgraph/04_subgraph.py
```

---

## 核心概念

### 1. 什么是子图？

子图是**嵌入在主图中的独立图结构**。它将复杂工作流拆分为多个可管理的模块：

```
单体图:     所有逻辑在一个大图里 (难维护)
子图模块化: 将功能拆分为独立子图，主图协调 (易维护、可复用)
```

**关键认知：** 子图是**关注点分离**的体现。主图负责高层协调，子图负责具体实现。就像函数调用一样，主图调用子图，子图完成任务后返回结果。

### 2. 子图的优势

| 优势 | 说明 |
|------|------|
| **模块化** | 每个子图负责一个明确的功能 |
| **可复用** | 子图可以在多个主图中复用 |
| **可测试** | 每个子图可以独立测试 |
| **可维护** | 修改子图不影响主图 |
| **可视化** | 子图可以独立可视化 |

### 3. 子图的使用方式

子图的使用分三步：

1. **定义子图**: 创建独立的 StateGraph
2. **调用子图**: 在主图节点中调用子图
3. **合并结果**: 将子图输出合并回主图状态

```python
# 1. 定义子图
def build_research_subgraph() -> StateGraph:
    graph = StateGraph(ResearchState)
    graph.add_node("research_planner", research_planner)
    graph.add_node("research_executor", research_executor)
    graph.add_node("research_summarizer", research_summarizer)
    graph.add_edge(START, "research_planner")
    graph.add_edge("research_planner", "research_executor")
    graph.add_edge("research_executor", "research_summarizer")
    graph.add_edge("research_summarizer", END)
    return graph.compile()

# 2. 在主图中调用
def research_coordinator(state: MainState) -> dict:
    """研究协调器: 调用研究子图"""
    
    # 构建子图输入
    subgraph_input = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "research_data": "",
        "summary": "",
    }
    
    # 调用子图
    research_graph = build_research_subgraph()
    subgraph_output = research_graph.invoke(subgraph_input)
    
    # 3. 合并结果
    return {
        "result": subgraph_output["summary"],
        "messages": [AIMessage(content=f"研究完成: {subgraph_output['summary']}")],
    }
```

---

## 代码实现详解

### 主图结构

本课实现了一个任务协调系统，主图负责路由到不同子图：

```
START → task_router → (条件路由)
                          ↓
                ┌─────────┼─────────┐
                ↓         ↓         ↓
          research    writing    analysis
          coordinator coordinator coordinator
                ↓         ↓         ↓
                └─────────┴─────────┘
                          ↓
                         END
```

**主图节点：**

| 节点 | 作用 |
|------|------|
| `task_router` | 识别任务类型，路由到对应子图 |
| `research_coordinator` | 调用研究子图 |
| `writing_coordinator` | 调用写作子图 |
| `analysis_coordinator` | 调用分析子图 |

### 研究子图

```
START → research_planner → research_executor → research_summarizer → END
```

**节点说明：**

| 节点 | 作用 |
|------|------|
| `research_planner` | 制定研究策略 |
| `research_executor` | 收集信息 |
| `research_summarizer` | 生成研究摘要 |

**状态定义：**

```python
class ResearchState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    research_data: str
    summary: str
```

### 写作子图

```
START → outline_generator → draft_writer → content_refiner → END
```

**节点说明：**

| 节点 | 作用 |
|------|------|
| `outline_generator` | 生成大纲 |
| `draft_writer` | 撰写草稿 |
| `content_refiner` | 内容润色 |

**状态定义：**

```python
class WritingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    topic: str
    outline: str
    draft: str
    final_content: str
```

### 分析子图

```
START → data_processor → analyzer → END
```

**节点说明：**

| 节点 | 作用 |
|------|------|
| `data_processor` | 数据处理 |
| `analyzer` | 执行分析 |

**状态定义：**

```python
class AnalysisState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    data: str
    analysis_result: str
```

### 子图调用示例

```python
def research_coordinator(state: MainState) -> dict:
    """研究协调器: 调用研究子图"""
    print("\n[research_coordinator] 调用研究子图...")
    
    # 1. 从主图状态提取输入
    last_message = state["messages"][-1]
    query = last_message.content
    
    # 2. 构建子图初始状态
    subgraph_input = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "research_data": "",
        "summary": "",
    }
    
    # 3. 调用子图
    research_graph = build_research_subgraph()
    subgraph_output = research_graph.invoke(subgraph_input)
    
    # 4. 将子图结果合并回主图状态
    return {
        "result": subgraph_output["summary"],
        "messages": [AIMessage(content=f"研究完成: {subgraph_output['summary']}")],
    }
```

---

## 子图设计模式

### 1. 功能拆分模式 (本课示例)

- 按功能拆分子图: 研究、写作、分析
- 适用: 多功能系统

```
主图: 任务路由
  ↓
子图A: 研究功能
子图B: 写作功能
子图C: 分析功能
```

### 2. 流程拆分模式

- 按流程阶段拆分子图: 预处理、处理、后处理
- 适用: 复杂流程

```
主图: 流程协调
  ↓
子图A: 数据预处理
子图B: 核心处理
子图C: 结果后处理
```

### 3. 复用模式

- 将通用逻辑封装为子图，多处复用
- 适用: 公共功能

```
主图A: 客服系统
主图B: 销售系统
  ↓
共用子图: 用户认证
```

### 4. 层级模式

- 子图还可以包含子图 (多层嵌套)
- 适用: 超复杂系统

```
主图
  ↓
子图A (包含子图A1, A2)
子图B (包含子图B1, B2)
```

---

## 实践经验

**Q: 子图和普通节点有什么区别？**

A: 
- **普通节点**: 一个函数，执行单一操作
- **子图**: 一个完整的图，包含多个节点和边

子图适合封装**复杂的多步骤逻辑**，普通节点适合**简单操作**。

**Q: 子图的状态和主图的状态是独立的吗？**

A: 是的，子图有自己独立的状态定义。主图通过**协调器节点**桥接两者：

```python
def coordinator(state: MainState) -> dict:
    # 1. 从主图状态提取输入
    input_data = state["some_field"]
    
    # 2. 构建子图输入
    subgraph_input = {
        "field1": input_data,
        "field2": "",
    }
    
    # 3. 调用子图
    subgraph_output = subgraph.invoke(subgraph_input)
    
    # 4. 合并回主图状态
    return {
        "result": subgraph_output["some_result"],
    }
```

**Q: 如何测试子图？**

A: 子图可以独立测试，不需要运行整个系统：

```python
def test_research_subgraph():
    research_graph = build_research_subgraph()
    
    result = research_graph.invoke({
        "messages": [HumanMessage(content="测试")],
        "query": "量子计算",
        "research_data": "",
        "summary": "",
    })
    
    assert "summary" in result
    assert len(result["summary"]) > 0
```

**Q: 子图可以共享状态吗？**

A: 子图状态是独立的，但可以通过主图协调器传递数据：

```python
def coordinator(state: MainState) -> dict:
    # 从主图传递数据给子图
    subgraph_input = {
        "shared_data": state["shared_field"],
    }
    
    subgraph_output = subgraph.invoke(subgraph_input)
    
    # 从子图传递数据回主图
    return {
        "shared_field": subgraph_output["result"],
    }
```

**Q: 子图嵌套会不会影响性能？**

A: 会有一定开销，但通常可以忽略。如果性能敏感，可以：
1. 避免过深的嵌套 (2-3 层足够)
2. 使用 `asyncio` 并行调用子图
3. 缓存子图结果

---

## 知识脉络

```
上一课: 人工介入 (interrupt 机制)
  ↓
本课: 子图模块化 (图嵌套)
  ↓
关键能力:
  • 子图定义: 独立的 StateGraph
  • 子图调用: 在主图节点中调用子图
  • 状态桥接: 主图状态 ↔ 子图状态
  ↓
阶段 4 完成！
```

子图模块化是构建大型 Agent 系统的关键技术。掌握了它，你就能构建**模块化、可维护、可扩展**的 Agent 系统。

---

## 阶段 4 总结

恭喜！你已经完成了 LangGraph 框架的学习。让我们回顾一下：

### 核心概念

1. **图基础**: State、Node、Edge、Graph
2. **条件路由**: 动态决策、分支逻辑
3. **人工介入**: interrupt、审批节点、断点恢复
4. **子图模块化**: 图嵌套、模块复用、关注点分离

### 你能做什么

- ✓ 用 LangGraph 构建有状态的 Agent 工作流
- ✓ 实现条件分支和循环控制
- ✓ 在关键节点加入人工审批
- ✓ 将复杂 Agent 拆分为可维护的子模块

### 下一步

→ [阶段 5 - MCP 协议](../05_mcp/01_mcp_client.md)

LangGraph 是工业级 Agent 开发的标准工具。结合你在阶段 3 手写的 Agent 模式，你现在既有理论深度，又有工程实践能力。继续前进！
