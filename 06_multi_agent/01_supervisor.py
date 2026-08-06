"""
01 - Supervisor 模式 (主管-工人架构)

学习目标:
- 理解多 Agent 系统中最经典的架构: Supervisor (主管) + Workers (工人)
- 掌握"主管路由 → 工人执行 → 结果汇总"的核心循环
- 学会用结构化输出让 Supervisor 做出可靠的调度决策
- 理解职责分工如何让每个 Agent 更专注、更可靠

核心思想:
    单 Agent:   一个 LLM 包揽所有工作 (提示词臃肿, 容易顾此失彼)
    Supervisor: 一个"主管"负责决策把任务分给谁, 多个"专家工人"各司其职

    主管不做具体活, 只做两件事:
      1. 看当前进展, 决定下一步交给哪个工人 (路由)
      2. 判断任务是否已经完成 (终止)

运行方式:
    python 06_multi_agent/01_supervisor.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# Worker (工人) 定义
# ============================================================
# 每个 Worker 是一个"专家 Agent", 由一个专属的 system prompt 定义其人格与职责。
# Worker 只需要专注做好自己那一件事, 不需要关心全局调度。

WORKERS = {
    "researcher": {
        "name": "研究员",
        "description": "负责收集资料、罗列事实与要点, 不做润色。",
        "system": (
            "你是一名严谨的研究员。收到主题后, 用简洁的要点(bullet)列出"
            "关键事实、数据和背景信息。只提供素材, 不写成文章。"
        ),
    },
    "writer": {
        "name": "写手",
        "description": "负责把素材整理成通顺、有条理的文字。",
        "system": (
            "你是一名专业写手。基于已有素材, 写出结构清晰、通顺易读的成稿。"
            "不要编造素材里没有的事实。"
        ),
    },
    "critic": {
        "name": "评审",
        "description": "负责挑刺、指出不足并给出改进建议。",
        "system": (
            "你是一名严格的评审。阅读稿件后, 用要点指出其中的问题"
            "(逻辑、准确性、表达), 并给出可执行的改进建议。"
        ),
    },
}


def run_worker(worker_key: str, task: str, shared_context: str) -> str:
    """
    运行单个 Worker。

    Worker 能看到:
      - 自己的 system prompt (决定它的专长)
      - 主管交代的当前子任务 (task)
      - 共享上下文 (前面工人产出的成果), 便于承接工作
    """
    worker = WORKERS[worker_key]
    user_content = f"【当前子任务】\n{task}\n\n【已有进展/共享上下文】\n{shared_context or '(暂无)'}"

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": worker["system"]},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content


# ============================================================
# Supervisor (主管) 定义
# ============================================================
# 主管不生产内容, 只做调度决策。它的输出被约束为结构化 JSON, 方便程序解析。

SUPERVISOR_SYSTEM = """你是一个多 Agent 团队的主管(Supervisor)。
你手下有几名专家工人, 你的职责是根据当前进展, 决定下一步该交给谁, 或宣布任务完成。

## 可调度的工人
- researcher (研究员): 收集资料、罗列事实要点
- writer (写手): 把素材整理成通顺的成稿
- critic (评审): 挑出稿件的问题并给改进建议

## 决策原则
1. 一般流程: 先 researcher 收集素材 → 再 writer 成稿 → 再 critic 评审 → writer 按评审意见改稿。
2. 当稿件已经过评审且质量达标时, 输出 FINISH 结束。
3. 不要无限循环, 评审-改稿最多来回一轮即可。

## 输出格式 (严格的 JSON, 不要多余文字)
{
  "reasoning": "你为什么这样决策 (一句话)",
  "next": "researcher | writer | critic | FINISH",
  "instruction": "交给该工人的具体指令 (若 next=FINISH 则留空)"
}
"""


def supervisor_decide(goal: str, history: list[dict]) -> dict:
    """
    主管根据总目标和历史进展, 决定下一步。

    返回: {"reasoning": ..., "next": ..., "instruction": ...}
    """
    # 把历史进展整理成主管能读的摘要
    progress = "\n\n".join(
        f"[{WORKERS[h['worker']]['name']} 产出]:\n{h['output']}"
        for h in history
    ) or "(尚未开始)"

    user_content = f"【总目标】\n{goal}\n\n【已完成的工作】\n{progress}\n\n请决定下一步。"

    response = client().chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": SUPERVISOR_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0,  # 调度决策需要确定性
    )
    return json.loads(response.choices[0].message.content)


# ============================================================
# Supervisor 主循环
# ============================================================

def supervisor_agent(goal: str, max_steps: int = 8) -> str:
    """
    Supervisor 多 Agent 主循环。

    循环:
        主管决策(next) → 若 FINISH 则结束 → 否则运行对应 Worker
        → 把产出写入共享历史 → 回到主管决策
    """
    print(f"\n[总目标]: {goal}")

    history: list[dict] = []  # 共享历史: 每个工人的产出都记录在这里

    for step in range(max_steps):
        print(f"\n{'='*55}")
        print(f"  第 {step + 1} 步 — 主管决策")
        print(f"{'='*55}")

        decision = supervisor_decide(goal, history)
        print(f"[主管思考]: {decision.get('reasoning', '')}")
        print(f"[主管决策]: next = {decision['next']}")

        if decision["next"] == "FINISH":
            print("\n[主管]: 任务完成, 结束调度。")
            break

        worker_key = decision["next"]
        if worker_key not in WORKERS:
            print(f"[警告]: 未知工人 '{worker_key}', 跳过。")
            continue

        instruction = decision.get("instruction", "")
        print(f"[分派给]: {WORKERS[worker_key]['name']}")
        print(f"[指令]: {instruction}")

        # 把已有历史作为共享上下文喂给工人
        shared_context = "\n\n".join(
            f"[{WORKERS[h['worker']]['name']}]:\n{h['output']}" for h in history
        )
        output = run_worker(worker_key, instruction, shared_context)
        print(f"\n[{WORKERS[worker_key]['name']} 产出]:\n{output}")

        history.append({"worker": worker_key, "output": output})

    # 最终成果: 取最后一次 writer 的产出 (如果有), 否则取最后一条
    final = next(
        (h["output"] for h in reversed(history) if h["worker"] == "writer"),
        history[-1]["output"] if history else "(无产出)",
    )
    return final


# ============================================================
# 演示
# ============================================================

def demo_supervisor():
    """演示: 主管调度一个研究-写作-评审团队完成短文"""
    print_separator("Supervisor 模式演示")

    goal = "写一段 200 字左右的短文, 介绍'为什么多 Agent 协作能超越单个 Agent'。"
    final = supervisor_agent(goal, max_steps=8)

    print_separator("最终成果")
    print(final)

    print(f"\n{'='*55}")
    print("Supervisor 模式要点:")
    print("  1. 主管只做调度, 不做具体工作 (关注点分离)")
    print("  2. 工人各是领域专家, 提示词精简、职责单一")
    print("  3. 用结构化输出(JSON)让路由决策可靠可解析")
    print("  4. 共享历史让工人能承接彼此的成果")


if __name__ == "__main__":
    print("=== 01 Supervisor 模式 ===\n")
    print("架构: 1 个主管(调度) + N 个专家工人(执行)")
    print("适用: 任务可拆分为清晰的专业分工时\n")

    demo_supervisor()

    print_separator("完成")
    print("下一步: 02_hierarchical.py - 层级式多 Agent 架构")
