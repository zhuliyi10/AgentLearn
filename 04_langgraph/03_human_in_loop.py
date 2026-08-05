"""
03 - LangGraph 人工介入

学习目标:
- 掌握 interrupt 机制: 在关键节点暂停等待人工输入
- 理解断点恢复: 从暂停点继续执行
- 实现审批节点: 人工审核 Agent 的决策
- 理解 human-in-the-loop 的应用场景

核心思想:
    全自动 Agent:  LLM 自主决策 → 执行工具 → 返回结果 (无人工参与)
    人工介入:     LLM 决策 → 暂停 → 人工审批 → 继续执行 (人在回路)
    
    优势: 安全可控、合规审计、错误拦截

运行方式:
    python 04_langgraph/03_human_in_loop.py
"""

import sys
from pathlib import Path
from typing import Annotated, Literal, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from utils.helpers import print_separator


# ============================================================
# 1. 定义 State
# ============================================================

class ApprovalState(TypedDict):
    """
    审批状态
    
    包含人工介入所需的信息:
    - messages: 对话历史
    - action: Agent 想要执行的动作
    - action_params: 动作参数
    - approval_status: 审批状态 (pending/approved/rejected)
    - human_feedback: 人工反馈
    """
    messages: Annotated[list[BaseMessage], add_messages]
    action: str  # 动作名称
    action_params: dict  # 动作参数
    approval_status: str  # "pending" | "approved" | "rejected"
    human_feedback: str  # 人工反馈


# ============================================================
# 2. Agent 决策节点
# ============================================================

def agent_planner(state: ApprovalState) -> dict:
    """
    Agent 规划器: 决定要执行的动作
    
    模拟 LLM 决策过程:
    1. 分析用户请求
    2. 决定执行什么动作
    3. 准备动作参数
    4. 等待人工审批
    """
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    print(f"\n[agent_planner] 分析用户请求: {user_text[:50]}...")
    
    # 模拟 LLM 决策 (实际项目中调用 LLM)
    if "删除" in user_text or "delete" in user_text.lower():
        action = "delete_data"
        params = {"target": "数据库记录", "reason": "用户请求删除"}
        print(f"  → 决策: 删除操作 (高风险)")
    elif "发送" in user_text or "send" in user_text.lower():
        action = "send_email"
        params = {"to": "user@example.com", "subject": "重要通知"}
        print(f"  → 决策: 发送邮件 (中风险)")
    elif "查询" in user_text or "query" in user_text.lower():
        action = "query_data"
        params = {"table": "users", "limit": 10}
        print(f"  → 决策: 查询数据 (低风险)")
    else:
        action = "general_action"
        params = {"description": "通用操作"}
        print(f"  → 决策: 通用操作")
    
    return {
        "action": action,
        "action_params": params,
        "approval_status": "pending",  # 等待审批
    }


# ============================================================
# 3. 人工审批节点 (使用 interrupt)
# ============================================================

def human_approval(state: ApprovalState) -> dict:
    """
    人工审批节点
    
    这是 LangGraph 的 interrupt 机制示例:
    - 图执行到这里会暂停
    - 等待人工输入
    - 人工可以 approve 或 reject
    - 图从暂停点继续执行
    
    注意: 实际使用时需要配合 checkpointer
    """
    print(f"\n[human_approval] 等待人工审批...")
    print(f"  动作: {state['action']}")
    print(f"  参数: {state['action_params']}")
    print(f"  状态: {state['approval_status']}")
    
    # 如果已经有审批结果，直接返回
    if state["approval_status"] in ["approved", "rejected"]:
        print(f"  ✓ 已审批: {state['approval_status']}")
        return {}
    
    # 模拟人工审批 (实际项目中通过 API 或 UI 获取)
    print("\n" + "="*50)
    print("人工审批界面 (模拟)")
    print("="*50)
    print(f"Agent 想要执行: {state['action']}")
    print(f"参数: {state['action_params']}")
    print("\n请选择:")
    print("  1. 批准 (approve)")
    print("  2. 拒绝 (reject)")
    print("  3. 修改后批准 (modify)")
    
    # 模拟用户输入 (实际项目中从 UI/API 获取)
    # 这里根据动作的风险等级自动决策
    if state["action"] == "delete_data":
        decision = "reject"  # 高风险操作，拒绝
        feedback = "删除操作风险太高，请先备份数据"
        print(f"\n模拟决策: {decision}")
        print(f"反馈: {feedback}")
    elif state["action"] == "send_email":
        decision = "approved"  # 中风险，批准
        feedback = "可以发送"
        print(f"\n模拟决策: {decision}")
        print(f"反馈: {feedback}")
    elif state["action"] == "query_data":
        decision = "approved"  # 低风险，批准
        feedback = "查询操作安全"
        print(f"\n模拟决策: {decision}")
        print(f"反馈: {feedback}")
    else:
        decision = "approved"
        feedback = "通用操作已批准"
        print(f"\n模拟决策: {decision}")
        print(f"反馈: {feedback}")
    
    return {
        "approval_status": decision,
        "human_feedback": feedback,
    }


# ============================================================
# 4. 执行节点
# ============================================================

def action_executor(state: ApprovalState) -> dict:
    """
    动作执行器: 执行被批准的动作
    
    只有在 approval_status == "approved" 时才会执行
    """
    if state["approval_status"] != "approved":
        print(f"\n[action_executor] 动作未批准，跳过执行")
        return {
            "messages": [AIMessage(content=f"动作 {state['action']} 未执行: {state['human_feedback']}")],
        }
    
    print(f"\n[action_executor] 执行动作: {state['action']}")
    print(f"  参数: {state['action_params']}")
    
    # 模拟执行
    if state["action"] == "delete_data":
        result = "数据已删除"
    elif state["action"] == "send_email":
        result = "邮件已发送"
    elif state["action"] == "query_data":
        result = "查询完成，返回 10 条记录"
    else:
        result = "操作完成"
    
    print(f"  ✓ 结果: {result}")
    
    return {
        "messages": [AIMessage(content=f"✓ {result}")],
    }


# ============================================================
# 5. 构建带人工介入的图
# ============================================================

def build_approval_graph() -> StateGraph:
    """
    构建带人工审批的图
    
    流程:
    START → agent_planner → human_approval → action_executor → END
    
    关键: human_approval 节点使用 interrupt 机制
    """
    # 使用 MemorySaver 保存状态 (支持中断和恢复)
    checkpointer = MemorySaver()
    
    graph = StateGraph(ApprovalState)
    
    # 添加节点
    graph.add_node("agent_planner", agent_planner)
    graph.add_node("human_approval", human_approval)
    graph.add_node("action_executor", action_executor)
    
    # 添加边
    graph.add_edge(START, "agent_planner")
    graph.add_edge("agent_planner", "human_approval")
    graph.add_edge("human_approval", "action_executor")
    graph.add_edge("action_executor", END)
    
    # 编译图，启用 checkpointer
    return graph.compile(checkpointer=checkpointer)


# ============================================================
# 6. 高级: 条件审批
# ============================================================

def risk_assessor(state: ApprovalState) -> dict:
    """风险评估器: 评估动作风险等级"""
    print(f"\n[risk_assessor] 评估风险...")
    
    action = state["action"]
    
    if action == "delete_data":
        risk = "high"
    elif action == "send_email":
        risk = "medium"
    elif action == "query_data":
        risk = "low"
    else:
        risk = "medium"
    
    print(f"  动作: {action}")
    print(f"  风险等级: {risk}")
    
    return {"approval_status": f"risk_{risk}"}


def conditional_approval_router(state: ApprovalState) -> str:
    """条件审批路由: 根据风险等级决定是否需要人工审批"""
    risk_status = state["approval_status"]
    
    print(f"\n[conditional_approval_router] 风险状态: {risk_status}")
    
    if risk_status == "risk_high":
        print("  → 高风险: 需要人工审批")
        return "human_approval"
    elif risk_status == "risk_medium":
        print("  → 中风险: 快速审批")
        return "quick_approval"
    else:
        print("  → 低风险: 自动批准")
        return "auto_approve"


def quick_approval(state: ApprovalState) -> dict:
    """快速审批: 中风险操作的简化审批"""
    print(f"\n[quick_approval] 快速审批...")
    return {
        "approval_status": "approved",
        "human_feedback": "中风险操作已快速批准",
    }


def auto_approve(state: ApprovalState) -> dict:
    """自动批准: 低风险操作自动通过"""
    print(f"\n[auto_approve] 自动批准低风险操作")
    return {
        "approval_status": "approved",
        "human_feedback": "低风险操作自动批准",
    }


def build_conditional_approval_graph() -> StateGraph:
    """
    构建条件审批图
    
    流程:
    START → agent_planner → risk_assessor → (条件路由)
                                                  ↓
                                    ┌─────────────┼─────────────┐
                                    ↓             ↓             ↓
                              human_approval  quick_approval  auto_approve
                                    ↓             ↓             ↓
                                    └─────────────┴─────────────┘
                                                  ↓
                                          action_executor
                                                  ↓
                                                 END
    """
    checkpointer = MemorySaver()
    
    graph = StateGraph(ApprovalState)
    
    # 添加节点
    graph.add_node("agent_planner", agent_planner)
    graph.add_node("risk_assessor", risk_assessor)
    graph.add_node("human_approval", human_approval)
    graph.add_node("quick_approval", quick_approval)
    graph.add_node("auto_approve", auto_approve)
    graph.add_node("action_executor", action_executor)
    
    # 添加边
    graph.add_edge(START, "agent_planner")
    graph.add_edge("agent_planner", "risk_assessor")
    
    # 条件路由
    graph.add_conditional_edges(
        "risk_assessor",
        conditional_approval_router,
        {
            "human_approval": "human_approval",
            "quick_approval": "quick_approval",
            "auto_approve": "auto_approve",
        }
    )
    
    # 所有审批路径都连接到执行器
    graph.add_edge("human_approval", "action_executor")
    graph.add_edge("quick_approval", "action_executor")
    graph.add_edge("auto_approve", "action_executor")
    graph.add_edge("action_executor", END)
    
    return graph.compile(checkpointer=checkpointer)


# ============================================================
# 7. 演示
# ============================================================

def demo_basic_approval():
    """演示: 基础人工审批"""
    print_separator("演示 1: 基础人工审批")
    
    app = build_approval_graph()
    
    test_cases = [
        "删除所有旧数据",
        "发送通知邮件给用户",
        "查询用户列表",
    ]
    
    for text in test_cases:
        print(f"\n{'='*50}")
        print(f"测试: {text}")
        print(f"{'='*50}")
        
        # 配置 thread (用于追踪对话)
        config = {"configurable": {"thread_id": f"test_{hash(text) % 1000}"}}
        
        initial_state = {
            "messages": [HumanMessage(content=text)],
            "action": "",
            "action_params": {},
            "approval_status": "pending",
            "human_feedback": "",
        }
        
        # 运行图
        final_state = app.invoke(initial_state, config)
        
        print(f"\n最终状态:")
        print(f"  动作: {final_state['action']}")
        print(f"  审批: {final_state['approval_status']}")
        print(f"  反馈: {final_state['human_feedback']}")
        print(f"  结果: {final_state['messages'][-1].content[:60]}...")


def demo_conditional_approval():
    """演示: 条件审批 (根据风险等级)"""
    print_separator("演示 2: 条件审批")
    
    app = build_conditional_approval_graph()
    
    test_cases = [
        ("删除所有数据", "高风险 → 人工审批"),
        ("发送邮件通知", "中风险 → 快速审批"),
        ("查询用户列表", "低风险 → 自动批准"),
    ]
    
    for text, expected in test_cases:
        print(f"\n{'='*50}")
        print(f"测试: {text}")
        print(f"预期: {expected}")
        print(f"{'='*50}")
        
        config = {"configurable": {"thread_id": f"cond_{hash(text) % 1000}"}}
        
        initial_state = {
            "messages": [HumanMessage(content=text)],
            "action": "",
            "action_params": {},
            "approval_status": "pending",
            "human_feedback": "",
        }
        
        final_state = app.invoke(initial_state, config)
        
        print(f"\n最终状态:")
        print(f"  动作: {final_state['action']}")
        print(f"  审批: {final_state['approval_status']}")
        print(f"  反馈: {final_state['human_feedback']}")
        print(f"  结果: {final_state['messages'][-1].content[:60]}...")


def show_hitl_patterns():
    """展示: Human-in-the-Loop 模式"""
    print_separator("Human-in-the-Loop 模式总结")
    
    print("""
常见人工介入模式:

1. 审批模式 (本课示例)
   - Agent 决策 → 人工审批 → 执行/拒绝
   - 适用: 高风险操作、合规要求
   
2. 确认模式
   - Agent 准备执行 → 人工确认 → 继续
   - 适用: 重要操作、不可逆操作
   
3. 修正模式
   - Agent 生成内容 → 人工修正 → 使用修正后版本
   - 适用: 内容生成、代码生成
   
4. 选择模式
   - Agent 提供多个选项 → 人工选择 → 执行选中项
   - 适用: 创意工作、方案设计
   
5. 监督模式
   - Agent 持续执行 → 人工随时可中断 → 调整方向
   - 适用: 长时间任务、复杂任务

LangGraph 特性:
✓ MemorySaver: 保存状态，支持中断恢复
✓ interrupt: 在节点暂停等待人工输入
✓ Checkpoint: 持久化状态，可回溯
✓ Thread: 追踪对话/任务状态

关键要点:
• 人工介入增加安全性，但降低自动化程度
• 根据风险等级动态决定是否需要人工参与
• 保留完整的决策轨迹，便于审计
"""
    )


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  03 - LangGraph 人工介入")
    print("=" * 60)
    print()
    print("Human-in-the-Loop 核心:")
    print("  • interrupt: 在关键节点暂停")
    print("  • checkpointer: 保存状态，支持恢复")
    print("  • 人工审批: Agent 决策，人工把关")
    print()
    
    # 运行演示
    demo_basic_approval()
    demo_conditional_approval()
    show_hitl_patterns()
    
    print_separator("总结")
    print("✓ 理解了 interrupt 机制的作用")
    print("✓ 掌握了人工审批节点的实现")
    print("✓ 看到了条件审批的应用")
    print()
    print("下一步: 04_subgraph.py - 学习子图模块化")
