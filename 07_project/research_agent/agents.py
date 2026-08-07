"""
agents.py - 研究助手的各个专职 Agent (综合阶段 1/2/3/6)

整条流水线由四类 Agent 接力完成, 每个都是一个"专家", 只做一件事:

    Planner    规划器   —— 把主题拆成子问题        (阶段 3 Plan)
    Researcher 研究员   —— 带搜索工具调研一个子问题  (阶段 2 tool loop)
    Synthesizer 综合器  —— 把发现整合成结构化报告    (阶段 1 结构化输出)
    Critic     评审     —— 给报告挑刺驱动改进        (阶段 3 Reflection)

设计原则和阶段 6 的 Supervisor 一致: 职责单一的 Agent 比全能 Agent 更可靠。
Agent 之间通过 schemas.py 里定义的强类型对象传递数据 (而非自由文本)。
"""

import json
from typing import Type, TypeVar

from pydantic import BaseModel

from utils.llm import client, get_model
from utils.helpers import json_skeleton
from .schemas import ResearchPlan, Finding, Critique, Report
from .tools import SEARCH_TOOL, execute_tool

T = TypeVar("T", bound=BaseModel)


# ============================================================
# 通用工具: 让 LLM 输出并校验为指定的 Pydantic 模型
# ============================================================

def _structured(system: str, user: str, model_cls: Type[T], temperature: float = 0.3) -> T:
    """
    调用 LLM 并把结果解析成指定的 Pydantic 模型。

    做法 (阶段 1 结构化输出):
      1. 用 json_skeleton 生成"填空模板"拼进 system prompt, 引导 LLM 输出实例
         (直接给 JSON Schema 会被有些模型原样抄回, 填空模板更可靠)
      2. 用 response_format=json_object 强制 JSON
      3. 用 pydantic 校验, 校验失败会抛异常 (说明提示词需要改进)
    """
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
# 1. Planner —— 把主题拆成子问题 (阶段 3 Plan)
# ============================================================

def make_plan(topic: str) -> ResearchPlan:
    """规划器: 面对一个宽泛主题, 先拆解成可独立检索的子问题。"""
    system = (
        "你是一名研究规划专家。用户会给你一个研究主题, "
        "你要把它拆解成 3-5 个彼此独立、合起来能全面覆盖该主题的子问题。"
        "子问题要具体、可检索, 避免宽泛重复。"
    )
    return _structured(system, f"研究主题: {topic}", ResearchPlan, temperature=0.4)


# ============================================================
# 2. Researcher —— 带搜索工具调研一个子问题 (阶段 2 tool loop)
# ============================================================

def research_one(sub_question: str, max_iterations: int = 4) -> Finding:
    """
    研究员: 针对单个子问题, 运行一个"带搜索工具的 Agent 循环"收集资料,
    最后把资料整理成一条 Finding。

    这里复用了阶段 2 的 tool loop: LLM 自主决定搜什么、搜几次,
    直到它认为资料够了, 再输出总结。
    """
    system = (
        "你是一名严谨的研究员。你的任务是调研给定的子问题。"
        "请使用 web_search 工具检索资料 (可多次搜索不同关键词), "
        "然后基于检索到的内容给出客观、有依据的总结。不要编造事实。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"请调研这个子问题: {sub_question}"},
    ]

    collected_sources: list[str] = []

    # --- tool loop: 决策 → 搜索 → 观察 → 继续 ---
    for _ in range(max_iterations):
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=[SEARCH_TOOL],
            temperature=0.3,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            break  # LLM 认为资料够了, 停止搜索

        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            result = execute_tool(tc.function.name, args)
            # 顺手记录来源, 供报告引用
            for item in json.loads(result).get("results", []):
                if item.get("title"):
                    collected_sources.append(item["title"])
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # --- 把整个搜索过程整理成结构化 Finding ---
    transcript = "\n".join(
        m["content"] if isinstance(m, dict) else (m.content or "")
        for m in messages
        if (isinstance(m, dict) and m.get("role") == "tool")
    )
    finding = _structured(
        "你是研究员。请把下面的检索资料, 针对子问题整理成一条客观总结。",
        f"子问题: {sub_question}\n\n检索到的资料:\n{transcript or '(无有效资料)'}",
        Finding,
    )
    # 用真实抓取到的来源覆盖 LLM 可能编造的来源
    if collected_sources:
        finding.sources = list(dict.fromkeys(collected_sources))[:5]
    return finding


# ============================================================
# 3. Synthesizer —— 把发现整合成结构化报告 (阶段 1 结构化输出)
# ============================================================

def synthesize(topic: str, findings: list[Finding], critique: Critique | None = None) -> Report:
    """
    综合器: 把所有子问题的调研发现, 整合成一份结构清晰的报告。

    如果传入了 critique (评审意见), 就在原基础上按意见改进 —— 这正是
    Reflection 循环里的"改稿"环节。
    """
    findings_text = "\n\n".join(
        f"【子问题】{f.sub_question}\n{f.summary}" for f in findings
    )
    all_sources = list(dict.fromkeys(s for f in findings for s in f.sources))

    user = (
        f"研究主题: {topic}\n\n各子问题的调研发现:\n{findings_text}\n\n"
        f"可用来源: {all_sources}"
    )
    if critique:
        user += (
            f"\n\n上一版报告收到如下评审意见, 请针对性改进:\n"
            f"问题: {critique.issues}\n建议: {critique.suggestions}"
        )

    system = (
        "你是一名资深分析师。请把零散的调研发现整合成一份逻辑连贯、"
        "有洞察的研究报告。要有摘要、分章节的正文, 并在末尾列出参考来源。"
        "只使用发现中提供的信息, 不要编造。"
    )
    return _structured(system, user, Report, temperature=0.5)


# ============================================================
# 4. Critic —— 给报告挑刺 (阶段 3 Reflection)
# ============================================================

def critique(report: Report) -> Critique:
    """评审: 站在挑剔读者的角度给报告打分并指出问题, 驱动下一轮改进。"""
    system = (
        "你是一名严格的审稿人。请评估这份研究报告的质量 (逻辑性、完整性、"
        "准确性、表达)。给出 1-10 分, 列出具体问题和可执行的改进建议。"
        "只有当报告确实优秀 (>=8 分) 时才标记 passed=true。"
    )
    return _structured(system, report.to_markdown(), Critique, temperature=0.2)
