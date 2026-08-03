"""
02 - 提示词工程技巧

学习目标:
- 掌握 System Prompt 的设计方法
- 学习 Few-shot (少样本) 提示
- 理解 Chain-of-Thought (思维链) 推理
- 了解提示词对 Agent 行为的关键影响

运行方式:
    python 01_basics/02_prompt_engineering.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


def system_prompt_design():
    """示例1: System Prompt 设计 - 定义 Agent 的人格与约束"""
    print_separator("示例1: System Prompt 设计")

    # 好的 System Prompt 包含: 角色 + 能力 + 约束 + 输出格式
    system_prompt = """你是一个专业的代码审查助手。

## 角色
你是一位有10年经验的 Python 高级工程师。

## 能力
- 识别代码中的 bug、性能问题和安全漏洞
- 提供具体的改进建议和示例代码

## 约束
- 只关注最重要的 3 个问题，不要面面俱到
- 每个问题必须给出修复代码
- 语气专业但友好

## 输出格式
对每个问题使用以下格式:
**问题 N**: [问题描述]
**严重性**: 高/中/低
**修复**: [代码示例]
"""

    code_to_review = '''
def process_users(users):
    result = []
    for i in range(len(users)):
        if users[i]["age"] > 18:
            result.append(users[i]["name"].upper())
    return result
'''

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请审查以下代码:\n```python{code_to_review}```"},
        ],
    )

    print(response.choices[0].message.content)


def few_shot_prompting():
    """示例2: Few-shot 提示 - 通过示例教会模型特定格式"""
    print_separator("示例2: Few-shot 提示")

    messages = [
        {"role": "system", "content": "将用户输入的情感分类为: 正面/负面/中性。只输出分类结果。"},
        # Few-shot 示例: 通过 user/assistant 对提供范例
        {"role": "user", "content": "这个产品太棒了，物超所值！"},
        {"role": "assistant", "content": "正面"},
        {"role": "user", "content": "发货速度一般般吧"},
        {"role": "assistant", "content": "中性"},
        {"role": "user", "content": "质量太差了，用了一天就坏了"},
        {"role": "assistant", "content": "负面"},
        # 实际需要分类的输入
        {"role": "user", "content": "代码跑通了，虽然花了点时间但结果不错"},
    ]

    response = client().chat.completions.create(
        model=get_model(),
        messages=messages,
        temperature=0,  # 分类任务用低 temperature 保证一致性
    )

    print(f"分类结果: {response.choices[0].message.content}")
    print("\n要点: Few-shot 让模型理解你期望的输出格式，无需额外说明")


def chain_of_thought():
    """示例3: Chain-of-Thought 思维链 - 让模型逐步推理"""
    print_separator("示例3: Chain-of-Thought 思维链")

    math_problem = "一个书架有3层，每层放了8本书。小明从第一层拿走了2本，又在第三层放了5本。现在书架上一共有多少本书？"

    # 对比: 不用 CoT
    print("--- 不用思维链 ---")
    response_direct = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "user", "content": f"{math_problem}\n直接给出答案。"},
        ],
        temperature=0,
    )
    print(f"回复: {response_direct.choices[0].message.content}")

    # 使用 CoT: 要求逐步思考
    print("\n--- 使用思维链 ---")
    response_cot = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "user", "content": f"{math_problem}\n请一步一步思考，展示你的推理过程，最后给出答案。"},
        ],
        temperature=0,
    )
    print(f"回复: {response_cot.choices[0].message.content}")

    print("\n要点: CoT 对复杂推理任务特别有效，也是 ReAct Agent 的思想基础")


def prompt_for_agent():
    """示例4: 为 Agent 设计提示词 - 定义工具使用规范"""
    print_separator("示例4: Agent 提示词设计")

    # 这是 Agent 系统提示词的雏形 (后续模块会深入)
    agent_prompt = """你是一个研究助手 Agent。你可以使用以下工具:

## 可用工具
1. search(query): 搜索互联网信息
2. calculate(expression): 计算数学表达式
3. summarize(text): 总结长文本

## 工作流程
1. 分析用户问题，确定需要哪些信息
2. 使用工具获取信息 (每次只调用一个工具)
3. 基于获取的信息回答问题
4. 如果信息不足，继续使用工具补充

## 输出规范
- 调用工具时，输出: [TOOL: 工具名(参数)]
- 最终回答时，输出: [ANSWER: 你的回答]
"""

    print("Agent System Prompt 示例:")
    print(agent_prompt)
    print("要点: Agent 提示词需要明确定义 工具 + 流程 + 输出格式")
    print("这将在 02_tool_calling 和 03_agent_patterns 中深入实践")


if __name__ == "__main__":
    print("=== 02 提示词工程技巧 ===\n")

    system_prompt_design()
    few_shot_prompting()
    chain_of_thought()
    prompt_for_agent()

    print_separator("完成")
    print("恭喜！你已掌握核心提示词技巧。")
    print("下一步: 03_structured_output.py - 学习结构化输出")
