# 01 - Chat Completion 基础调用

## 学习目标

- 理解 OpenAI Chat API 的基本结构
- 掌握 messages 中 system / user / assistant 三种角色
- 了解 temperature、max_tokens 等常用参数
- 体验流式输出 (streaming)

## 运行方式

```bash
python 01_basics/01_chat_completion.py
```

---

## 核心概念

### 1. Chat API 的基本结构

Chat Completion API 是大语言模型最基础的调用方式。你发送一组 **消息 (messages)**，模型返回一个 **回复 (completion)**。

```
请求 (Request)                    响应 (Response)
┌─────────────────────┐          ┌─────────────────────┐
│ model               │          │ choices[0].message  │
│ messages: [...]     │  ──────► │   .content          │
│ temperature         │          │ usage               │
│ max_tokens          │          │   .prompt_tokens    │
│ stream              │          │   .completion_tokens│
└─────────────────────┘          └─────────────────────┘
```

### 2. 三种消息角色

| 角色 | 作用 | 类比 |
|------|------|------|
| `system` | 设定 AI 的身份、行为准则、约束条件 | 给演员的"角色说明书" |
| `user` | 用户的输入/提问 | 观众的问题 |
| `assistant` | AI 的回复（也用于提供历史上下文） | 演员之前的回答 |

**关键点：** 模型本身是无状态的，每次调用都是独立的。要实现"记住上下文"，必须把完整对话历史作为 messages 传入。

### 3. 常用参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | str | 模型名称，如 `glm-4-flash`、`gpt-4o` |
| `messages` | list | 对话消息列表 |
| `temperature` | float | 控制随机性。0=确定性输出，1=最大随机性 |
| `max_tokens` | int | 回复的最大 token 数 |
| `stream` | bool | 是否启用流式输出 |

---

## 四个示例详解

### 示例 1：基础对话

最简单的单次问答：

```python
response = client().chat.completions.create(
    model=get_model(),
    messages=[
        {"role": "system", "content": "你是一个友好的编程助手，回答简洁明了。"},
        {"role": "user", "content": "用一句话解释什么是 Agent？"},
    ],
)

# 提取回复
reply = response.choices[0].message.content

# 查看 token 消耗
usage = response.usage  # prompt_tokens / completion_tokens / total_tokens
```

**要点：**
- `choices[0]` — 默认只生成 1 个回复（可通过 `n` 参数生成多个）
- `usage` — 用于监控成本和调试

### 示例 2：多轮对话

实现上下文记忆的核心模式：

```python
messages = [{"role": "system", "content": "你是一个 Python 教师"}]

for user_input in conversations:
    # 1. 追加用户消息
    messages.append({"role": "user", "content": user_input})

    # 2. 发送完整历史给 API
    response = client().chat.completions.create(model=..., messages=messages)

    # 3. 追加助手回复（关键！）
    messages.append({"role": "assistant", "content": response.choices[0].message.content})
```

**要点：**
- 每次调用都发送 **完整历史**，模型才能理解上下文
- 必须把 assistant 回复也加回 messages，否则下一轮模型"失忆"
- 对话越长，token 消耗越大（注意成本控制）

### 示例 3：流式输出

逐字显示回复，提升用户体验：

```python
stream = client().chat.completions.create(
    model=...,
    messages=[...],
    stream=True,  # 开启流式
)

for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        print(delta.content, end="", flush=True)
```

**要点：**
- `stream=True` 返回一个迭代器，而非完整响应
- 每个 `chunk` 包含一小段增量文本 (`delta.content`)
- 流式模式下无法直接获取 `usage` 信息
- 适用于聊天界面、长文本生成等场景

### 示例 4：Temperature 对比

同一 prompt，不同 temperature 产生不同风格的输出：

```python
for temp in [0.0, 0.5, 1.0]:
    response = client().chat.completions.create(
        model=...,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        max_tokens=50,
    )
```

**Temperature 选择指南：**

| 值 | 特点 | 适用场景 |
|----|------|----------|
| 0.0 | 确定性最强，每次结果几乎相同 | 代码生成、数据提取、分类任务 |
| 0.3~0.7 | 平衡创造性和一致性 | 通用对话、写作辅助 |
| 0.8~1.0 | 高度随机，输出多样 | 头脑风暴、创意写作 |

> ⚠️ 注意：不同 API 提供商的 temperature 范围不同。OpenAI 支持 [0, 2]，智谱支持 [0, 1]。

---

## 响应结构速查

```python
response = client().chat.completions.create(...)

response.id                  # 请求唯一 ID
response.model               # 实际使用的模型
response.choices[0].message.role       # "assistant"
response.choices[0].message.content    # 回复文本
response.choices[0].finish_reason      # "stop" / "length"
response.usage.prompt_tokens           # 输入 token 数
response.usage.completion_tokens       # 输出 token 数
response.usage.total_tokens            # 总 token 数
```

---

## 常见问题

**Q: 为什么每次调用都要发送完整历史？**
A: LLM 是无状态的，它不会"记住"上一次调用。上下文完全由你传入的 messages 决定。

**Q: 对话太长怎么办？**
A: 常见策略：截断早期消息、使用摘要压缩历史、利用模型的长上下文窗口。

**Q: stream 模式和非 stream 模式有什么区别？**
A: 非 stream 等全部生成完毕后一次性返回；stream 边生成边返回，首字延迟更低，适合交互场景。

---

## 下一步

→ [02_prompt_engineering.py](./02_prompt_engineering.py) - 学习提示词工程技巧
