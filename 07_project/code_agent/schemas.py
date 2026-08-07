"""
schemas.py - 代码助手的结构化数据模型 (阶段 1 结构化输出)

代码助手是一条"生成-测试-修复"的闭环流水线。为了让程序能可靠地驱动这个
闭环, 每个阶段的产出都用 Pydantic 建模:

    CodePlan   规划器的产出: 理解需求 + 函数签名 + 测试用例
    CodeAttempt 编码器的产出: 一份可运行的代码
    TestReport  沙箱执行的产出: 测试是否通过 + 失败详情

其中 TestReport 不是 LLM 生成的, 而是"真实运行代码"得到的客观事实 ——
这正是代码助手比纯聊天靠谱的关键: 它的反思有事实依据, 不是自我感觉良好。
"""

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """一个测试用例: 调用表达式 + 期望结果表达式。"""

    description: str = Field(description="这个用例在验证什么")
    call: str = Field(description="调用表达式, 如 'add(2, 3)'")
    expected: str = Field(description="期望结果的 Python 字面量, 如 '5'")


class CodePlan(BaseModel):
    """规划器的产出: 把自然语言需求变成明确的实现契约。"""

    understanding: str = Field(description="用一句话复述你对需求的理解")
    function_name: str = Field(description="要实现的函数名")
    signature: str = Field(description="函数签名, 如 'def add(a: int, b: int) -> int'")
    approach: list[str] = Field(description="实现思路的分步骤要点")
    test_cases: list[TestCase] = Field(description="3-5 个覆盖正常与边界情况的测试用例")


class CodeAttempt(BaseModel):
    """编码器的产出: 一次代码实现尝试。"""

    code: str = Field(description="完整的函数实现代码 (只含函数定义, 不含测试)")
    explanation: str = Field(description="简要说明实现思路或这次相比上次改了什么")


class TestReport(BaseModel):
    """沙箱执行测试的客观结果 (由程序生成, 非 LLM)。"""

    passed: bool = Field(description="是否全部测试通过")
    total: int = Field(description="测试用例总数")
    failed: int = Field(description="失败的用例数")
    details: str = Field(description="失败详情或错误堆栈 (供反思修复使用)")
