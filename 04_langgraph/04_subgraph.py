"""
04 - LangGraph 子图模块化

学习目标:
- 掌握子图 (Subgraph) 的概念和用法
- 理解图嵌套: 在图中嵌入子图
- 实现模块复用: 将通用逻辑封装为子图
- 掌握关注点分离: 用子图组织复杂工作流

核心思想:
    单体图:     所有逻辑在一个大图里 (难维护)
    子图模块化: 将功能拆分为独立子图，主图协调 (易维护、可复用)
    
    优势: 模块化、可测试、可复用、关注点分离

运行方式:
    python 04_langgraph/04_subgraph.py
"""

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from utils.helpers import print_separator


# ============================================================
# 1. 定义主图 State
# ============================================================

class MainState(TypedDict):
    """
    主图状态
    
    主图负责协调各个子图:
    - messages: 对话历史
    - task_type: 任务类型 (用于路由到不同子图)
    - result: 最终结果
    """
    messages: Annotated[list[BaseMessage], add_messages]
    task_type: str  # "research" | "writing" | "analysis"
    result: str


# ============================================================
# 2. 定义子图 States
# ============================================================

class ResearchState(TypedDict):
    """研究子图状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    query: str
    research_data: str
    summary: str


class WritingState(TypedDict):
    """写作子图状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    topic: str
    outline: str
    draft: str
    final_content: str


class AnalysisState(TypedDict):
    """分析子图状态"""
    messages: Annotated[list[BaseMessage], add_messages]
    data: str
    analysis_result: str


# ============================================================
# 3. 研究子图
# ============================================================

def research_planner(state: ResearchState) -> dict:
    """研究规划: 制定研究策略"""
    print("\n[research_planner] 制定研究策略...")
    
    query = state["query"]
    print(f"  研究主题: {query}")
    
    strategy = f"针对 '{query}' 的研究策略：1. 收集背景资料 2. 分析关键数据 3. 总结核心发现"
    print(f"  策略: {strategy}")
    
    return {"research_data": strategy}


def research_executor(state: ResearchState) -> dict:
    """研究执行: 收集信息"""
    print("\n[research_executor] 执行研究...")
    
    query = state["query"]
    print(f"  正在研究: {query}")
    
    # 模拟研究结果
    research_data = f"关于 '{query}' 的研究发现：\n- 要点1: 这是一个重要的研究领域\n- 要点2: 有多个关键因素需要考虑\n- 要点3: 最新研究表明..."
    
    print(f"  ✓ 收集到 {len(research_data)} 字符的数据")
    return {"research_data": research_data}


def research_summarizer(state: ResearchState) -> dict:
    """研究总结: 生成摘要"""
    print("\n[research_summarizer] 生成研究摘要...")
    
    data = state["research_data"]
    summary = f"研究摘要: 通过对 '{data[:30]}...' 的分析，我们获得了关键洞察。"
    
    print(f"  ✓ 摘要: {summary[:50]}...")
    return {"summary": summary}


def build_research_subgraph() -> StateGraph:
    """
    构建研究子图
    
    流程:
    START → research_planner → research_executor → research_summarizer → END
    """
    graph = StateGraph(ResearchState)
    
    graph.add_node("research_planner", research_planner)
    graph.add_node("research_executor", research_executor)
    graph.add_node("research_summarizer", research_summarizer)
    
    graph.add_edge(START, "research_planner")
    graph.add_edge("research_planner", "research_executor")
    graph.add_edge("research_executor", "research_summarizer")
    graph.add_edge("research_summarizer", END)
    
    return graph.compile()


# ============================================================
# 4. 写作子图
# ============================================================

def outline_generator(state: WritingState) -> dict:
    """大纲生成: 创建内容结构"""
    print("\n[outline_generator] 生成大纲...")
    
    topic = state["topic"]
    outline = f"""
大纲 - {topic}:
1. 引言
   1.1 背景介绍
   1.2 目的说明
2. 主体内容
   2.1 核心概念
   2.2 实践方法
3. 结论
   3.1 总结要点
   3.2 未来展望
"""
    
    print(f"  ✓ 大纲已生成")
    return {"outline": outline}


def draft_writer(state: WritingState) -> dict:
    """草稿撰写: 根据大纲写初稿"""
    print("\n[draft_writer] 撰写草稿...")
    
    outline = state["outline"]
    topic = state["topic"]
    
    draft = f"这是关于 '{topic}' 的草稿。根据大纲结构，我们首先介绍背景，然后深入核心内容，最后总结要点..."
    
    print(f"  ✓ 草稿长度: {len(draft)} 字符")
    return {"draft": draft}


def content_refiner(state: WritingState) -> dict:
    """内容润色: 优化表达"""
    print("\n[content_refiner] 润色内容...")
    
    draft = state["draft"]
    final_content = f"[润色后] {draft} 通过优化表达，内容更加清晰流畅。"
    
    print(f"  ✓ 内容已润色")
    return {"final_content": final_content}


def build_writing_subgraph() -> StateGraph:
    """
    构建写作子图
    
    流程:
    START → outline_generator → draft_writer → content_refiner → END
    """
    graph = StateGraph(WritingState)
    
    graph.add_node("outline_generator", outline_generator)
    graph.add_node("draft_writer", draft_writer)
    graph.add_node("content_refiner", content_refiner)
    
    graph.add_edge(START, "outline_generator")
    graph.add_edge("outline_generator", "draft_writer")
    graph.add_edge("draft_writer", "content_refiner")
    graph.add_edge("content_refiner", END)
    
    return graph.compile()


# ============================================================
# 5. 分析子图
# ============================================================

def data_processor(state: AnalysisState) -> dict:
    """数据处理: 准备分析数据"""
    print("\n[data_processor] 处理数据...")
    
    data = state["data"]
    print(f"  输入数据: {data[:50]}...")
    
    processed = f"处理后的数据: {data} [已清洗、格式化]"
    return {"data": processed}


def analyzer(state: AnalysisState) -> dict:
    """分析器: 执行分析"""
    print("\n[analyzer] 执行分析...")
    
    data = state["data"]
    result = f"分析结果: 通过对数据的深入分析，我们发现以下模式：1. 趋势上升 2. 季节性波动 3. 异常点检测"
    
    print(f"  ✓ 分析完成")
    return {"analysis_result": result}


def build_analysis_subgraph() -> StateGraph:
    """
    构建分析子图
    
    流程:
    START → data_processor → analyzer → END
    """
    graph = StateGraph(AnalysisState)
    
    graph.add_node("data_processor", data_processor)
    graph.add_node("analyzer", analyzer)
    
    graph.add_edge(START, "data_processor")
    graph.add_edge("data_processor", "analyzer")
    graph.add_edge("analyzer", END)
    
    return graph.compile()


# ============================================================
# 6. 主图: 协调子图
# ============================================================

def task_router(state: MainState) -> dict:
    """任务路由器: 识别任务类型"""
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    print(f"\n[task_router] 分析任务: {user_text[:50]}...")
    
    if any(kw in user_text for kw in ["研究", "调研", "调查", "research"]):
        task_type = "research"
        print(f"  → 任务类型: research")
    elif any(kw in user_text for kw in ["写", "文章", "报告", "文档", "write"]):
        task_type = "writing"
        print(f"  → 任务类型: writing")
    elif any(kw in user_text for kw in ["分析", "数据", "统计", "analyze"]):
        task_type = "analysis"
        print(f"  → 任务类型: analysis")
    else:
        task_type = "research"  # 默认
        print(f"  → 任务类型: research (默认)")
    
    return {"task_type": task_type}


def research_coordinator(state: MainState) -> dict:
    """
    研究协调器: 调用研究子图
    
    这是子图调用的关键:
    1. 从主图状态提取输入
    2. 构建子图初始状态
    3. 调用子图
    4. 将子图结果合并回主图状态
    """
    print("\n[research_coordinator] 调用研究子图...")
    
    # 构建子图输入
    last_message = state["messages"][-1]
    query = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    subgraph_input = {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "research_data": "",
        "summary": "",
    }
    
    # 调用子图
    research_graph = build_research_subgraph()
    subgraph_output = research_graph.invoke(subgraph_input)
    
    print(f"  ✓ 研究完成: {subgraph_output['summary'][:50]}...")
    
    return {
        "result": subgraph_output["summary"],
        "messages": [AIMessage(content=f"研究完成: {subgraph_output['summary']}")],
    }


def writing_coordinator(state: MainState) -> dict:
    """写作协调器: 调用写作子图"""
    print("\n[writing_coordinator] 调用写作子图...")
    
    last_message = state["messages"][-1]
    topic = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    subgraph_input = {
        "messages": [HumanMessage(content=topic)],
        "topic": topic,
        "outline": "",
        "draft": "",
        "final_content": "",
    }
    
    writing_graph = build_writing_subgraph()
    subgraph_output = writing_graph.invoke(subgraph_input)
    
    print(f"  ✓ 写作完成: {subgraph_output['final_content'][:50]}...")
    
    return {
        "result": subgraph_output["final_content"],
        "messages": [AIMessage(content=f"写作完成: {subgraph_output['final_content']}")],
    }


def analysis_coordinator(state: MainState) -> dict:
    """分析协调器: 调用分析子图"""
    print("\n[analysis_coordinator] 调用分析子图...")
    
    last_message = state["messages"][-1]
    data = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    subgraph_input = {
        "messages": [HumanMessage(content=data)],
        "data": data,
        "analysis_result": "",
    }
    
    analysis_graph = build_analysis_subgraph()
    subgraph_output = analysis_graph.invoke(subgraph_input)
    
    print(f"  ✓ 分析完成: {subgraph_output['analysis_result'][:50]}...")
    
    return {
        "result": subgraph_output["analysis_result"],
        "messages": [AIMessage(content=f"分析完成: {subgraph_output['analysis_result']}")],
    }


def build_main_graph() -> StateGraph:
    """
    构建主图: 协调各个子图
    
    流程:
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
    """
    graph = StateGraph(MainState)
    
    # 添加节点
    graph.add_node("task_router", task_router)
    graph.add_node("research_coordinator", research_coordinator)
    graph.add_node("writing_coordinator", writing_coordinator)
    graph.add_node("analysis_coordinator", analysis_coordinator)
    
    # 添加边
    graph.add_edge(START, "task_router")
    
    # 条件路由
    def route_to_subgraph(state: MainState) -> str:
        return f"{state['task_type']}_coordinator"
    
    graph.add_conditional_edges(
        "task_router",
        route_to_subgraph,
        {
            "research_coordinator": "research_coordinator",
            "writing_coordinator": "writing_coordinator",
            "analysis_coordinator": "analysis_coordinator",
        }
    )
    
    # 所有协调器连接到 END
    graph.add_edge("research_coordinator", END)
    graph.add_edge("writing_coordinator", END)
    graph.add_edge("analysis_coordinator", END)
    
    return graph.compile()


# ============================================================
# 7. 演示
# ============================================================

def demo_subgraphs():
    """演示: 子图模块化"""
    print_separator("演示: 子图模块化")
    
    main_app = build_main_graph()
    
    test_cases = [
        ("研究人工智能的最新进展", "research"),
        ("写一篇关于气候变化的文章", "writing"),
        ("分析销售数据", "analysis"),
    ]
    
    for text, expected_type in test_cases:
        print(f"\n{'='*50}")
        print(f"测试: {text}")
        print(f"预期任务类型: {expected_type}")
        print(f"{'='*50}")
        
        initial_state = {
            "messages": [HumanMessage(content=text)],
            "task_type": "",
            "result": "",
        }
        
        final_state = main_app.invoke(initial_state)
        
        print(f"\n最终结果:")
        print(f"  任务类型: {final_state['task_type']}")
        print(f"  结果: {final_state['result'][:80]}...")


def demo_individual_subgraphs():
    """演示: 单独测试各个子图"""
    print_separator("演示: 单独测试子图")
    
    # 测试研究子图
    print("\n1. 研究子图测试")
    print("-" * 50)
    research_graph = build_research_subgraph()
    research_result = research_graph.invoke({
        "messages": [HumanMessage(content="测试研究")],
        "query": "量子计算",
        "research_data": "",
        "summary": "",
    })
    print(f"研究摘要: {research_result['summary']}")
    
    # 测试写作子图
    print("\n2. 写作子图测试")
    print("-" * 50)
    writing_graph = build_writing_subgraph()
    writing_result = writing_graph.invoke({
        "messages": [HumanMessage(content="测试写作")],
        "topic": "机器学习入门",
        "outline": "",
        "draft": "",
        "final_content": "",
    })
    print(f"最终内容: {writing_result['final_content'][:80]}...")
    
    # 测试分析子图
    print("\n3. 分析子图测试")
    print("-" * 50)
    analysis_graph = build_analysis_subgraph()
    analysis_result = analysis_graph.invoke({
        "messages": [HumanMessage(content="测试分析")],
        "data": "销售数据: Q1 100万, Q2 150万, Q3 200万",
        "analysis_result": "",
    })
    print(f"分析结果: {analysis_result['analysis_result']}")


def show_subgraph_patterns():
    """展示: 子图设计模式"""
    print_separator("子图设计模式总结")
    
    print("""
子图模块化优势:

1. 关注点分离
   - 每个子图负责一个明确的功能
   - 主图只负责协调，不处理具体逻辑
   - 代码更清晰，易于理解

2. 可复用性
   - 子图可以在多个主图中复用
   - 例如: 研究子图可用于多个项目
   - 减少重复代码

3. 可测试性
   - 每个子图可以独立测试
   - 不需要运行整个系统
   - 单元测试更简单

4. 可维护性
   - 修改子图不影响主图
   - 新增功能只需添加新子图
   - 团队协作更容易

5. 可视化
   - 子图可以独立可视化
   - 主图展示高层流程
   - 子图展示详细逻辑

设计原则:
✓ 子图应该有明确的输入/输出接口
✓ 子图之间应该低耦合
✓ 主图应该高内聚 (只做协调)
✓ 子图状态应该独立于主图状态

实际应用:
- 客服系统: 意图识别 → 不同业务子图
- 数据处理: ETL 子图 + 分析子图 + 可视化子图
- 内容生成: 研究子图 + 写作子图 + 审核子图
""")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  04 - LangGraph 子图模块化")
    print("=" * 60)
    print()
    print("子图核心概念:")
    print("  • 模块化: 将功能拆分为独立子图")
    print("  • 协调: 主图负责路由和协调")
    print("  • 复用: 子图可在多处使用")
    print("  • 分离: 关注点分离，各司其职")
    print()
    
    # 运行演示
    demo_individual_subgraphs()
    demo_subgraphs()
    show_subgraph_patterns()
    
    print_separator("总结")
    print("✓ 理解了子图的概念和用途")
    print("✓ 掌握了如何构建和调用子图")
    print("✓ 看到了模块化设计的优势")
    print()
    print("阶段 4 完成！")
    print("下一步: 阶段 5 - MCP 协议 (05_mcp/)")
