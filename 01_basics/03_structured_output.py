"""
03 - 结构化输出 (JSON Mode / Pydantic)

学习目标:
- 使用 response_format 强制 JSON 输出
- 用 Pydantic 模型定义输出结构并自动校验
- 理解结构化输出对 Agent 的重要性 (工具调用、状态管理)

运行方式:
    python 01_basics/03_structured_output.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field
from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 定义 Pydantic 模型 - 描述我们期望的输出结构
# ============================================================

class BookRecommendation(BaseModel):
    """书籍推荐的结构化输出"""
    title: str = Field(description="书籍标题")
    author: str = Field(description="作者")
    reason: str = Field(description="推荐理由，一句话")
    difficulty: str = Field(description="难度: 入门/进阶/高级")
    rating: float = Field(description="推荐评分 1-10", ge=1, le=10)


class CodeAnalysis(BaseModel):
    """代码分析的结构化输出"""
    language: str = Field(description="编程语言")
    functionality: str = Field(description="代码功能描述")
    issues: list[str] = Field(description="发现的问题列表")
    suggestions: list[str] = Field(description="改进建议列表")
    complexity: str = Field(description="时间复杂度")


def json_mode_basic():
    """示例1: JSON Mode - 强制输出合法 JSON"""
    print_separator("示例1: JSON Mode 基础")

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": "你是一个书籍推荐助手。请以 JSON 格式回答。"},
            {"role": "user", "content": "推荐一本学习 Python 的书，包含 title, author, reason 字段"},
        ],
        # 强制输出 JSON (模型保证输出合法 JSON)
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content
    print(f"原始输出:\n{result}")

    # 可以安全地解析为字典
    data = json.loads(result)
    print(f"\n解析后: {data}")


def structured_output_pydantic():
    """示例2: 使用 Pydantic 模型进行结构化输出 (推荐方式)"""
    print_separator("示例2: Pydantic 结构化输出")

    # 方式A: OpenAI 原生支持 (需要模型支持 Structured Outputs)
    #   response = client().beta.chat.completions.parse(
    #       model=get_model(),
    #       messages=[...],
    #       response_format=BookRecommendation,
    #   )
    #   book = response.choices[0].message.parsed
    #
    # 方式B: 兼容第三方 API (DeepSeek/智谱/Moonshot 等)
    #   使用 json_object 模式 + Pydantic 手动校验

    # 将 Pydantic 模型的 JSON Schema 嵌入 system prompt，引导模型输出
    schema_str = json.dumps(BookRecommendation.model_json_schema(), ensure_ascii=False, indent=2)

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": (
                "你是一个书籍推荐专家。请严格按照以下 JSON Schema 输出，只输出 JSON，不要输出其他内容。\n"
                f"JSON Schema:\n{schema_str}"
            )},
            {"role": "user", "content": "推荐一本学习 AI Agent 开发的书"},
        ],
        response_format={"type": "json_object"},  # 强制输出合法 JSON
    )

    # 手动用 Pydantic 校验并解析
    raw_content = response.choices[0].message.content
    book = BookRecommendation.model_validate_json(raw_content)

    # 直接获得类型安全的 Python 对象
    print(f"书名: {book.title}")
    print(f"作者: {book.author}")
    print(f"推荐理由: {book.reason}")
    print(f"难度: {book.difficulty}")
    print(f"评分: {book.rating}/10")
    print(f"\n类型: {type(book)}")  # <class 'BookRecommendation'>


def structured_output_complex():
    """示例3: 复杂结构化输出 - 代码分析"""
    print_separator("示例3: 复杂结构化输出")

    code_snippet = '''
def find_duplicates(lst):
    duplicates = []
    for i in range(len(lst)):
        for j in range(i+1, len(lst)):
            if lst[i] == lst[j] and lst[i] not in duplicates:
                duplicates.append(lst[i])
    return duplicates
'''

    schema_str = json.dumps(CodeAnalysis.model_json_schema(), ensure_ascii=False, indent=2)

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": (
                "你是一个代码分析专家，请分析给定的代码。请严格按照以下 JSON Schema 输出，只输出 JSON，不要输出其他内容。\n"
                f"JSON Schema:\n{schema_str}"
            )},
            {"role": "user", "content": f"分析以下代码:\n```python{code_snippet}```"},
        ],
        response_format={"type": "json_object"},
    )

    analysis = CodeAnalysis.model_validate_json(response.choices[0].message.content)
    print(f"语言: {analysis.language}")
    print(f"功能: {analysis.functionality}")
    print(f"复杂度: {analysis.complexity}")
    print(f"\n发现的问题:")
    for i, issue in enumerate(analysis.issues, 1):
        print(f"  {i}. {issue}")
    print(f"\n改进建议:")
    for i, sug in enumerate(analysis.suggestions, 1):
        print(f"  {i}. {sug}")


def why_structured_output_matters():
    """示例4: 为什么 Agent 需要结构化输出"""
    print_separator("示例4: 结构化输出与 Agent 的关系")

    print("""
结构化输出是 Agent 系统的基石:

1. 工具调用: Agent 决定调用哪个工具、传什么参数 → 结构化数据
2. 状态管理: Agent 的规划、记忆、反思 → 需要可靠解析
3. 多 Agent 通信: Agent 之间传递任务和信息 → 需要统一格式
4. 流程控制: 判断任务是否完成、是否需要重试 → 结构化标志

没有结构化输出，Agent 就无法可靠地:
- 解析 LLM 的决策
- 执行正确的动作
- 维护一致的状态

下一模块 (02_tool_calling) 将展示结构化输出如何驱动工具调用。
""")


if __name__ == "__main__":
    print("=== 03 结构化输出 ===\n")

    json_mode_basic()
    structured_output_pydantic()
    structured_output_complex()
    why_structured_output_matters()

    print_separator("阶段 1 完成!")
    print("你已掌握 LLM 交互的三大基础:")
    print("  1. Chat Completion API 调用")
    print("  2. 提示词工程技巧")
    print("  3. 结构化输出")
    print("\n下一阶段: 02_tool_calling/ - 工具调用 (Agent 的核心机制)")
