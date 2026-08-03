"""
01 - OpenAI Function Calling 机制

学习目标:
- 理解 Function Calling 的完整流程
- 掌握 tools 参数的 JSON Schema 定义方式
- 学会解析 tool_calls 并返回 tool role 消息
- 理解 parallel tool calls (并行工具调用)

核心流程:
    用户提问 → LLM 决定调用工具 → 返回 tool_calls
    → 我们执行工具 → 将结果以 tool role 返回 → LLM 生成最终回答

运行方式:
    python 02_tool_calling/01_function_calling.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 第一步: 定义工具的 JSON Schema
# ============================================================

# 工具定义列表 - 告诉 LLM 有哪些工具可用
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 '北京'、'上海'",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位",
                    },
                },
                "required": ["city"],  # 必填参数
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'",
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


# ============================================================
# 第二步: 实现工具的实际逻辑
# ============================================================

def get_weather(city: str, unit: str = "celsius") -> str:
    """模拟天气查询 (实际项目中会调用天气 API)"""
    # 模拟数据
    weather_data = {
        "北京": {"temp": 28, "condition": "晴", "humidity": 45},
        "上海": {"temp": 31, "condition": "多云", "humidity": 72},
        "深圳": {"temp": 33, "condition": "雷阵雨", "humidity": 85},
    }

    data = weather_data.get(city, {"temp": 25, "condition": "未知", "humidity": 50})
    temp = data["temp"]
    if unit == "fahrenheit":
        temp = temp * 9 / 5 + 32

    return json.dumps({
        "city": city,
        "temperature": temp,
        "unit": unit,
        "condition": data["condition"],
        "humidity": f"{data['humidity']}%",
    }, ensure_ascii=False)


def calculate(expression: str) -> str:
    """安全地计算数学表达式"""
    try:
        # 注意: 生产环境不应使用 eval，这里仅为演示
        allowed_names = {"abs": abs, "round": round, "min": min, "max": max}
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return json.dumps({"expression": expression, "result": result})
    except Exception as e:
        return json.dumps({"error": f"计算失败: {str(e)}"})


# 工具名称 → 函数的映射 (用于动态调用)
TOOL_FUNCTIONS = {
    "get_weather": get_weather,
    "calculate": calculate,
}


# ============================================================
# 第三步: 完整的 Function Calling 流程
# ============================================================

def demo_single_tool_call():
    """示例1: 单次工具调用"""
    print_separator("示例1: 单次工具调用")

    messages = [
        {"role": "system", "content": "你是一个助手。当用户的问题匹配可用工具时，直接调用工具，不要反问用户。对于未指定的可选参数，使用合理默认值。"},
        {"role": "user", "content": "北京今天天气怎么样？"},
    ]

    print(f"[用户]: {messages[-1]['content']}")

    # 第一次调用: LLM 决定是否使用工具
    response = client().chat.completions.create(
        model=get_model(),
        messages=messages,
        tools=TOOLS,  # 传入可用工具列表
    )

    msg = response.choices[0].message

    # 检查 LLM 是否决定调用工具
    if msg.tool_calls:
        print(f"\n[LLM 决策]: 需要调用工具")

        # 将 assistant 消息加入历史 (包含 tool_calls 信息)
        messages.append(msg)

        # 执行每个工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            print(f"  → 调用: {func_name}({func_args})")

            # 执行工具函数
            result = TOOL_FUNCTIONS[func_name](**func_args)
            print(f"  ← 结果: {result}")

            # 将工具结果以 tool role 返回给 LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,  # 必须匹配 tool_call 的 id
                "content": result,
            })

        # 第二次调用: LLM 基于工具结果生成最终回答
        final_response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=TOOLS,
        )

        print(f"\n[最终回答]: {final_response.choices[0].message.content}")
    else:
        # LLM 认为不需要工具，直接回答
        print(f"\n[直接回答]: {msg.content}")


def demo_parallel_tool_calls():
    """示例2: 并行工具调用 - LLM 可能一次请求多个工具，也可能分多轮调用"""
    print_separator("示例2: 并行工具调用 (循环处理)")

    messages = [
        {"role": "system", "content": "你是一个助手。当用户的问题匹配可用工具时，直接调用工具，不要反问用户。对于未指定的可选参数，使用合理默认值。尽量一次性并行调用所有需要的工具。"},
        {"role": "user", "content": "帮我查一下北京和上海的天气，再算一下 28+31 等于多少"},
    ]

    print(f"[用户]: {messages[-1]['content']}")

    # 循环处理: 模型可能分多轮调用工具
    round_num = 0
    while True:
        round_num += 1
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=TOOLS,
        )

        msg = response.choices[0].message

        # 没有 tool_calls → 模型给出了最终回答，退出循环
        if not msg.tool_calls:
            print(f"\n[最终回答]: {msg.content}")
            break

        print(f"\n[第 {round_num} 轮]: 调用 {len(msg.tool_calls)} 个工具")
        messages.append(msg)

        # 执行本轮所有工具调用
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            print(f"  → {func_name}({func_args})")

            result = TOOL_FUNCTIONS[func_name](**func_args)
            print(f"  ← {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })


def demo_no_tool_needed():
    """示例3: LLM 判断不需要工具"""
    print_separator("示例3: 无需工具的情况")

    messages = [
        {"role": "user", "content": "你好，介绍一下你自己"},
    ]

    print(f"[用户]: {messages[0]['content']}")

    response = client().chat.completions.create(
        model=get_model(),
        messages=messages,
        tools=TOOLS,
    )

    msg = response.choices[0].message

    if msg.tool_calls:
        print("[LLM 决策]: 调用工具")
    else:
        print(f"[LLM 决策]: 无需工具，直接回答")
        print(f"[回答]: {msg.content}")


if __name__ == "__main__":
    print("=== 01 Function Calling 机制 ===\n")

    demo_single_tool_call()
    demo_parallel_tool_calls()
    demo_no_tool_needed()

    print_separator("完成")
    print("核心要点:")
    print("  1. tools 参数定义工具 Schema (JSON Schema 格式)")
    print("  2. LLM 自主决定是否调用工具、调用哪个、传什么参数")
    print("  3. 我们负责执行工具，将结果以 tool role 返回")
    print("  4. tool_call_id 必须一一对应")
    print("\n下一步: 02_custom_tools.py - 构建更丰富的自定义工具")
