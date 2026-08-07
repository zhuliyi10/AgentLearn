"""
schemas.py - 研究助手的结构化数据模型 (阶段 1 结构化输出的实战应用)

为什么需要 Schema?
    一个端到端 Agent 由多个阶段串联 (规划 → 检索 → 综合 → 反思)。
    如果每个阶段之间用自由文本传递, 下游根本没法可靠解析。
    我们用 Pydantic 把"阶段之间的接口"定义成强类型的数据契约:
      - LLM 被 Schema 引导, 输出稳定的 JSON
      - 程序拿到的是校验过的 Python 对象, 而不是一坨字符串

这些模型就是各个 Agent 之间流动的"数据管道"。
"""

from pydantic import BaseModel, Field, field_validator


# ============================================================
# 阶段 1: 规划 (Planner 的产出)
# ============================================================

class ResearchPlan(BaseModel):
    """研究计划: 把一个宽泛的主题拆解成若干可独立检索的子问题。"""

    topic: str = Field(description="用户输入的原始研究主题")
    rationale: str = Field(description="为什么这样拆解 (一句话说明整体思路)")
    sub_questions: list[str] = Field(
        description="3-5 个彼此独立、合起来能覆盖主题的子问题"
    )


# ============================================================
# 阶段 2: 检索 (每个 Researcher 的产出)
# ============================================================

class Finding(BaseModel):
    """针对单个子问题的调研发现。"""

    sub_question: str = Field(description="本次调研针对的子问题")
    summary: str = Field(description="基于检索结果整理出的要点总结")
    sources: list[str] = Field(
        default_factory=list, description="参考来源 (标题或链接)"
    )

    @field_validator("sources", mode="before")
    @classmethod
    def _coerce_sources(cls, v):
        """
        防御式解析: LLM 有时会把来源写成 {"title": ..., "url": ...} 对象,
        而不是纯字符串。这里统一强制转成字符串, 避免整条流水线因格式抖动而崩溃。
        (端到端系统的一条重要经验: 对 LLM 的输出要宽进严出。)
        """
        if not isinstance(v, list):
            return v
        coerced = []
        for item in v:
            if isinstance(item, dict):
                coerced.append(str(item.get("title") or item.get("url") or item))
            else:
                coerced.append(str(item))
        return coerced


# ============================================================
# 阶段 4: 反思 (Critic 的产出)
# ============================================================

class Critique(BaseModel):
    """评审意见: 用于驱动报告的反思-改进循环。"""

    score: int = Field(description="报告质量总分 1-10")
    passed: bool = Field(description="是否已达到可交付标准 (score>=8 视为通过)")
    issues: list[str] = Field(
        default_factory=list, description="发现的具体问题"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="可执行的改进建议"
    )


# ============================================================
# 阶段 3/5: 报告 (Synthesizer 的最终产出)
# ============================================================

class ReportSection(BaseModel):
    """报告中的一个章节。"""

    heading: str = Field(description="章节标题")
    content: str = Field(description="章节正文")


class Report(BaseModel):
    """结构化研究报告 —— 整条流水线的最终交付物。"""

    title: str = Field(description="报告标题")
    summary: str = Field(description="一段话的核心摘要 (给忙碌的读者)")
    sections: list[ReportSection] = Field(description="正文章节")
    references: list[str] = Field(
        default_factory=list, description="全文引用的来源汇总"
    )

    def to_markdown(self) -> str:
        """把结构化报告渲染成 Markdown 文本, 方便阅读或保存。"""
        lines = [f"# {self.title}\n", f"> {self.summary}\n"]
        for sec in self.sections:
            lines.append(f"## {sec.heading}\n\n{sec.content}\n")
        if self.references:
            lines.append("## 参考来源\n")
            lines.extend(f"- {ref}" for ref in self.references)
        return "\n".join(lines)
