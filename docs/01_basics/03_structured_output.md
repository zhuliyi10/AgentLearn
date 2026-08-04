# 03 - 结构化输出 (JSON Mode / Pydantic)

## 学习目标

- 使用 `response_format` 强制 JSON 输出
- 用 Pydantic 模型定义输出结构并自动校验
- 理解结构化输出对 Agent 的重要性（工具调用、状态管理）

## 运行方式

```bash
python 01_basics/03_structured_output.py
```

---

## 核心概念

### 为什么需要结构化输出？

LLM 默认输出自由文本，但程序需要**可解析、可校验**的数据。结构化输出让 LLM 的回复从"人可读"升级为"机器可用"。

```
自由文本: "我推荐《Python Crash Course》，适合入门..."
     ↓ 无法可靠提取字段

结构化 JSON: {"title": "Python Crash Course", "author": "Eric Matthes", ...}
     ↓ 程序直接解析使用
```

### 两种实现方式对比

| 方式 | 原理 | 适用场景 |
|------|------|----------|
| JSON Mode (`json_object`) | 强制输出合法 JSON，结构由 prompt 引导 | 所有兼容 API（推荐） |
| Structured Outputs (`parse`) | SDK 自动生成 Schema 并严格约束输出 | 仅 OpenAI 原生模型 |

> ⚠️ 第三方 API（智谱、DeepSeek、Moonshot 等）通常不支持 `beta.chat.completions.parse`，应使用 JSON Mode + Pydantic 手动校验。

### Pydantic 在其中的角色

```
┌──────────────┐         ┌──────────────┐         ┌──────────────────┐
│ Pydantic 模型 │ ──生成──► │  JSON Schema │ ──嵌入──► │  System Prompt   │
│ (定义结构)    │         │  (描述约束)   │         │  (引导模型输出)   │
└──────────────┘         └──────────────┘         └──────────────────┘
       ▲                                                    │
       │                   ┌──────────────┐                 │
       └───── 校验 ────────│  模型输出 JSON │ ◄───────────────┘
                           └──────────────┘
```

Pydantic 既是"合同模板"（定义期望结构），又是"质检员"（校验输出合规性）。

---

## 四个示例详解

### 示例 1：JSON Mode 基础

最简单的结构化输出 — 只保证输出是合法 JSON：

```python
response = client().chat.completions.create(
    model=get_model(),
    messages=[
        {"role": "system", "content": "你是一个书籍推荐助手。请以 JSON 格式回答。"},
        {"role": "user", "content": "推荐一本学习 Python 的书，包含 title, author, reason 字段"},
    ],
    response_format={"type": "json_object"},  # 关键参数
)

result = response.choices[0].message.content
data = json.loads(result)  # 安全解析，不会报错
```

**要点：**
- `response_format={"type": "json_object"}` 保证输出一定是合法 JSON
- 但**不保证**字段名和类型 — 结构由 prompt 引导
- system prompt 中必须提到"JSON"，否则部分 API 会报错

### 示例 2：Pydantic 结构化输出（推荐方式）

用 Pydantic 模型实现**类型安全**的结构化输出：

```python
# 第一步：定义期望的输出结构
class BookRecommendation(BaseModel):
    title: str = Field(description="书籍标题")
    author: str = Field(description="作者")
    reason: str = Field(description="推荐理由，一句话")
    difficulty: str = Field(description="难度: 入门/进阶/高级")
    rating: float = Field(description="推荐评分 1-10", ge=1, le=10)

# 第二步：将 JSON Schema 嵌入 prompt
schema_str = json.dumps(BookRecommendation.model_json_schema(), ensure_ascii=False, indent=2)

response = client().chat.completions.create(
    model=get_model(),
    messages=[
        {"role": "system", "content": (
            "你是一个书籍推荐专家。请严格按照以下 JSON Schema 输出，只输出 JSON。\n"
            f"JSON Schema:\n{schema_str}"
        )},
        {"role": "user", "content": "推荐一本学习 AI Agent 开发的书"},
    ],
    response_format={"type": "json_object"},
)

# 第三步：Pydantic 校验并解析为 Python 对象
book = BookRecommendation.model_validate_json(response.choices[0].message.content)
print(book.title)   # 直接属性访问，IDE 有自动补全
print(book.rating)  # float 类型，已校验范围 [1, 10]
```

**要点：**
- `Field(description=...)` 会写入 JSON Schema，帮助模型理解每个字段的含义
- `ge=1, le=10` 等约束会在 Pydantic 校验时生效（模型输出 11 分会报错）
- 得到的是 Python 对象，而非 dict — 有类型提示、属性访问、IDE 补全

**OpenAI 原生方式（仅 GPT-4o 等支持）：**

```python
# 如果直接使用 OpenAI 官方模型，可以更简洁：
response = client().beta.chat.completions.parse(
    model="gpt-4o",
    messages=[...],
    response_format=BookRecommendation,  # 直接传入模型
)
book = response.choices[0].message.parsed  # 自动解析
```

### 示例 3：复杂结构化输出

处理包含列表字段的复杂结构：

```python
class CodeAnalysis(BaseModel):
    language: str = Field(description="编程语言")
    functionality: str = Field(description="代码功能描述")
    issues: list[str] = Field(description="发现的问题列表")
    suggestions: list[str] = Field(description="改进建议列表")
    complexity: str = Field(description="时间复杂度")
```

**要点：**
- `list[str]` 类型在 JSON Schema 中会生成 `{"type": "array", "items": {"type": "string"}}`
- 复杂结构更需要 Schema 引导，否则模型容易遗漏字段或格式不一致
- 校验失败时 Pydantic 会抛出详细的 `ValidationError`，便于调试

### 示例 4：结构化输出与 Agent 的关系

结构化输出是 Agent 系统的基石：

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 系统                             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  工具调用 ──► 函数名 + 参数        → 结构化 JSON         │
│  状态管理 ──► 规划 / 记忆 / 反思   → 结构化存储          │
│  多Agent通信 ► 任务分配 / 结果汇总  → 统一数据格式        │
│  流程控制 ──► 完成? 重试? 升级?    → 结构化标志位         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

没有结构化输出，Agent 就无法可靠地：
- 解析 LLM 的决策（"它到底想调用哪个工具？"）
- 执行正确的动作（"参数是什么类型？"）
- 维护一致的状态（"上次执行到哪一步了？"）

---

## 关键 API 速查

```python
# JSON Mode（通用）
response_format={"type": "json_object"}

# Pydantic → JSON Schema
BookRecommendation.model_json_schema()

# JSON 字符串 → Pydantic 对象（自动校验）
book = BookRecommendation.model_validate_json(json_str)

# dict → Pydantic 对象
book = BookRecommendation.model_validate({"title": "...", ...})

# Pydantic 对象 → dict
book.model_dump()

# Pydantic 对象 → JSON 字符串
book.model_dump_json()
```

---

## 常见问题

**Q: `json_object` 模式和 Structured Outputs 有什么区别？**
A: `json_object` 只保证输出是合法 JSON，不约束具体结构；Structured Outputs（`parse` 方法）通过 JSON Schema 严格约束每个字段的名称、类型和必填性。后者仅 OpenAI 原生模型支持。

**Q: 模型输出的 JSON 字段不符合预期怎么办？**
A: 三层防御：① 在 prompt 中嵌入完整 JSON Schema；② 使用 `response_format={"type": "json_object"}` 保证合法 JSON；③ 用 Pydantic `model_validate_json` 校验，失败时捕获异常并重试。

**Q: 为什么 system prompt 中必须提到 "JSON"？**
A: 这是 OpenAI API 的硬性要求 — 开启 `json_object` 模式时，messages 中必须包含"JSON"相关提示，否则会返回错误。第三方 API 通常也有类似约束。

**Q: Pydantic 的 `Field(description=...)` 有什么用？**
A: description 会被写入 JSON Schema，模型能看到每个字段的说明，从而更准确地填充内容。它同时充当了"给模型的提示"和"给开发者的文档"双重角色。

**Q: 校验失败如何处理？**
A: 捕获 `pydantic.ValidationError`，常见策略：自动重试（降低 temperature）、截取 JSON 片段修复、记录日志后降级为自由文本。

---

## 下一步

→ 进入 `02_tool_calling/` 模块 — 学习工具调用（Agent 的核心机制），结构化输出将直接驱动函数调用。
