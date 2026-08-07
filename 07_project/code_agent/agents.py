"""
agents.py - 代码助手的各个专职 Agent (综合阶段 1/3)

代码助手由两个 LLM 角色 + 一个执行工具协作:

    Planner  规划器 —— 读懂需求, 定下函数签名和测试用例   (阶段 3 Plan)
    Coder    编码器 —— 写实现; 失败时带着报错重写         (阶段 3 Reflection)
    (sandbox 执行测试是"工具", 见 sandbox.py)

关键点: 编码器的"反思"不是凭空自省, 而是拿着 **真实的测试报错** 去修 ——
这让 Reflection 循环有了客观的收敛信号 (测试全绿 = 完成)。
"""

from typing import Type, TypeVar

from pydantic import BaseModel

from utils.llm import client, get_model
from utils.helpers import json_skeleton
from .schemas import CodePlan, CodeAttempt, TestReport

T = TypeVar("T", bound=BaseModel)


def _structured(system: str, user: str, model_cls: Type[T], temperature: float = 0.2) -> T:
    """调用 LLM 并解析为指定 Pydantic 模型 (同研究助手, 阶段 1 结构化输出)。"""
    skeleton = json_skeleton(model_cls)
    full_system = (
        f"{system}\n\n"
        f"请只输出一个 JSON 对象, 结构严格如下 —— 把每个 <...> 占位替换成真实内容, "
        f"不要输出这段模板说明本身:\n{skeleton}"
    )
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return model_cls.model_validate_json(response.choices[0].message.content)


# ============================================================
# 1. Planner —— 读懂需求, 定契约 (阶段 3 Plan)
# ============================================================

def plan_task(requirement: str) -> CodePlan:
    """
    规划器: 把自然语言需求转成明确的实现契约 —— 函数签名 + 测试用例。

    先定测试用例再写代码, 是"测试驱动"的思路: 用例即需求的可执行规格,
    也成了后面反思循环的收敛目标。
    """
    system = (
        "你是一名资深工程师。用户会用自然语言描述一个函数需求。"
        "请先读懂需求, 确定函数名和签名, 给出实现思路, "
        "并设计 3-5 个测试用例 (覆盖正常情况和边界情况)。"
        "测试用例的 call 是调用表达式, expected 是期望结果的 Python 字面量。"
    )
    return _structured(system, f"需求: {requirement}", CodePlan, temperature=0.3)


# ============================================================
# 2. Coder —— 写代码 / 带报错改代码 (阶段 3 Reflection)
# ============================================================

def write_code(plan: CodePlan, last_attempt: CodeAttempt | None = None,
               last_report: TestReport | None = None) -> CodeAttempt:
    """
    编码器: 根据计划实现函数。

    首轮: 从零实现。
    后续轮: 带着"上一版代码 + 真实测试报错"重写 —— 这就是反思修复。
    """
    system = (
        "你是一名 Python 专家。请根据给定的计划实现函数。"
        "只输出函数定义本身 (可含必要的 import 和辅助函数), 不要写测试代码、"
        "不要写 print、不要有示例调用。确保代码能直接运行。"
    )
    user = (
        f"函数签名: {plan.signature}\n"
        f"需求理解: {plan.understanding}\n"
        f"实现思路: {plan.approach}"
    )
    # 反思分支: 把上一次的失败作为改进依据
    if last_attempt and last_report:
        user += (
            f"\n\n你上一版的代码:\n```python\n{last_attempt.code}\n```\n"
            f"运行测试后失败了, 报错如下:\n{last_report.details}\n\n"
            f"请分析失败原因并修正代码。"
        )
    return _structured(system, user, CodeAttempt, temperature=0.2)
