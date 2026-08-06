"""
03 - 协作式架构 (Collaborative Multi-Agent)

学习目标:
- 理解"去中心化"协作: 没有主管, Agent 之间平等协作
- 掌握共享上下文(黑板/blackboard)作为协作媒介的思想
- 学会用"轮流发言"(round-robin)的方式推进多方讨论
- 理解协作式与 Supervisor 式的本质区别: 谁来决定下一步

核心思想:
    Supervisor 式: 有一个主管居中调度, 工人之间不直接对话 (星型)
    协作式:        没有主管, 每个 Agent 都能看到共享上下文, 平等地贡献 (网状)

    协作的媒介是"共享黑板"(shared blackboard):
      所有 Agent 读同一块黑板, 也把自己的发言写回黑板。
      每个 Agent 都能承接、呼应、补充别人的观点。

    典型场景: 头脑风暴、圆桌讨论 —— 结论从多方交流中"涌现", 而非被指派。

运行方式:
    python 06_multi_agent/03_collaborative.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 参与协作的 Agent (平等的团队成员, 没有主管)
# ============================================================
# 每个成员有不同的专业视角。它们不听命于谁, 只是从各自角度贡献想法。

AGENTS = [
    {
        "name": "产品经理",
        "system": (
            "你是产品经理, 关注用户需求、使用场景和产品价值。"
            "在讨论中, 你从'用户到底要什么'的角度贡献观点, 简明扼要。"
        ),
    },
    {
        "name": "工程师",
        "system": (
            "你是软件工程师, 关注技术可行性、实现成本和潜在风险。"
            "在讨论中, 你从'能不能做、怎么做'的角度贡献观点, 简明扼要。"
        ),
    },
    {
        "name": "设计师",
        "system": (
            "你是设计师, 关注用户体验、交互流程和视觉表达。"
            "在讨论中, 你从'用起来是否顺畅、好懂'的角度贡献观点, 简明扼要。"
        ),
    },
]


# ============================================================
# 共享黑板 (Blackboard): 协作的核心媒介
# ============================================================

class Blackboard:
    """
    共享黑板: 所有 Agent 读写的同一块公共记忆。

    这是协作式架构的关键 —— 没有主管传话, Agent 靠共读黑板来"看见"彼此。
    """

    def __init__(self, topic: str):
        self.topic = topic
        self.entries: list[dict] = []  # 每条 = {"speaker": 谁, "content": 说了什么}

    def write(self, speaker: str, content: str) -> None:
        self.entries.append({"speaker": speaker, "content": content})

    def transcript(self) -> str:
        """把黑板上的全部发言渲染成 Agent 可读的讨论记录。"""
        if not self.entries:
            return "(讨论刚开始, 还没有人发言)"
        return "\n\n".join(f"【{e['speaker']}】: {e['content']}" for e in self.entries)


def speak(agent: dict, board: Blackboard) -> str:
    """
    让一个 Agent 基于当前黑板发言。

    Agent 看到的是: 讨论主题 + 到目前为止的完整发言记录。
    要求它承接前面的讨论, 而不是自说自话 —— 这是"协作"的关键。
    """
    system = (
        f"{agent['system']}\n\n"
        "你正在参加一场多人圆桌讨论。请先简要回应/呼应前面同事的观点, "
        "再补充你自己的看法。不要重复别人已经说过的内容, 控制在 3 句话以内。"
    )
    user = (
        f"讨论主题: {board.topic}\n\n"
        f"目前的讨论记录:\n{board.transcript()}\n\n"
        f"现在轮到你({agent['name']})发言。"
    )
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.8,  # 协作/头脑风暴需要一些发散性
    )
    return response.choices[0].message.content


def summarize(board: Blackboard) -> str:
    """讨论结束后, 由一个中立的整合者归纳共识与结论。"""
    system = (
        "你是一名中立的会议记录员。请阅读整场讨论, 归纳出:\n"
        "1) 达成的共识  2) 存在的分歧  3) 综合各方的最终建议。用要点呈现。"
    )
    user = f"讨论主题: {board.topic}\n\n完整讨论记录:\n{board.transcript()}"
    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


# ============================================================
# 协作主循环 (轮流发言 / round-robin)
# ============================================================

def collaborative_session(topic: str, rounds: int = 2) -> str:
    """
    协作式多 Agent 讨论。

    循环: 进行若干轮, 每一轮让每个 Agent 依次基于共享黑板发言。
    没有主管决定谁说话 —— 用最简单的轮流(round-robin)机制推进。
    """
    print(f"\n[讨论主题]: {topic}")
    board = Blackboard(topic)

    for r in range(rounds):
        print(f"\n{'='*55}")
        print(f"  第 {r + 1} 轮讨论")
        print(f"{'='*55}")

        for agent in AGENTS:
            content = speak(agent, board)
            board.write(agent["name"], content)
            print(f"\n【{agent['name']}】: {content}")

    print(f"\n{'='*55}")
    print("  归纳总结")
    print(f"{'='*55}")
    conclusion = summarize(board)
    print(f"\n{conclusion}")
    return conclusion


# ============================================================
# 演示
# ============================================================

def demo_collaborative():
    """演示: 三个不同角色平等协作, 讨论一个开放性问题"""
    print_separator("协作式架构演示")

    topic = "我们要为一款'学习类 App'设计一个帮助用户坚持每日学习的功能, 该怎么做?"
    collaborative_session(topic, rounds=2)

    print(f"\n{'='*55}")
    print("协作式架构要点:")
    print("  1. 去中心化 —— 没有主管, Agent 地位平等")
    print("  2. 共享黑板是协作媒介, 大家读写同一块记忆")
    print("  3. 发言要'承接他人', 结论从交流中涌现")
    print("  4. 适合开放性、需要多视角碰撞的问题")


if __name__ == "__main__":
    print("=== 03 协作式架构 ===\n")
    print("架构: 多个平等 Agent + 共享黑板 (去中心化, 网状)")
    print("适用: 头脑风暴、圆桌讨论等开放性问题\n")

    demo_collaborative()

    print_separator("完成")
    print("下一步: 04_debate.py - 辩论式多 Agent 架构")
