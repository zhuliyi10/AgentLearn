"""
tools.py - 研究助手的工具层 (阶段 2 工具调用的实战应用)

Agent 要研究一个主题, 就得能"看到外部世界"。这里提供一个网页搜索工具:
  - web_search():   真正干活的 Python 函数 (基于 Bing 搜索 + HTML 解析)
  - SEARCH_TOOL:    交给 LLM 的工具 Schema (function calling 定义)
  - execute_tool(): 工具名 → 函数 的分发器

这一层刻意和"Agent 逻辑"分离: 工具只管返回数据, 不关心谁在调用。
如果没有网络, web_search 会优雅降级 (返回错误提示), 整条流水线仍能跑通。
"""

import json


def web_search(query: str, top_k: int = 3) -> list[dict]:
    """
    网页搜索工具 (使用 Bing 搜索, 解析前 top_k 条结果)。

    返回: [{"title": ..., "snippet": ..., "url": ...}, ...]
    失败时返回 [{"error": ...}], 不抛异常 —— 让 Agent 自己决定如何应对。
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        resp = httpx.get(
            "https://cn.bing.com/search",
            params={"q": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36"
                )
            },
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.b_algo")[:top_k]

        results = []
        for item in items:
            title_el = item.select_one("h2")
            snippet_el = item.select_one(".b_caption p")
            link_el = item.select_one("h2 a")
            results.append({
                "title": title_el.get_text() if title_el else "",
                "snippet": snippet_el.get_text()[:200] if snippet_el else "",
                "url": link_el.get("href") if link_el else "",
            })
        return results or [{"note": "未找到结果"}]
    except Exception as e:
        return [{"error": f"搜索失败: {e}"}]


# 交给 LLM 的工具定义 (回忆阶段 2: 这是 function calling 的 Schema)
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜索互联网获取实时信息、事实和资料。研究任何主题时都应主动使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词, 越具体越好"},
            },
            "required": ["query"],
        },
    },
}


def execute_tool(name: str, args: dict) -> str:
    """
    工具分发器: 根据 LLM 给出的工具名执行对应函数, 返回 JSON 字符串。

    工具的返回值必须是字符串 (要塞进 tool role 消息), 所以统一 json.dumps。
    """
    if name == "web_search":
        results = web_search(args["query"])
        return json.dumps({"query": args["query"], "results": results}, ensure_ascii=False)
    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
