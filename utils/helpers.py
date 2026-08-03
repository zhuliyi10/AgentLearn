"""
通用辅助函数模块

提供项目中各示例共用的工具函数。
"""

import json
from typing import Any


def print_separator(title: str = "") -> None:
    """打印分隔线，用于示例输出格式化"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print(f"\n{'-'*60}\n")


def print_messages(messages: list[dict]) -> None:
    """格式化打印消息列表"""
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if content:
            print(f"[{role}]: {content[:200]}{'...' if len(content) > 200 else ''}")
        # 打印工具调用信息
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                func = tc["function"]
                print(f"[{role}] 调用工具: {func['name']}({func['arguments']})")


def pretty_json(data: Any) -> str:
    """将数据格式化为美观的 JSON 字符串"""
    return json.dumps(data, ensure_ascii=False, indent=2)


def truncate(text: str, max_len: int = 500) -> str:
    """截断过长文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... (共 {len(text)} 字符)"
