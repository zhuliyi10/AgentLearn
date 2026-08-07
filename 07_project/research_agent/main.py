"""
main.py - 研究助手主流程 (端到端项目 A)

这是阶段 7 的第一个综合项目。它把前面所有阶段的能力串成一条流水线:

    用户主题
       │
       ▼  ① 规划 (Planner)              —— 阶段 3 Plan
    拆成 N 个子问题
       │
       ▼  ② 并行调研 (N × Researcher)    —— 阶段 2 tool loop + 阶段 6 多 Agent
    N 条 Finding
       │
       ▼  ③ 综合 (Synthesizer)          —— 阶段 1 结构化输出
    初版报告
       │
       ▼  ④ 反思循环 (Critic ⇄ 改稿)     —— 阶段 3 Reflection
    达标报告
       │
       ▼  输出 Markdown 报告

运行方式:
    python 07_project/research_agent/main.py
"""

import sys
from pathlib import Path

# 让脚本能直接运行: 需要两个路径
#   项目根目录 (AgentLearn/)   → 导入 utils
#   阶段目录  (07_project/)    → 把 research_agent 当作包导入
_ROOT = Path(__file__).resolve().parent.parent.parent
_STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_STAGE))

from utils.helpers import print_separator
from research_agent.agents import make_plan, research_one, synthesize, critique


def run_research(topic: str, max_reflections: int = 2) -> str:
    """
    运行完整的研究流水线, 返回最终报告的 Markdown 文本。

    参数:
        topic:            研究主题
        max_reflections:  反思-改进的最大轮数 (安全阀, 防止无限打磨)
    """
    # ---------- ① 规划 ----------
    print_separator("① 规划 (Planner)")
    plan = make_plan(topic)
    print(f"[主题]: {plan.topic}")
    print(f"[思路]: {plan.rationale}")
    print("[拆解出的子问题]:")
    for i, q in enumerate(plan.sub_questions, 1):
        print(f"  {i}. {q}")

    # ---------- ② 逐个调研 (每个子问题一个研究员) ----------
    print_separator("② 调研 (Researchers)")
    findings = []
    for i, q in enumerate(plan.sub_questions, 1):
        print(f"\n[研究员 {i}] 正在调研: {q}")
        finding = research_one(q)
        print(f"  → 总结: {finding.summary[:120]}...")
        print(f"  → 来源: {finding.sources}")
        findings.append(finding)

    # ---------- ③ 综合成初版报告 ----------
    print_separator("③ 综合 (Synthesizer)")
    report = synthesize(topic, findings)
    print(f"[初版报告标题]: {report.title}")
    print(f"[章节数]: {len(report.sections)}")

    # ---------- ④ 反思-改进循环 ----------
    print_separator("④ 反思循环 (Critic ⇄ 改稿)")
    for round_no in range(1, max_reflections + 1):
        crit = critique(report)
        print(f"\n[第 {round_no} 轮评审] 得分 {crit.score}/10, 通过={crit.passed}")
        if crit.issues:
            print(f"  问题: {crit.issues}")

        if crit.passed:
            print("  ✓ 报告已达标, 结束打磨。")
            break

        print("  → 根据评审意见改稿中...")
        report = synthesize(topic, findings, critique=crit)
    else:
        print("\n[提示] 已达最大反思轮数, 输出当前最佳版本。")

    return report.to_markdown()


def demo():
    """演示: 研究一个具体主题, 打印最终报告。"""
    print("=== 端到端项目 A: 研究助手 ===\n")
    print("流水线: 规划 → 并行调研 → 综合 → 反思循环 → 结构化报告\n")

    topic = "大语言模型 Agent 的记忆机制有哪些常见实现方式?"
    final_markdown = run_research(topic, max_reflections=2)

    print_separator("最终研究报告")
    print(final_markdown)


if __name__ == "__main__":
    demo()

    print_separator("项目 A 完成")
    print("这个项目综合运用了:")
    print("  • 阶段 1: 结构化输出 (Pydantic 定义阶段间数据契约)")
    print("  • 阶段 2: tool loop (研究员自主搜索)")
    print("  • 阶段 3: Plan (先拆解) + Reflection (评审改稿)")
    print("  • 阶段 6: 多 Agent 分工 (规划/研究/综合/评审各司其职)")
    print("\n下一个项目: code_agent/ - 会写代码、会自测、会自我修复的代码助手")
