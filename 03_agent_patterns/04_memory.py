"""
04 - 记忆机制 (短期/长期/向量)

学习目标:
- 理解 Agent 记忆系统的三种类型
- 实现短期记忆 (对话历史管理)
- 实现长期记忆 (向量数据库存储与检索)
- 掌握 ChromaDB 的基本使用
- 理解记忆对 Agent 持续学习的重要性

核心思想:
    短期记忆: 当前对话上下文 (messages 列表)
    长期记忆: 持久化存储的知识 (向量数据库)
    工作记忆: 当前任务的临时信息 (scratchpad)

运行方式:
    python 03_agent_patterns/04_memory.py
"""

import sys
import json
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 1. 短期记忆: 对话历史管理
# ============================================================

class ShortTermMemory:
    """
    短期记忆: 管理当前对话的上下文

    解决的问题:
    - LLM 有上下文窗口限制 (如 128K tokens)
    - 对话太长会超出限制
    - 需要智能管理历史消息
    """

    def __init__(self, max_messages: int = 20, max_tokens: int = 4000):
        self.messages: list[dict] = []
        self.max_messages = max_messages
        self.max_tokens = max_tokens

    def add(self, role: str, content: str):
        """添加消息到短期记忆"""
        self.messages.append({"role": role, "content": content})
        self._trim()  # 自动裁剪

    def get_messages(self) -> list[dict]:
        """获取当前消息列表"""
        return self.messages

    def _trim(self):
        """裁剪消息列表，防止超出限制"""
        # 策略1: 保留 system 消息，限制总消息数
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        other_msgs = [m for m in self.messages if m["role"] != "system"]

        if len(other_msgs) > self.max_messages:
            # 保留最近的消息
            other_msgs = other_msgs[-self.max_messages:]

        self.messages = system_msgs + other_msgs

    def clear(self):
        """清空短期记忆"""
        system_msgs = [m for m in self.messages if m["role"] == "system"]
        self.messages = system_msgs

    def summary(self) -> str:
        """生成对话摘要 (用于压缩记忆)"""
        if len(self.messages) <= 5:
            return ""

        # 用 LLM 生成对话摘要
        response = client().chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "请用一句话总结以下对话的核心内容。"},
                {"role": "user", "content": json.dumps(self.messages[-10:], ensure_ascii=False)},
            ],
        )
        return response.choices[0].message.content


# ============================================================
# 2. 长期记忆: 向量数据库
# ============================================================

class LongTermMemory:
    """
    长期记忆: 使用向量数据库存储和检索知识

    工作原理:
    1. 存储: 文本 → Embedding 向量 → 存入向量数据库
    2. 检索: 查询文本 → Embedding → 相似度搜索 → 返回相关记忆

    使用 ChromaDB 作为向量数据库 (轻量级，适合学习)
    使用 OpenAI 兼容 API 生成 Embedding (避免本地 ONNX 模型下载问题)
    """

    def __init__(self, collection_name: str = "agent_memory"):
        import chromadb
        from chromadb.config import Settings
        import os

        # 自定义 Embedding 函数，使用 OpenAI 兼容 API
        class APIEmbeddingFunction:
            """使用 OpenAI 兼容 API 的 Embedding 函数"""
            def __init__(self):
                self._client = client()
                self._model = os.getenv("OPENAI_EMBEDDING_MODEL", "embedding-3")

            def __call__(self, input: list[str]) -> list[list[float]]:
                response = self._client.embeddings.create(
                    model=self._model,
                    input=input,
                )
                return [item.embedding for item in response.data]

            def embed_query(self, input: list[str]) -> list[list[float]]:
                """查询时的嵌入 (ChromaDB 要求)"""
                return self.__call__(input)

            def name(self) -> str:
                """ChromaDB 要求的唯一名称"""
                return "api_embedding_function"

        # 创建 ChromaDB 客户端 (持久化存储)
        self.chroma_client = chromadb.Client(Settings(
            is_persistent=True,
            persist_directory=str(Path(__file__).parent / ".chroma_data"),
            anonymized_telemetry=False,
        ))

        self._embedding_fn = APIEmbeddingFunction()

        # 获取或创建集合
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Agent 长期记忆"},
            embedding_function=self._embedding_fn,
        )

    def remember(self, content: str, metadata: dict = None):
        """记住一条信息"""
        doc_id = str(uuid.uuid4())
        self.collection.add(
            documents=[content],
            metadatas=[metadata or {}],
            ids=[doc_id],
        )
        print(f"  [记忆] 已存储: {content[:50]}...")

    def recall(self, query: str, n_results: int = 3) -> list[dict]:
        """回忆相关信息 (语义搜索)"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        memories = []
        if results["documents"] and results["documents"][0]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                memories.append({
                    "content": doc,
                    "metadata": meta,
                })

        return memories

    def forget(self, query: str, n_results: int = 1):
        """遗忘相关信息"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        if results["ids"] and results["ids"][0]:
            self.collection.delete(ids=results["ids"][0])
            print(f"  [遗忘] 已删除相关记忆")

    def count(self) -> int:
        """获取记忆总数"""
        return self.collection.count()


# ============================================================
# 3. 带记忆的 Agent
# ============================================================

class MemoryAgent:
    """
    带记忆的 Agent: 结合短期记忆和长期记忆

    工作流程:
    1. 用户输入
    2. 从长期记忆中检索相关信息
    3. 将检索结果注入上下文
    4. LLM 生成回答 (使用短期+长期记忆)
    5. 判断是否需要记住当前对话
    6. 更新短期记忆
    """

    def __init__(self, system_prompt: str = ""):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()

        if system_prompt:
            self.short_term.add("system", system_prompt)

    def chat(self, user_input: str) -> str:
        """处理用户输入"""
        print(f"\n[用户]: {user_input}")

        # 步骤1: 从长期记忆中检索相关信息
        print(f"\n[检索长期记忆]...")
        relevant_memories = self.long_term.recall(user_input, n_results=3)

        if relevant_memories:
            print(f"  找到 {len(relevant_memories)} 条相关记忆:")
            for mem in relevant_memories:
                print(f"    - {mem['content'][:80]}...")

        # 步骤2: 构建上下文 (注入长期记忆)
        messages = self.short_term.get_messages().copy()

        if relevant_memories:
            memory_context = "\n".join([f"- {m['content']}" for m in relevant_memories])
            messages.append({
                "role": "system",
                "content": f"以下是你记得的相关信息:\n{memory_context}",
            })

        messages.append({"role": "user", "content": user_input})

        # 步骤3: LLM 生成回答
        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
        )

        assistant_reply = response.choices[0].message.content
        print(f"\n[Agent]: {assistant_reply}")

        # 步骤4: 更新短期记忆
        self.short_term.add("user", user_input)
        self.short_term.add("assistant", assistant_reply)

        # 步骤5: 判断是否需要记住 (简化: 总是记住)
        # 实际项目中可以用 LLM 判断信息的重要性
        self.long_term.remember(
            content=f"用户说: {user_input}\nAgent回答: {assistant_reply[:200]}",
            metadata={"type": "conversation"},
        )

        return assistant_reply

    def get_stats(self) -> dict:
        """获取记忆统计信息"""
        return {
            "short_term_messages": len(self.short_term.messages),
            "long_term_memories": self.long_term.count(),
        }


# ============================================================
# 演示
# ============================================================

def demo_short_term_memory():
    """演示: 短期记忆管理"""
    print_separator("短期记忆演示")

    memory = ShortTermMemory(max_messages=5)

    # 模拟对话
    conversations = [
        ("user", "我叫小明"),
        ("assistant", "你好小明！有什么可以帮你的？"),
        ("user", "我想学习 Python"),
        ("assistant", "Python 是个很好的选择！"),
        ("user", "有什么推荐的书籍吗？"),
        ("assistant", "推荐《Python Crash Course》"),
        ("user", "这本书多少钱？"),
        ("assistant", "大约 50-80 元"),
    ]

    for role, content in conversations:
        memory.add(role, content)
        print(f"  [{role}]: {content}")

    print(f"\n当前消息数: {len(memory.messages)}")
    print(f"最大限制: {memory.max_messages}")
    print(f"实际保留: {len([m for m in memory.messages if m['role'] != 'system'])} 条用户/助手消息")


def demo_long_term_memory():
    """演示: 长期记忆存储与检索"""
    print_separator("长期记忆演示")

    memory = LongTermMemory(collection_name="demo_memory")

    # 存储一些知识
    print("\n[存储记忆]...")
    memories_to_store = [
        ("Python 的 GIL 使得多线程无法真正并行执行 CPU 密集型任务", {"topic": "python", "type": "fact"}),
        ("LangGraph 是基于图结构的 Agent 框架", {"topic": "langgraph", "type": "fact"}),
        ("ReAct 模式的核心是 Thought-Action-Observation 循环", {"topic": "agent", "type": "pattern"}),
        ("用户偏好使用中文进行编程学习", {"topic": "user", "type": "preference"}),
        ("用户正在学习 Agent 开发，目前进度到阶段3", {"topic": "user", "type": "progress"}),
    ]

    for content, meta in memories_to_store:
        memory.remember(content, meta)

    print(f"\n总记忆数: {memory.count()}")

    # 语义检索
    queries = ["Python 多线程有什么问题？", "用户喜欢什么语言？", "Agent 有哪些设计模式？"]

    for query in queries:
        print(f"\n[查询]: {query}")
        results = memory.recall(query, n_results=2)
        for i, mem in enumerate(results, 1):
            print(f"  {i}. {mem['content']}")


def demo_memory_agent():
    """演示: 带记忆的 Agent 对话"""
    print_separator("记忆 Agent 演示")

    agent = MemoryAgent(system_prompt="你是一个友好的助手，记住用户告诉你的信息，并在后续对话中使用。")

    # 多轮对话
    agent.chat("我叫小明，是一名 Python 开发者")
    agent.chat("我最近在学习 AI Agent 开发")
    agent.chat("你还记得我叫什么吗？我在学什么？")

    # 查看统计
    stats = agent.get_stats()
    print(f"\n[记忆统计]:")
    print(f"  短期记忆消息数: {stats['short_term_messages']}")
    print(f"  长期记忆条数: {stats['long_term_memories']}")


if __name__ == "__main__":
    print("=== 04 记忆机制 ===\n")

    demo_short_term_memory()
    demo_long_term_memory()
    demo_memory_agent()

    print_separator("阶段 3 完成!")
    print("你已掌握四种核心 Agent 模式:")
    print("  1. ReAct: 推理+行动交替 (Thought→Action→Observation)")
    print("  2. Plan-and-Execute: 先规划后执行")
    print("  3. Reflection: 生成→反思→改进迭代")
    print("  4. Memory: 短期+长期记忆系统")
    print("\n下一阶段: 04_langgraph/ - 使用 LangGraph 框架构建 Agent")
