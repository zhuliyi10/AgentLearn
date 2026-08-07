"""
通用辅助函数模块

提供项目中各示例共用的工具函数。
"""

import json
import typing
from typing import Any

from pydantic import BaseModel


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


def json_skeleton(model_cls: type[BaseModel]) -> str:
    """
    根据 Pydantic 模型生成带占位说明的 JSON 骨架。

    为什么需要它?
        直接把 model_json_schema() 塞进提示词, 有些模型会把 Schema 本身原样
        抄回来 (输出 {"type": "object", ...} 而不是真实数据)。
        改成给一个"填空模板"—— 字段名固定、值是 <说明> 占位 —— 能非常可靠地
        引导模型输出符合结构的实例。支持嵌套模型和列表。

    示例输出:
        { "title": <报告标题>, "sections": [ { "heading": <章节标题> }, ... ] }
    """
    def is_model(t: Any) -> bool:
        return isinstance(t, type) and issubclass(t, BaseModel)

    def render_model(cls: type[BaseModel]) -> str:
        parts = [
            f'"{name}": {render_value(f.annotation, f.description or name)}'
            for name, f in cls.model_fields.items()
        ]
        return "{ " + ", ".join(parts) + " }"

    def render_value(ann: Any, desc: str) -> str:
        if is_model(ann):
            return render_model(ann)
        if typing.get_origin(ann) is list:
            args = typing.get_args(ann)
            item = args[0] if args else str
            if is_model(item):
                return f"[ {render_model(item)}, ... ]"
            return f"[ <{desc}> ]"
        return f"<{desc}>"

    return render_model(model_cls)
