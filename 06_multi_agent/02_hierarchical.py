"""
02 - 层级式架构 (Hierarchical Multi-Agent)

学习目标:
- 理解 Supervisor 模式的递归扩展: 主管之下还有主管
- 掌握"逐级分解"的思想: 大任务 → 子任务 → 具体执行
- 学会用组合(而非继承)搭建多层团队结构
- 理解层级架构如何应对单层 Supervisor 扛不住的复杂任务

核心思想:
    单层 Supervisor: 1 个主管直接管 N 个工人 —— 工人一多, 主管的调度提示词就会爆炸
    层级式:          顶层主管管几个"团队主管", 每个团队主管再管自己的工人

    就像公司组织架构:
        CEO (顶层)
         ├── 研发经理 (中层主管) → 后端工程师 / 前端工程师 (工人)
         └── 市场经理 (中层主管) → 文案 / 设计 (工人)

    每一层只需理解"下一层能做什么", 无需了解最底层细节 —— 抽象与分治。

运行方式:
    python 06_multi_agent/02_hierarchical.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 通用组件: 一个可复用的"主管"和"工人"
# ============================================================
# 层级式的关键洞察: Supervisor 和 Worker 是可以递归组合的积木。
# 一个"中层主管"对上是工人(接受任务、交付成果), 对下是主管(调度自己的工人)。


def llm(system: str, user: str, temperature: float = 0.7, as_json: bool = False) -> str:
    """对 LLM 的一次薄封装, 供各层复用。"""
    kwargs = {
        "model": get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if as_json:
        kwargs["response_format"] = {"type": "json_object"}
    return client().chat.completions.create(**kwargs).choices[0].message.content


class Worker:
    """底层工人: 拿到具体任务, 直接产出结果。"""

    def __init__(self, name: str, system: str):
        self.name = name
        self.system = system

    def run(self, task: str, indent: int = 0) -> str:
        pad = "  " * indent
        print(f"{pad}└─ [{self.name}] 执行: {task}")
        output = llm(self.system, f"请完成以下任务:\n{task}", temperature=0.7)
        print(f"{pad}   [{self.name}] 产出: {output[:80].strip()}...")
        return output


class TeamLead:
    """
    中层主管(团队主管): 管理一组工人。

    - 对上: 像一个 Worker, 接受一个子任务并返回团队的整合成果
    - 对下: 像一个 Supervisor, 把子任务拆给自己的工人并汇总
    """

    def __init__(self, name: str, mission: str, workers: list[Worker]):
        self.name = name
        self.mission = mission  # 这个团队擅长什么
        self.workers = workers

    def _plan(self, task: str) -> list[dict]:
        """把交办的子任务, 拆解成分派给各工人的指令。"""
        roster = "\n".join(f"- {w.name}" for w in self.workers)
        system = (
            f"你是'{self.name}'团队的主管, 团队职责: {self.mission}。\n"
            f"你的工人有:\n{roster}\n\n"
            "请把上级交办的任务拆解成分派给各工人的具体指令。\n"
            "只输出 JSON: {\"assignments\": [{\"worker\": \"工人名\", \"instruction\": \"具体指令\"}]}"
        )
        raw = llm(system, f"上级交办的任务:\n{task}", temperature=0, as_json=True)
        return json.loads(raw).get("assignments", [])

    def _synthesize(self, task: str, results: list[str]) -> str:
        """把工人们的产出整合成本团队交付给上级的成果。"""
        joined = "\n\n".join(results)
        system = f"你是'{self.name}'团队的主管。请把工人们的产出整合成一份连贯的团队成果。"
        return llm(system, f"团队任务:\n{task}\n\n各工人产出:\n{joined}", temperature=0.5)

    def run(self, task: str, indent: int = 0) -> str:
        pad = "  " * indent
        print(f"{pad}├─ [{self.name} 团队] 接到任务: {task}")

        assignments = self._plan(task)
        results = []
        for a in assignments:
            worker = next((w for w in self.workers if w.name == a["worker"]), None)
            if worker is None:
                # 找不到指定工人时, 退化为交给第一个工人
                worker = self.workers[0]
            results.append(worker.run(a["instruction"], indent + 1))

        summary = self._synthesize(task, results)
        print(f"{pad}   [{self.name} 团队] 交付整合成果 ({len(results)} 份产出)")
        return summary


class TopManager:
    """顶层主管(CEO): 管理若干个团队主管, 逐级分解大目标。"""

    def __init__(self, teams: list[TeamLead]):
        self.teams = teams

    def _delegate(self, goal: str) -> list[dict]:
        """把总目标分解成交给各团队的子任务。"""
        roster = "\n".join(f"- {t.name}: {t.mission}" for t in self.teams)
        system = (
            "你是公司的顶层主管(CEO)。你手下有几个团队:\n"
            f"{roster}\n\n"
            "请把总目标分解成交给各团队的子任务(每个团队一个)。\n"
            "只输出 JSON: {\"tasks\": [{\"team\": \"团队名\", \"subtask\": \"子任务\"}]}"
        )
        raw = llm(system, f"总目标:\n{goal}", temperature=0, as_json=True)
        return json.loads(raw).get("tasks", [])

    def _final_report(self, goal: str, deliverables: list[str]) -> str:
        """整合各团队成果, 形成最终交付。"""
        joined = "\n\n".join(deliverables)
        system = "你是顶层主管。请把各团队的成果整合成一份面向最终目标的完整交付物。"
        return llm(system, f"总目标:\n{goal}\n\n各团队成果:\n{joined}", temperature=0.5)

    def run(self, goal: str) -> str:
        print(f"\n[CEO] 总目标: {goal}\n")
        print("[CEO] 逐级分解中...\n")

        tasks = self._delegate(goal)
        deliverables = []
        for t in tasks:
            team = next((tm for tm in self.teams if tm.name == t["team"]), None)
            if team is None:
                continue
            deliverables.append(team.run(t["subtask"], indent=0))
            print()

        return self._final_report(goal, deliverables)


# ============================================================
# 搭建一个两层团队并演示
# ============================================================

def build_company() -> TopManager:
    """组装一个"内容工作室": CEO → 2 个团队 → 每队 2 名工人。"""
    research_team = TeamLead(
        name="调研组",
        mission="收集事实、数据与背景资料",
        workers=[
            Worker("资料员", "你负责查找并罗列与主题相关的关键事实和数据, 用要点呈现。"),
            Worker("案例员", "你负责为主题找出具体、生动的实例或类比, 用要点呈现。"),
        ],
    )
    content_team = TeamLead(
        name="内容组",
        mission="把素材写成通顺、有吸引力的成稿",
        workers=[
            Worker("撰稿人", "你负责把给定素材组织成结构清晰、通顺的文章。"),
            Worker("标题党", "你负责为文章拟 3 个吸引人但不夸大的标题。"),
        ],
    )
    return TopManager(teams=[research_team, content_team])


def demo_hierarchical():
    """演示: 两层架构逐级分解并完成一篇科普短文"""
    print_separator("层级式架构演示")

    ceo = build_company()
    goal = "产出一篇面向初学者的科普短文, 主题: '什么是多 Agent 系统'。"
    final = ceo.run(goal)

    print_separator("最终交付物")
    print(final)

    print(f"\n{'='*55}")
    print("层级式架构要点:")
    print("  1. Supervisor/Worker 是可递归组合的积木")
    print("  2. 中层主管'对上是工人, 对下是主管'")
    print("  3. 每层只需了解下一层的能力 (抽象与分治)")
    print("  4. 适合单层主管管不过来的大型、多领域任务")


if __name__ == "__main__":
    print("=== 02 层级式架构 ===\n")
    print("架构: CEO → 团队主管 → 工人 (多层递归)")
    print("适用: 任务规模大、领域多, 单层调度扛不住时\n")

    demo_hierarchical()

    print_separator("完成")
    print("下一步: 03_collaborative.py - 协作式多 Agent 架构")
