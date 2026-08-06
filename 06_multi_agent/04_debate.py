"""
04 - 辩论式架构 (Multi-Agent Debate)

学习目标:
- 理解"对抗式"协作: 让 Agent 各执一词, 通过交锋逼出更优答案
- 掌握正方/反方/裁判(Proponent / Opponent / Judge)三角色架构
- 理解辩论如何对冲单个 LLM 的偏见与"一本正经的胡说八道"
- 对比辩论式与协作式: 前者求真(对抗), 后者共创(合作)

核心思想:
    协作式: Agent 互相补充、达成共识 (求同)
    辩论式: Agent 互相反驳、挑战论点 (求异, 再由裁判裁决)

    为什么有用?
      单个 LLM 容易对自己的第一想法过度自信。
      让另一个 Agent 专职"抬杠", 能暴露论证的漏洞和被忽略的反例。
      多轮交锋后, 由中立裁判权衡双方, 得出更经得起推敲的结论。

    这类似人类的"红队/蓝队"和法庭辩论 —— 真理越辩越明。

运行方式:
    python 06_multi_agent/04_debate.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 辩论的三个角色
# ============================================================

PROPONENT_SYSTEM = """你是辩论中的【正方】, 支持给定命题。
你的任务: 提出有力的论据支持命题, 并针对反方的质疑进行有理有据的反驳。
要求: 论据具体、有逻辑, 承认合理之处但坚持立场。每次发言控制在 4 句话以内。"""

OPPONENT_SYSTEM = """你是辩论中的【反方】, 反对给定命题。
你的任务: 找出命题的漏洞、反例和风险, 针对正方的论据进行犀利反驳。
要求: 质疑要具体、切中要害, 不要为反对而反对。每次发言控制在 4 句话以内。"""

JUDGE_SYSTEM = """你是辩论的【裁判】, 保持中立。
你的任务: 通读双方全部交锋, 客观权衡双方论据的强弱, 给出最终裁决。
要求: 不预设立场, 基于论证质量而非个人偏好。

只输出 JSON:
{
  "proponent_strong_points": "正方最有力的点 (一句话)",
  "opponent_strong_points": "反方最有力的点 (一句话)",
  "winner": "正方 | 反方 | 平局",
  "verdict": "综合双方后的平衡结论 (2-3 句话)"
}"""


def argue(role_system: str, motion: str, transcript: str, role_name: str) -> str:
    """让正方或反方基于当前辩论记录发表一轮论述。"""
    user = (
        f"辩论命题: {motion}\n\n"
        f"目前的辩论记录:\n{transcript or '(辩论刚开始)'}\n\n"
        f"现在轮到你({role_name})发言。"
    )
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": role_system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content


def judge(motion: str, transcript: str) -> dict:
    """裁判通读全部交锋, 给出结构化裁决。"""
    user = f"辩论命题: {motion}\n\n完整辩论记录:\n{transcript}"
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,  # 裁决需要稳定、可复现
    )
    return json.loads(response.choices[0].message.content)


# ============================================================
# 辩论主循环
# ============================================================

def debate(motion: str, rounds: int = 2) -> dict:
    """
    多 Agent 辩论。

    循环: 进行若干轮, 每轮正方先发言、反方再反驳; 双方都能看到完整记录。
    最后由裁判权衡双方, 给出裁决。
    """
    print(f"\n[辩论命题]: {motion}")

    turns: list[str] = []  # 完整辩论记录

    def transcript() -> str:
        return "\n\n".join(turns)

    for r in range(rounds):
        print(f"\n{'='*55}")
        print(f"  第 {r + 1} 轮交锋")
        print(f"{'='*55}")

        # 正方发言
        pro = argue(PROPONENT_SYSTEM, motion, transcript(), "正方")
        turns.append(f"【正方 第{r+1}轮】: {pro}")
        print(f"\n【正方】: {pro}")

        # 反方反驳 (能看到正方刚才的发言)
        opp = argue(OPPONENT_SYSTEM, motion, transcript(), "反方")
        turns.append(f"【反方 第{r+1}轮】: {opp}")
        print(f"\n【反方】: {opp}")

    # 裁判裁决
    print(f"\n{'='*55}")
    print("  裁判裁决")
    print(f"{'='*55}")
    verdict = judge(motion, transcript())

    print(f"\n[正方最强点]: {verdict.get('proponent_strong_points', '')}")
    print(f"[反方最强点]: {verdict.get('opponent_strong_points', '')}")
    print(f"[胜方]: {verdict.get('winner', '')}")
    print(f"\n[最终裁决]:\n{verdict.get('verdict', '')}")

    return verdict


# ============================================================
# 演示
# ============================================================

def demo_debate():
    """演示: 就一个有争议的命题展开正反辩论并由裁判裁决"""
    print_separator("辩论式架构演示")

    motion = "初创公司在早期就应该大规模引入 AI Agent 替代人工客服。"
    debate(motion, rounds=2)

    print(f"\n{'='*55}")
    print("辩论式架构要点:")
    print("  1. 对抗式协作 —— 专门安排一方'抬杠', 逼出漏洞")
    print("  2. 正方/反方/裁判三角色, 职责对立且互补")
    print("  3. 对冲单个 LLM 的过度自信与偏见")
    print("  4. 适合有争议、需要审慎权衡的决策问题")


if __name__ == "__main__":
    print("=== 04 辩论式架构 ===\n")
    print("架构: 正方 vs 反方 (对抗) + 裁判 (裁决)")
    print("适用: 争议性决策、需要多视角审视的判断题\n")

    demo_debate()

    print_separator("阶段 6 完成!")
    print("你已掌握四种多 Agent 协作架构:")
    print("  1. Supervisor: 主管调度 + 专家工人 (星型)")
    print("  2. Hierarchical: 多层递归的团队组织 (树型)")
    print("  3. Collaborative: 共享黑板的平等协作 (网状)")
    print("  4. Debate: 正反对抗 + 裁判裁决 (对抗)")
    print("\n下一阶段: 07_project/ - 综合运用所有知识构建端到端应用")
