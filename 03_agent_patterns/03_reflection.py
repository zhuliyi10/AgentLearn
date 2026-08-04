"""
03 - Reflection 自我反思模式

学习目标:
- 理解 Reflection 模式的核心: 生成 → 评估 → 改进 的迭代循环
- 实现 Generator (生成器) + Reflector (反思器) 双角色架构
- 掌握如何用 LLM 评估和改进自己的输出
- 理解 Reflection 在提升输出质量中的作用

核心思想:
    单次生成: 用户提问 → LLM 回答 (可能不够好)
    Reflection: 用户提问 → LLM 生成 → LLM 反思(评估) → LLM 改进 → 再反思 → ... → 最终输出

    关键: 用同一个 LLM 扮演不同角色 (生成者 vs 批评者)

运行方式:
    python 03_agent_patterns/03_reflection.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# Reflection Agent 实现
# ============================================================

GENERATOR_PROMPT = """你是一个写作助手。请根据用户要求生成内容。

## 要求
1. 严格按照用户的具体要求生成
2. 内容要有深度，不要泛泛而谈
3. 结构清晰，逻辑连贯
4. 语言流畅，表达精准
"""

REFLECTOR_PROMPT = """你是一个严格的评审专家。请对以下作品进行评审。

## 评审维度
1. 内容质量: 是否切题、有深度、信息准确
2. 结构逻辑: 是否条理清晰、层次分明
3. 表达质量: 是否语言流畅、用词精准
4. 完整性: 是否覆盖了所有要求

## 输出格式
请输出:
1. 评分 (1-10分)
2. 优点 (至少2点)
3. 改进建议 (至少2点，要具体可操作)
4. 是否通过 (pass/fail)

## 评审原则
- 严格但公正
- 指出问题时要给出具体修改建议
- 不要为了批评而批评，好的地方也要肯定
"""


def generate(initial_prompt: str) -> str:
    """生成器: 生成初始内容"""
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": GENERATOR_PROMPT},
            {"role": "user", "content": initial_prompt},
        ],
    )
    return response.choices[0].message.content


def reflect(content: str, original_prompt: str) -> dict:
    """反思器: 评估内容并给出反馈"""
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": REFLECTOR_PROMPT},
            {"role": "user", "content": f"原始要求:\n{original_prompt}\n\n待评审作品:\n{content}"},
        ],
    )
    review = response.choices[0].message.content

    # 解析评审结果
    passed = "pass" in review.lower() and "fail" not in review.lower()

    return {
        "review": review,
        "passed": passed,
    }


def improve(content: str, feedback: str, original_prompt: str) -> str:
    """改进器: 根据反馈改进内容"""
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": "你是一个写作助手。请根据评审反馈改进你的作品。"},
            {"role": "user", "content": f"""原始要求:
{original_prompt}

你的初稿:
{content}

评审反馈:
{feedback}

请根据反馈进行改进，输出改进后的完整作品。"""},
        ],
    )
    return response.choices[0].message.content


def reflection_agent(prompt: str, max_iterations: int = 3) -> dict:
    """
    Reflection Agent 主循环

    流程:
        1. Generate: 生成初始内容
        2. Reflect: 评估内容质量
        3. 如果通过或达到最大迭代 → 返回
        4. 否则 → Improve: 根据反馈改进 → 回到步骤2

    返回:
        包含最终内容和迭代历史的字典
    """
    print(f"\n[任务]: {prompt}")

    history = []

    # 步骤1: 生成初始内容
    print(f"\n{'='*50}")
    print("  第 1 轮: 生成")
    print(f"{'='*50}")

    current_content = generate(prompt)
    print(f"\n[生成内容]:\n{current_content[:300]}...")

    history.append({
        "iteration": 1,
        "content": current_content,
        "action": "generate",
    })

    # 步骤2-4: 反思-改进循环
    for iteration in range(2, max_iterations + 1):
        print(f"\n{'='*50}")
        print(f"  第 {iteration} 轮: 反思")
        print(f"{'='*50}")

        # 反思
        review_result = reflect(current_content, prompt)
        print(f"\n[评审结果]:\n{review_result['review']}")

        history.append({
            "iteration": iteration,
            "action": "reflect",
            "review": review_result["review"],
        })

        # 检查是否通过
        if review_result["passed"]:
            print(f"\n✓ 评审通过！")
            break

        # 改进
        print(f"\n{'='*50}")
        print(f"  第 {iteration} 轮: 改进")
        print(f"{'='*50}")

        current_content = improve(current_content, review_result["review"], prompt)
        print(f"\n[改进后内容]:\n{current_content[:300]}...")

        history.append({
            "iteration": iteration,
            "content": current_content,
            "action": "improve",
        })

    return {
        "final_content": current_content,
        "history": history,
        "iterations": len([h for h in history if h["action"] == "reflect"]),
    }


# ============================================================
# 演示
# ============================================================

def demo_reflection():
    """演示: Reflection 提升写作质量"""
    print_separator("Reflection 演示: 写作改进")

    prompt = "写一段关于'为什么程序员应该学习 AI Agent 开发'的短文，要求200字左右，有说服力。"

    result = reflection_agent(prompt, max_iterations=3)

    print(f"\n{'='*50}")
    print("  最终作品")
    print(f"{'='*50}")
    print(result["final_content"])
    print(f"\n迭代次数: {result['iterations']}")


def demo_code_reflection():
    """演示: Reflection 改进代码"""
    print_separator("Reflection 演示: 代码改进")

    prompt = """写一个 Python 函数，实现以下功能:
输入一个字符串列表，返回去重后的列表，保持原始顺序。
要求: 有类型注解、有文档字符串、处理边界情况。"""

    result = reflection_agent(prompt, max_iterations=2)

    print(f"\n{'='*50}")
    print("  最终代码")
    print(f"{'='*50}")
    print(result["final_content"])


def demo_comparison():
    """演示: 不同 Agent 模式对比"""
    print_separator("Agent 模式总结")

    print("""
目前学到的三种 Agent 模式:

┌─────────────────────┬──────────────┬──────────────┬──────────────┐
│                     │ ReAct        │ Plan-Execute │ Reflection   │
├─────────────────────┼──────────────┼──────────────┼──────────────┤
│ 核心思想            │ 推理+行动    │ 先规划后执行 │ 生成+反思    │
│ 循环结构            │ T→A→O 循环   │ Plan→Execute │ G→R→I 循环   │
│ 主要目标            │ 解决问题     │ 完成任务     │ 提升质量     │
│ 适合场景            │ 问答/搜索    │ 复杂多步     │ 写作/代码    │
│ 关键组件            │ 工具         │ 规划器       │ 反思器       │
│ 输出特点            │ 答案         │ 报告         │ 高质量内容   │
└─────────────────────┴──────────────┴──────────────┴──────────────┘

组合使用:
- ReAct + Reflection: 推理过程中加入自我反思
- Plan-Execute + Reflection: 执行后反思计划质量
- 实际 Agent 系统通常组合多种模式
""")


if __name__ == "__main__":
    print("=== 03 Reflection 自我反思模式 ===\n")

    demo_comparison()
    demo_reflection()
    # demo_code_reflection()  # 取消注释可体验代码改进

    print_separator("完成")
    print("下一步: 04_memory.py - 记忆机制")
