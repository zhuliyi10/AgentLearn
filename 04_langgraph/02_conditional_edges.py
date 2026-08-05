"""
02 - LangGraph 条件路由

学习目标:
- 掌握条件边的实现方式: 路由函数 + 映射
- 理解动态决策: 根据状态决定下一步
- 实现分支逻辑: 不同条件走不同路径
- 对比条件路由与硬编码路由的区别

核心思想:
    硬编码路由:  A → B → C (固定流程)
    条件路由:    A → (根据状态) → B 或 C 或 D (动态决策)
    
    优势: 灵活、智能、可处理复杂场景

运行方式:
    python 04_langgraph/02_conditional_edges.py
"""

import sys
from pathlib import Path
from typing import Annotated, Literal, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from utils.helpers import print_separator


# ============================================================
# 1. 定义 State
# ============================================================

class RouterState(TypedDict):
    """
    路由状态
    
    包含路由决策所需的所有信息:
    - messages: 对话历史
    - intent: 识别的意图 (用于路由决策)
    - confidence: 意图识别的置信度
    - route: 路由目标
    """
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str  # 意图: "question", "task", "chitchat"
    confidence: float  # 置信度: 0.0 - 1.0
    route: str  # 路由目标: "qa", "task_executor", "chitchat", "fallback"


# ============================================================
# 2. 意图识别节点
# ============================================================

def intent_classifier(state: RouterState) -> dict:
    """
    意图分类器: 识别用户意图
    
    这是路由决策的第一步:
    1. 分析用户输入
    2. 识别意图类别
    3. 给出置信度评分
    4. 为后续路由提供依据
    """
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    print(f"\n[intent_classifier] 分析用户输入: {user_text[:50]}...")
    
    # 简单的规则匹配 (实际项目中用 LLM 或分类模型)
    intent = "chitchat"
    confidence = 0.5
    
    if any(kw in user_text for kw in ["什么", "如何", "为什么", "怎么", "what", "how", "why"]):
        intent = "question"
        confidence = 0.85
        print(f"  → 识别为: 问题类 (confidence: {confidence})")
    elif any(kw in user_text for kw in ["帮我", "请", "执行", "创建", "生成", "help", "create"]):
        intent = "task"
        confidence = 0.90
        print(f"  → 识别为: 任务类 (confidence: {confidence})")
    else:
        intent = "chitchat"
        confidence = 0.70
        print(f"  → 识别为: 闲聊类 (confidence: {confidence})")
    
    return {
        "intent": intent,
        "confidence": confidence,
    }


# ============================================================
# 3. 路由决策节点
# ============================================================

def route_decision(state: RouterState) -> dict:
    """
    路由决策: 根据意图和置信度决定路由
    
    路由策略:
    - 高置信度 + 问题意图 → qa (问答处理器)
    - 高置信度 + 任务意图 → task_executor (任务执行器)
    - 高置信度 + 闲聊意图 → chitchat (闲聊处理器)
    - 低置信度 → fallback (降级处理)
    """
    intent = state["intent"]
    confidence = state["confidence"]
    
    print(f"\n[route_decision] 意图: {intent}, 置信度: {confidence:.2f}")
    
    # 路由逻辑
    if confidence < 0.6:
        route = "fallback"
        print(f"  → 路由到: fallback (置信度过低)")
    elif intent == "question":
        route = "qa"
        print(f"  → 路由到: qa")
    elif intent == "task":
        route = "task_executor"
        print(f"  → 路由到: task_executor")
    elif intent == "chitchat":
        route = "chitchat"
        print(f"  → 路由到: chitchat")
    else:
        route = "fallback"
        print(f"  → 路由到: fallback (未知意图)")
    
    return {"route": route}


# ============================================================
# 4. 处理器节点
# ============================================================

def qa_handler(state: RouterState) -> dict:
    """问答处理器: 处理问题类意图"""
    print("\n[qa_handler] 处理问题...")
    
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    response = f"这是一个很好的问题！关于 '{user_text[:30]}...'，我的回答是：这是一个需要深入分析的话题。"
    
    return {
        "messages": [AIMessage(content=response)],
    }


def task_executor(state: RouterState) -> dict:
    """任务执行器: 处理任务类意图"""
    print("\n[task_executor] 执行任务...")
    
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    response = f"好的，我来帮你完成任务：'{user_text[:30]}...'。任务已执行完毕。"
    
    return {
        "messages": [AIMessage(content=response)],
    }


def chitchat_handler(state: RouterState) -> dict:
    """闲聊处理器: 处理闲聊类意图"""
    print("\n[chitchat_handler] 闲聊回应...")
    
    response = "聊天很有趣！有什么我可以帮你的吗？"
    
    return {
        "messages": [AIMessage(content=response)],
    }


def fallback_handler(state: RouterState) -> dict:
    """降级处理器: 无法识别意图时的处理"""
    print("\n[fallback_handler] 降级处理...")
    
    response = "抱歉，我不太理解你的意思。能否换个方式描述？"
    
    return {
        "messages": [AIMessage(content=response)],
    }


# ============================================================
# 5. 构建条件路由图
# ============================================================

def build_router_graph() -> StateGraph:
    """
    构建带条件路由的图
    
    流程:
    START → intent_classifier → route_decision → (条件路由)
                                                      ↓
                                              ┌───────┴───────┬──────────┐
                                              ↓               ↓          ↓
                                            qa_handler    task_executor  ...
                                              ↓               ↓          ↓
                                              └───────┬───────┴──────────┘
                                                      ↓
                                                     END
    """
    graph = StateGraph(RouterState)
    
    # 添加节点
    graph.add_node("intent_classifier", intent_classifier)
    graph.add_node("route_decision", route_decision)
    graph.add_node("qa", qa_handler)
    graph.add_node("task_executor", task_executor)
    graph.add_node("chitchat", chitchat_handler)
    graph.add_node("fallback", fallback_handler)
    
    # 添加固定边
    graph.add_edge(START, "intent_classifier")
    graph.add_edge("intent_classifier", "route_decision")
    
    # 添加条件边: 核心路由逻辑
    def route_after_decision(state: RouterState) -> str:
        """路由函数: 返回下一个节点名称"""
        return state["route"]
    
    graph.add_conditional_edges(
        "route_decision",  # 源节点
        route_after_decision,  # 路由函数
        {
            "qa": "qa",
            "task_executor": "task_executor",
            "chitchat": "chitchat",
            "fallback": "fallback",
        }
    )
    
    # 所有处理器都连接到 END
    graph.add_edge("qa", END)
    graph.add_edge("task_executor", END)
    graph.add_edge("chitchat", END)
    graph.add_edge("fallback", END)
    
    return graph.compile()


# ============================================================
# 6. 高级: 多级路由
# ============================================================

class AdvancedState(TypedDict):
    """高级路由状态: 包含更多决策信息"""
    messages: Annotated[list[BaseMessage], add_messages]
    user_type: str  # "new" | "returning" | "premium"
    request_complexity: str  # "simple" | "complex"
    route: str


def user_classifier(state: AdvancedState) -> dict:
    """用户分类: 识别用户类型"""
    print("\n[user_classifier] 分类用户类型...")
    
    # 简化: 实际项目中从数据库或 session 获取
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    if "VIP" in user_text or "高级" in user_text:
        user_type = "premium"
    elif "第一次" in user_text or "新" in user_text:
        user_type = "new"
    else:
        user_type = "returning"
    
    print(f"  → 用户类型: {user_type}")
    return {"user_type": user_type}


def complexity_analyzer(state: AdvancedState) -> dict:
    """复杂度分析: 评估请求复杂度"""
    print("\n[complexity_analyzer] 分析请求复杂度...")
    
    last_message = state["messages"][-1]
    user_text = last_message.content if hasattr(last_message, "content") else str(last_message)
    
    # 简单规则: 文本长度 > 50 或包含多个步骤
    if len(user_text) > 50 or user_text.count("然后") > 1:
        complexity = "complex"
    else:
        complexity = "simple"
    
    print(f"  → 复杂度: {complexity}")
    return {"request_complexity": complexity}


def advanced_router(state: AdvancedState) -> dict:
    """
    高级路由: 综合考虑用户类型和请求复杂度
    
    路由策略:
    - premium + complex → premium_complex_handler
    - premium + simple → premium_simple_handler
    - new + any → onboarding_handler
    - returning + complex → complex_handler
    - returning + simple → simple_handler
    """
    user_type = state["user_type"]
    complexity = state["request_complexity"]
    
    print(f"\n[advanced_router] 用户: {user_type}, 复杂度: {complexity}")
    
    if user_type == "new":
        route = "onboarding"
    elif user_type == "premium" and complexity == "complex":
        route = "premium_complex"
    elif user_type == "premium" and complexity == "simple":
        route = "premium_simple"
    elif complexity == "complex":
        route = "complex"
    else:
        route = "simple"
    
    print(f"  → 路由到: {route}")
    return {"route": route}


def build_advanced_router() -> StateGraph:
    """构建高级多级路由器"""
    graph = StateGraph(AdvancedState)
    
    # 添加节点
    graph.add_node("user_classifier", user_classifier)
    graph.add_node("complexity_analyzer", complexity_analyzer)
    graph.add_node("advanced_router", advanced_router)
    
    # 处理器节点
    graph.add_node("onboarding", lambda state: {"messages": [AIMessage(content="欢迎新用户！让我来介绍我们的产品...")]})
    graph.add_node("premium_complex", lambda state: {"messages": [AIMessage(content="尊贵的VIP用户，我已为您启动高级服务...")]})
    graph.add_node("premium_simple", lambda state: {"messages": [AIMessage(content="VIP用户专属快速通道...")]})
    graph.add_node("complex", lambda state: {"messages": [AIMessage(content="这是一个复杂的请求，让我详细分析...")]})
    graph.add_node("simple", lambda state: {"messages": [AIMessage(content="好的，我来快速处理...")]})
    
    # 连接
    graph.add_edge(START, "user_classifier")
    graph.add_edge("user_classifier", "complexity_analyzer")
    graph.add_edge("complexity_analyzer", "advanced_router")
    
    # 条件路由
    graph.add_conditional_edges(
        "advanced_router",
        lambda state: state["route"],
        {
            "onboarding": "onboarding",
            "premium_complex": "premium_complex",
            "premium_simple": "premium_simple",
            "complex": "complex",
            "simple": "simple",
        }
    )
    
    # 所有处理器连接到 END
    for node in ["onboarding", "premium_complex", "premium_simple", "complex", "simple"]:
        graph.add_edge(node, END)
    
    return graph.compile()


# ============================================================
# 7. 演示
# ============================================================

def demo_basic_routing():
    """演示: 基础条件路由"""
    print_separator("演示 1: 基础条件路由")
    
    app = build_router_graph()
    
    test_cases = [
        ("Python 如何学习？", "问题类"),
        ("帮我生成一份报告", "任务类"),
        ("今天天气不错", "闲聊类"),
        ("asdfghjkl", "低置信度"),
    ]
    
    for text, expected in test_cases:
        print(f"\n{'='*50}")
        print(f"测试: {text} (预期: {expected})")
        print(f"{'='*50}")
        
        initial_state = {
            "messages": [HumanMessage(content=text)],
            "intent": "",
            "confidence": 0.0,
            "route": "",
        }
        
        final_state = app.invoke(initial_state)
        
        print(f"\n最终路由: {final_state['route']}")
        print(f"助手回复: {final_state['messages'][-1].content[:60]}...")


def demo_advanced_routing():
    """演示: 高级多级路由"""
    print_separator("演示 2: 高级多级路由")
    
    app = build_advanced_router()
    
    test_cases = [
        ("我是新用户", "新用户引导"),
        ("我是VIP用户，需要复杂的分析", "VIP复杂"),
        ("我是VIP用户，快速查询", "VIP简单"),
        ("分析这个复杂的数据集，然后生成报告，然后发送邮件", "复杂请求"),
        ("查询余额", "简单请求"),
    ]
    
    for text, expected in test_cases:
        print(f"\n{'='*50}")
        print(f"测试: {text}")
        print(f"预期: {expected}")
        print(f"{'='*50}")
        
        initial_state = {
            "messages": [HumanMessage(content=text)],
            "user_type": "",
            "request_complexity": "",
            "route": "",
        }
        
        final_state = app.invoke(initial_state)
        
        print(f"\n最终路由: {final_state['route']}")
        print(f"用户类型: {final_state['user_type']}")
        print(f"复杂度: {final_state['request_complexity']}")
        print(f"助手回复: {final_state['messages'][-1].content[:60]}...")


def show_routing_patterns():
    """展示: 路由模式总结"""
    print_separator("条件路由模式总结")
    
    print("""
常见路由模式:

1. 意图路由 (本课示例)
   - 根据用户意图分类到不同处理器
   - 适用: 客服系统、智能助手
   
2. 权限路由
   - 根据用户角色/权限决定处理路径
   - 适用: SaaS 产品、多租户系统
   
3. 复杂度路由
   - 根据任务复杂度分配资源
   - 适用: 任务调度、资源分配
   
4. 状态机路由
   - 根据业务状态流转决定下一步
   - 适用: 订单处理、审批流程
   
5. 混合路由 (高级示例)
   - 多维度综合决策
   - 适用: 复杂业务场景

关键要点:
✓ 路由函数返回字符串 (下一个节点名)
✓ 路由映射: {返回值: 节点名}
✓ 路由决策基于 State 中的信息
✓ 可以串联多个路由节点 (多级路由)
""")


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  02 - LangGraph 条件路由")
    print("=" * 60)
    print()
    print("条件路由核心:")
    print("  • 路由函数: 根据状态返回下一个节点名")
    print("  • 路由映射: {返回值: 节点名}")
    print("  • 动态决策: 不同输入走不同路径")
    print()
    
    # 运行演示
    demo_basic_routing()
    demo_advanced_routing()
    show_routing_patterns()
    
    print_separator("总结")
    print("✓ 掌握了条件边的实现方式")
    print("✓ 理解了路由函数的作用")
    print("✓ 看到了多级路由的应用")
    print()
    print("下一步: 03_human_in_loop.py - 学习人工介入机制")
