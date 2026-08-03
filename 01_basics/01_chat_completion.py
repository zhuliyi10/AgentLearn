"""
01 - Chat Completion 基础调用

学习目标:
- 理解 OpenAI Chat API 的基本结构
- 掌握 messages 中 system/user/assistant 三种角色
- 了解 temperature、max_tokens 等常用参数
- 体验流式输出 (streaming)

运行方式:
    python 01_basics/01_chat_completion.py
"""

import sys
from pathlib import Path

# 将项目根目录加入 path，以便导入 utils
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


def basic_chat():
    """示例1: 最基础的对话调用"""
    print_separator("示例1: 基础对话")

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            # system: 设定 AI 的角色和行为准则
            {"role": "system", "content": "你是一个友好的编程助手，回答简洁明了。"},
            # user: 用户的输入
            {"role": "user", "content": "用一句话解释什么是 Agent？"},
        ],
    )

    # 提取助手的回复
    assistant_message = response.choices[0].message.content
    print(f"回复: {assistant_message}")

    # 查看 token 使用情况
    usage = response.usage
    print(f"\nToken 使用: 输入={usage.prompt_tokens}, 输出={usage.completion_tokens}, 总计={usage.total_tokens}")


def multi_turn_chat():
    """示例2: 多轮对话 - 维护上下文"""
    print_separator("示例2: 多轮对话")

    # 对话历史列表 - 这是维护上下文的关键
    messages = [
        {"role": "system", "content": "你是一个 Python 教师，善于用类比解释概念。"},
    ]

    # 模拟多轮对话
    conversations = [
        "什么是列表推导式？",
        "能给一个过滤偶数的例子吗？",
        "它和 for 循环相比有什么优势？",
    ]

    for user_input in conversations:
        print(f"[用户]: {user_input}")

        # 将用户消息加入历史
        messages.append({"role": "user", "content": user_input})

        # 调用 API (每次都发送完整历史)
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
        )

        assistant_reply = response.choices[0].message.content
        print(f"[助手]: {assistant_reply}\n")

        # 将助手回复也加入历史 (关键！否则下一轮没有上下文)
        messages.append({"role": "assistant", "content": assistant_reply})


def streaming_chat():
    """示例3: 流式输出 - 逐字显示回复"""
    print_separator("示例3: 流式输出")

    print("[助手]: ", end="", flush=True)

    # stream=True 开启流式返回
    stream = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "user", "content": "用三句话介绍 Python 语言的特点"},
        ],
        stream=True,  # 关键参数
    )

    # 逐块读取响应
    for chunk in stream:
        # 每个 chunk 包含一小段文本
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)

    print()  # 换行


def temperature_demo():
    """示例4: temperature 参数对比"""
    print_separator("示例4: Temperature 对比")

    prompt = "给一个变量起一个有创意的名字，用于存储用户的年龄"

    for temp in [0.0, 0.5, 1.0]:
        response = client().chat.completions.create(
            model=get_model(),
            messages=[{"role": "user", "content": prompt}],
            temperature=temp,  # 0=确定性高, 1+=更随机有创意
            max_tokens=50,
        )
        reply = response.choices[0].message.content
        print(f"temperature={temp}: {reply}")


if __name__ == "__main__":
    print("=== 01 Chat Completion 基础 ===\n")
    print("提示: 确保已配置 .env 文件中的 OPENAI_API_KEY\n")

    # basic_chat()
    # multi_turn_chat()
    # streaming_chat()
    temperature_demo()

    print_separator("完成")
    print("恭喜！你已掌握 Chat API 的基本用法。")
    print("下一步: 02_prompt_engineering.py - 学习提示词工程技巧")
