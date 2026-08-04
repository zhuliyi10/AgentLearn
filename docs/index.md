# Agent 学习项目 - 全局学习规划

## 项目概述

本项目是一个渐进式 AI Agent 开发学习路径，从 LLM 基础 API 调用出发，逐步深入到 Agent 设计模式、框架使用、协议实现和多 Agent 协作，最终完成端到端的 Agent 应用。

**技术栈**: Python 3.11+ / OpenAI SDK / LangGraph / MCP / Pydantic / ChromaDB

---

## 学习路线总览

```
阶段1        阶段2          阶段3           阶段4         阶段5      阶段6         阶段7
LLM基础  →  工具调用  →  Agent模式  →  LangGraph  →  MCP协议  →  多Agent  →  实战项目
(API调用)   (Function    (ReAct/       (工业级      (Model     (协作架构)  (研究助手/
             Calling)    Plan/Reflect)  框架)       Context)               代码助手)
```

---

## 阶段 1: LLM 基础 (`01_basics/`)

**目标**: 掌握与 LLM 交互的基本能力，为后续 Agent 开发打下基础。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_chat_completion.py` | Chat API 基础调用 | messages 角色、多轮对话、streaming、temperature |
| `02_prompt_engineering.py` | 提示词工程 | System Prompt 设计、Few-shot、Chain-of-Thought |
| `03_structured_output.py` | 结构化输出 | JSON Mode、Pydantic 校验、Schema 引导 |

**学完你应该能**:
- [ ] 独立完成多轮对话并维护上下文
- [ ] 设计有效的 System Prompt
- [ ] 让 LLM 输出可靠的结构化数据

**预计时间**: 1-2 天

---

## 阶段 2: 工具调用 (`02_tool_calling/`)

**目标**: 理解 Agent 的核心机制 —— LLM 通过工具与外部世界交互。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_function_calling.py` | OpenAI Function Calling | tools 参数定义、tool_calls 解析、tool role 消息 |
| `02_custom_tools.py` | 自定义工具实现 | 工具注册模式、参数校验、错误处理 |
| `03_tool_loop.py` | 工具调用循环 | Agent 核心循环: 决策→调用→观察→继续 |

**学完你应该能**:
- [ ] 定义工具 Schema 并让 LLM 正确调用
- [ ] 实现完整的 tool loop (Agent 最小闭环)
- [ ] 理解"LLM 是大脑，工具是手脚"的架构思想

**预计时间**: 2-3 天

---

## 阶段 3: Agent 设计模式 (`03_agent_patterns/`)

**目标**: 手动实现经典 Agent 模式，深入理解原理（不依赖框架）。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_react.py` | ReAct 模式 | Thought→Action→Observation 循环、推理与行动交替 |
| `02_plan_and_execute.py` | Plan-and-Execute | 先规划后执行、动态 replan、任务分解 |
| `03_reflection.py` | Reflection 反思 | 生成→评估→改进迭代、自我批评、质量提升 |
| `04_memory.py` | 记忆机制 | 短期记忆(对话)、长期记忆(向量库)、记忆检索 |

**学完你应该能**:
- [ ] 手写实现 ReAct Agent 并解释其工作原理
- [ ] 设计带规划能力的 Agent (先想后做)
- [ ] 用反思机制提升 Agent 输出质量
- [ ] 为 Agent 添加向量数据库长期记忆

**预计时间**: 4-5 天

---

## 阶段 4: LangGraph 框架 (`04_langgraph/`)

**目标**: 使用工业级框架构建可靠、可控的 Agent 系统。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_graph_basics.py` | 图基础 | StateGraph、Node、Edge、State 定义 |
| `02_conditional_edges.py` | 条件路由 | 根据状态决定下一步、分支逻辑 |
| `03_human_in_loop.py` | 人工介入 | interrupt、审批节点、断点恢复 |
| `04_subgraph.py` | 子图模块化 | 图嵌套、模块复用、关注点分离 |

**学完你应该能**:
- [ ] 用 LangGraph 构建有状态的 Agent 工作流
- [ ] 实现条件分支和循环控制
- [ ] 在关键节点加入人工审批
- [ ] 将复杂 Agent 拆分为可维护的子模块

**预计时间**: 3-4 天

---

## 阶段 5: MCP 协议 (`05_mcp/`)

**目标**: 理解并实现 Model Context Protocol，掌握 Agent 工具生态标准。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_mcp_client.py` | MCP Client | 连接 Server、发现工具、调用工具 |
| `02_mcp_server.py` | MCP Server | 暴露工具、资源管理、协议实现 |
| `03_mcp_tools/` | 自定义工具集 | 文件操作、数据库、API 集成等实用工具 |

**学完你应该能**:
- [ ] 解释 MCP 协议的设计理念和通信机制
- [ ] 开发自己的 MCP Server 并暴露工具
- [ ] 让 Agent 通过 MCP 连接外部能力

**预计时间**: 2-3 天

---

## 阶段 6: 多 Agent 协作 (`06_multi_agent/`)

**目标**: 掌握多 Agent 系统的常见架构模式。

| 文件 | 内容 | 核心知识点 |
|------|------|-----------|
| `01_supervisor.py` | Supervisor 模式 | 主控分配任务、Worker 执行、结果汇总 |
| `02_hierarchical.py` | 层级式 | 多层管理、逐级分解、职责划分 |
| `03_collaborative.py` | 协作式 | 平等协作、共享上下文、轮流发言 |
| `04_debate.py` | 辩论式 | 对抗生成、多视角分析、共识达成 |

**学完你应该能**:
- [ ] 设计 Supervisor 架构解决复杂任务
- [ ] 实现 Agent 间的状态共享与消息传递
- [ ] 根据任务特点选择合适的协作模式

**预计时间**: 3-4 天

---

## 阶段 7: 端到端项目 (`07_project/`)

**目标**: 综合运用所有知识，构建生产级 Agent 应用。

### 项目 A: 研究助手 (`research_agent/`)

```
用户输入研究主题
    → 规划搜索策略 (Plan)
    → 多源并行检索 (Tools + Multi-Agent)
    → 信息整合分析 (Reflection)
    → 生成结构化报告 (Structured Output)
```

### 项目 B: 代码助手 (`code_agent/`)

```
用户描述需求
    → 理解并拆解任务 (Plan)
    → 生成代码 (Action)
    → 执行测试 (Tool)
    → 反思修复 (Reflection Loop)
    → 输出最终结果
```

**预计时间**: 5-7 天

---

## 环境配置

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -e .

# 3. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
# 如使用兼容 API (DeepSeek/Moonshot)，还需设置 OPENAI_BASE_URL
```

## 运行方式

每个文件都可独立运行:

```bash
python 01_basics/01_chat_completion.py
python 02_tool_calling/01_function_calling.py
# ...以此类推
```

---

## 学习建议

1. **先跑通再理解**: 每个示例先运行看效果，再逐行读代码理解原理
2. **动手改**: 修改参数、换提示词、加工具，观察行为变化
3. **手写核心逻辑**: 阶段 3 的模式尝试不看代码自己实现一遍
4. **做笔记**: 在每个文件顶部记录自己的理解和实验结果
5. **循序渐进**: 不要跳阶段，每个阶段都是下一阶段的基础

---

## 参考资源

- [OpenAI API 文档](https://platform.openai.com/docs)
- [LangGraph 官方教程](https://langchain-ai.github.io/langgraph/)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Anthropic Agent 设计模式](https://docs.anthropic.com/en/docs/build-with-claude/agentic)
- [Lilian Weng: LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
