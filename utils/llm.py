"""
LLM 客户端封装模块

提供统一的 OpenAI 客户端初始化，支持:
- 从 .env 文件加载配置
- 自定义 base_url (兼容 DeepSeek/Moonshot/Ollama 等)
- 默认模型配置
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
load_dotenv()


def get_client() -> OpenAI:
    """获取 OpenAI 客户端实例"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")  # 可选

    if not api_key:
        raise ValueError(
            "未设置 OPENAI_API_KEY 环境变量。\n"
            "请复制 .env.example 为 .env 并填入你的 API Key。"
        )

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def get_model() -> str:
    """获取默认模型名称"""
    return os.getenv("OPENAI_MODEL", "gpt-4o")


# 便捷单例 (延迟初始化)
_client: OpenAI | None = None


def client() -> OpenAI:
    """获取全局客户端单例"""
    global _client
    if _client is None:
        _client = get_client()
    return _client
