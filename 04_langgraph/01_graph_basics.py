"""
01 - LangGraph 图基础

学习目标:
- 理解 LangGraph 的核心概念: StateGraph、Node、Edge、State
- 掌握如何使用 LangGraph 构建有状态的工作流
- 理解状态驱动的执行模型
- 对比 LangGraph 与手写 Agent 循环的区别

核心思想:
    手写 Agent:   用 Python 代码手动管理状态和循环
    LangGraph:    用图结构声明式定义工作流，框架自动管理状态流转
    
    优势: 可视化、可调试、可持久化、可控制

运行方式:
    python 04_langgraph/01_graph_basics.py
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
# 1. 定义 State (状态)
# ============================================================

class AgentState(TypedDict):
    """
    Agent 状态定义
    
    State 是 LangGraph 的核心概念:
    - 所有节点共享同一个 State 对象
    - 节点通过读取 State 获取输入，通过返回更新来修改 State
    - State 的结构决定了整个图的数据流
    
    Annotated[list[BaseMessage], add_messages]:
    - 消息列表类型
    - add_messages 是 LangGraph 的 reducer，自动合并新消息
    - 每次节点返回 {"messages": [new_msg]} 时，会自动追加到列表
    """
    messages: Annotated[list[BaseMessage], add_messages]
    next_action: str  # 下一步动作: "continue" 或 "finish"


# ============================================================
# 2. 定义 Node (节点)
# ============================================================

def chatbot_node(state: AgentState) -> dict:
    """
    聊天机器人节点
    
    节点函数签名: (state: State) -> dict
    - 输入: 当前状态
    - 输出: 要更新的状态字段 (字典形式)
    
    注意: 返回的字典只包含要更新的字段，未返回的字段保持不变
    """
    print(f"\n[chatbot_node] 收到 {len(state['messages'])} 条消息")
    
    # 获取最后一条用户消息
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    print(f"[chatbot_node] 用户输入: {user_text}")
    
    # 简单的回应逻辑 (实际项目中这里调用 LLM)
    if "你好" in user_text or "hello" in user_text.lower():
        response = "你好！我是 LangGraph Agent，很高兴为你服务。"
        next_action = "finish"
    elif "帮助" in user_text or "help" in user_text.lower():
        response = "我可以帮你理解 LangGraph 的基本概念。你可以问我关于 State、Node、Edge 的问题。"
        next_action = "continue"
    elif "状态" in user_text or "state" in user_text.lower():
        response = "State 是 LangGraph 的核心，所有节点共享同一个 State 对象，通过返回字典来更新状态。"
        next_action = "finish"
    else:
        response = "我理解了你的问题。这是一个基础的 LangGraph 示例，展示了 State、Node、Edge 的概念。"
        next_action = "finish"
    
    print(f"[chatbot_node] 生成回复: {response[:50]}...")
    
    # 返回要更新的状态字段
    return {
        "messages": [AIMessage(content=response)],
        "next_action": next_action,
    }


def router_node(state: AgentState) -> dict:
    """
    路由节点: 决定下一步做什么
    
    这个节点展示了状态驱动的工作流:
    - 根据 state["next_action"] 决定下一步
    - 返回更新后的状态
    """
    print(f"\n[router_node] 当前 next_action: {state['next_action']}")
    
    if state["next_action"] == "continue":
        print("[router_node] 决定: 继续对话")
        return {"next_action": "continue"}
    else:
        print("[router_node] 决定: 结束对话")
        return {"next_action": "finish"}


# ============================================================
# 3. 构建 Graph (图)
# ============================================================

def build_simple_graph() -> StateGraph:
    """
    构建一个简单的 LangGraph 图
    
    图的组成:
    1. State: 定义数据结构
    2. Nodes: 定义处理逻辑
    3. Edges: 定义节点间的连接
    
    基本流程:
    START → chatbot_node → router_node → END
    """
    # 创建图，传入 State 类型
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("chatbot", chatbot_node)
    graph.add_node("router", router_node)
    
    # 添加边 (连接节点)
    graph.add_edge(START, "chatbot")  # 入口 → chatbot
    graph.add_edge("chatbot", "router")  # chatbot → router
    graph.add_edge("router", END)  # router → 出口
    
    # 编译图 (生成可执行的运行时)
    return graph.compile()


def build_conversational_graph() -> StateGraph:
    """
    构建一个带循环的对话图
    
    流程:
    START → chatbot → router → (如果 continue) → chatbot
                            → (如果 finish) → END
    
    这展示了如何用 LangGraph 实现循环逻辑
    """
    graph = StateGraph(AgentState)
    
    graph.add_node("chatbot", chatbot_node)
    graph.add_node("router", router_node)
    
    # 入口边
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", "router")
    
    # 条件边: 根据状态决定下一步
    def should_continue(state: AgentState) -> str:
        """路由函数: 返回下一个节点名称"""
        if state["next_action"] == "continue":
            return "chatbot"  # 回到 chatbot
        else:
            return END  # 结束
    
    graph.add_conditional_edges(
        "router",  # 源节点
        should_continue,  # 路由函数
        {
            "chatbot": "chatbot",  # 映射: 返回值 → 节点名
            END: END,
        }
    )
    
    return graph.compile()


# ============================================================
# 4. 运行 Graph
# ============================================================

def demo_simple_graph():
    """演示: 简单线性图"""
    print_separator("演示 1: 简单线性图")
    
    print("图结构: START → chatbot → router → END\n")
    
    app = build_simple_graph()
    
    # 初始状态
    initial_state = {
        "messages": [HumanMessage(content="你好，介绍一下 LangGraph")],
        "next_action": "continue",
    }
    
    print("初始状态:")
    print(f"  消息数: {len(initial_state['messages'])}")
    print(f"  next_action: {initial_state['next_action']}")
    
    # 运行图
    print("\n开始执行...")
    final_state = app.invoke(initial_state)
    
    print("\n最终状态:")
    print(f"  消息数: {len(final_state['messages'])}")
    print(f"  next_action: {final_state['next_action']}")
    
    print("\n对话历史:")
    for i, msg in enumerate(final_state["messages"], 1):
        role = "用户" if isinstance(msg, HumanMessage) else "助手"
        print(f"  {i}. [{role}]: {msg.content[:80]}...")


def demo_conversational_graph():
    """演示: 带循环的对话图"""
    print_separator("演示 2: 带循环的对话图")
    
    print("图结构: START → chatbot → router → (continue? chatbot : END)\n")
    
    app = build_conversational_graph()
    
    # 测试用例 1: 需要继续对话
    print("测试 1: 用户询问 '帮助'")
    state1 = {
        "messages": [HumanMessage(content="帮助")],
        "next_action": "continue",
    }
    final1 = app.invoke(state1)
    print(f"  最终消息数: {len(final1['messages'])}")
    print(f"  最后一条: {final1['messages'][-1].content[:60]}...")
    
    # 测试用例 2: 直接结束
    print("\n测试 2: 用户说 '你好'")
    state2 = {
        "messages": [HumanMessage(content="你好")],
        "next_action": "continue",
    }
    final2 = app.invoke(state2)
    print(f"  最终消息数: {len(final2['messages'])}")
    print(f"  最后一条: {final2['messages'][-1].content[:60]}...")


def demo_state_flow():
    """演示: 状态流转过程"""
    print_separator("演示 3: 状态流转可视化")
    
    print("让我们追踪状态在节点间的流转:\n")
    
    app = build_simple_graph()
    
    # 使用 stream 模式，可以看到每一步的执行
    initial_state = {
        "messages": [HumanMessage(content="LangGraph 的状态是什么？")],
        "next_action": "continue",
    }
    
    print("初始状态:")
    print(f"  messages: {len(initial_state['messages'])} 条")
    print(f"  next_action: '{initial_state['next_action']}'")
    
    print("\n执行流程:")
    step = 0
    for event in app.stream(initial_state):
        step += 1
        node_name = list(event.keys())[0]
        node_output = event[node_name]
        
        print(f"\n  步骤 {step}: {node_name}")
        if "messages" in node_output:
            print(f"    新增消息: {len(node_output['messages'])} 条")
        if "next_action" in node_output:
            print(f"    next_action: '{node_output['next_action']}'")
    
    print("\n✓ 执行完成")


# ============================================================
# 5. 对比: 手写 vs LangGraph
# ============================================================

def show_comparison():
    """展示: 手写 Agent vs LangGraph 对比"""
    print_separator("手写 Agent vs LangGraph 对比")
    
    print("""
┌─────────────────┬──────────────────────┬──────────────────────┐
│                 │ 手写 Agent (阶段3)   │ LangGraph            │
├─────────────────┼──────────────────────┼──────────────────────┤
│ 定义方式        │ 命令式 (Python 循环) │ 声明式 (图结构)      │
│ 状态管理        │ 手动维护变量         │ 框架自动管理         │
│ 控制流          │ if/else/while        │ 条件边、路由函数     │
│ 可视化          │ 无                   │ 可生成 Mermaid 图    │
│ 持久化          │ 需手动实现           │ 内置 Checkpoint      │
│ 人工介入        │ 需手动实现           │ 内置 interrupt       │
│ 调试            │ print 日志           │ LangSmith 集成       │
│ 学习曲线        │ 低 (纯 Python)       │ 中 (需理解图概念)    │
│ 灵活性          │ 高 (完全控制)        │ 中 (受框架约束)      │
│ 适合场景        │ 学习原理、简单场景   │ 生产环境、复杂工作流 │
└─────────────────┴──────────────────────┴──────────────────────┘

核心价值:
- 阶段3 手写: 理解 Agent 原理，掌握底层机制
- 阶段4 LangGraph: 学习工业级框架，为生产环境做准备

两者互补: 理解原理 + 掌握工具 = 真正的能力
""")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  01 - LangGraph 图基础")
    print("=" * 60)
    print()
    print("LangGraph 核心概念:")
    print("  • State: 共享的数据结构，所有节点读写")
    print("  • Node: 处理函数，读取 State，返回更新")
    print("  • Edge: 连接节点，定义执行流程")
    print("  • Graph: 编译后的可执行工作流")
    print()
    
    # 运行演示
    # demo_simple_graph()
    # demo_conversational_graph()
    # demo_state_flow()
    show_comparison()
    
    print_separator("总结")
    print("✓ 理解了 State、Node、Edge 的概念")
    print("✓ 掌握了如何构建简单的 LangGraph 图")
    print("✓ 看到了状态在节点间的流转过程")
    print()
    print("下一步: 02_conditional_edges.py - 学习条件路由和分支逻辑")
