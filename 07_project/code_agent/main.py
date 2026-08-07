"""
main.py - 代码助手主流程 (端到端项目 B)

这是阶段 7 的第二个综合项目。它是一个会自测、能自我修复的代码 Agent:

    自然语言需求
       │
       ▼  ① 规划 (Planner)         —— 阶段 3 Plan: 定签名 + 测试用例
    函数契约 + 测试用例
       │
       ▼  ② 编码 (Coder)           —— 阶段 3 Action: 生成实现
    一份代码
       │
       ▼  ③ 执行测试 (sandbox)      —— 阶段 2 工具: 子进程真实运行
    TestReport (客观事实)
       │
       ├─ 全绿 ─────────────────▶ 完成, 输出代码
       │
       ▼  否则 ④ 反思修复 (Coder 带报错重写)  —— 阶段 3 Reflection Loop
       └───────────────── 回到 ③ 再测 ───────┘

与研究助手最大的不同: 这里的反思循环有 **客观的收敛信号** (测试是否通过),
而不是让 LLM 主观判断"够好了没"。

运行方式:
    python 07_project/code_agent/main.py
"""

import sys
from pathlib import Path

# 直接运行时需要: 项目根目录 (导入 utils) + 阶段目录 (导入 code_agent 包)
_ROOT = Path(__file__).resolve().parent.parent.parent
_STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_STAGE))

from utils.helpers import print_separator
from code_agent.agents import plan_task, write_code
from code_agent.sandbox import run_tests


def run_code_agent(requirement: str, max_fixes: int = 3) -> str:
    """
    运行"生成-测试-修复"闭环, 返回最终通过测试的代码 (或最后一版)。

    参数:
        requirement: 自然语言需求
        max_fixes:   反思修复的最大轮数 (安全阀)
    """
    # ---------- ① 规划 ----------
    print_separator("① 规划 (Planner)")
    plan = plan_task(requirement)
    print(f"[理解]: {plan.understanding}")
    print(f"[签名]: {plan.signature}")
    print("[测试用例]:")
    for tc in plan.test_cases:
        print(f"  - {tc.description}: {tc.call} == {tc.expected}")

    attempt = None
    report = None

    # ---------- ②③④ 生成 → 测试 → 反思 循环 ----------
    for round_no in range(1, max_fixes + 2):  # 1 次初版 + max_fixes 次修复
        stage = "编码" if round_no == 1 else f"反思修复 (第 {round_no - 1} 次)"
        print_separator(f"② 编码 / {stage}")

        attempt = write_code(plan, last_attempt=attempt, last_report=report)
        print(f"[说明]: {attempt.explanation}")
        print(f"[代码]:\n{attempt.code}")

        # ---------- 执行测试 (工具) ----------
        print("\n--- ③ 运行测试 (sandbox) ---")
        report = run_tests(attempt.code, plan.test_cases)
        print(f"[结果]: {report.total - report.failed}/{report.total} 通过")

        if report.passed:
            print("  ✓ 全部测试通过!")
            break

        print(f"  ✗ 有 {report.failed} 个失败:\n{report.details}")
        if round_no == max_fixes + 1:
            print("\n[提示] 已达最大修复轮数, 输出当前最佳版本。")

    return attempt.code if attempt else "# (未能生成代码)"


def demo():
    """演示: 给一个有边界情况的需求, 看 Agent 如何规划-编码-自测-修复。"""
    print("=== 端到端项目 B: 代码助手 ===\n")
    print("流水线: 规划 → 编码 → 执行测试 → 反思修复循环\n")

    requirement = (
        "实现一个函数, 判断给定的整数是否为素数 (prime)。"
        "注意处理小于 2 的输入。"
    )
    final_code = run_code_agent(requirement, max_fixes=3)

    print_separator("最终代码")
    print(final_code)


if __name__ == "__main__":
    demo()

    print_separator("项目 B 完成")
    print("这个项目综合运用了:")
    print("  • 阶段 1: 结构化输出 (计划 / 代码 / 测试报告都是强类型)")
    print("  • 阶段 2: 工具 (在子进程沙箱里真实运行代码)")
    print("  • 阶段 3: Plan (先定测试用例) + Reflection (带报错自我修复)")
    print("\n核心洞察: 让反思循环拥有客观的收敛信号 (测试通过), 而非主观判断。")
    print("\n恭喜! 你已走完从 LLM 基础到端到端 Agent 应用的完整路径。")
