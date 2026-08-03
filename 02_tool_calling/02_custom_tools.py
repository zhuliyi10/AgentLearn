"""
02 - 自定义工具实现

学习目标:
- 掌握工具注册的设计模式 (装饰器/类/字典映射)
- 实现实用工具: 网页搜索、文件读写、时间查询
- 学会工具的错误处理与结果格式化
- 理解工具描述 (description) 对 LLM 调用的影响

运行方式:
    python 02_tool_calling/02_custom_tools.py
"""

import sys
import json
import math
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm import client, get_model
from utils.helpers import print_separator


# ============================================================
# 工具注册表模式 - 用装饰器自动注册工具
# ============================================================

class ToolRegistry:
    """工具注册表: 管理所有可用工具"""

    def __init__(self):
        self._tools: dict[str, dict] = {}  # name -> {"func": callable, "schema": dict}

    def register(self, name: str, description: str, parameters: dict):
        """装饰器: 注册一个工具"""
        def decorator(func):
            self._tools[name] = {
                "func": func,
                "schema": {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": parameters,
                    },
                },
            }
            return func
        return decorator

    def get_openai_tools(self) -> list[dict]:
        """获取 OpenAI tools 格式的工具列表"""
        return [t["schema"] for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> str:
        """执行指定工具，返回字符串结果"""
        if name not in self._tools:
            return json.dumps({"error": f"未知工具: {name}"})
        try:
            result = self._tools[name]["func"](**arguments)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"工具执行失败: {str(e)}"}, ensure_ascii=False)

    def list_tools(self) -> list[str]:
        """列出所有已注册工具名"""
        return list(self._tools.keys())


# 创建全局注册表
registry = ToolRegistry()


# ============================================================
# 注册自定义工具
# ============================================================

@registry.register(
    name="web_search",
    description="搜索互联网获取实时信息。适用于查询新闻、事实、最新数据等。",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词",
            },
            "max_results": {
                "type": "integer",
                "description": "最大返回结果数，默认 3",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, max_results: int = 3) -> str:
    """网页搜索工具 (使用 Bing 搜索)"""
    try:
        import httpx
        from bs4 import BeautifulSoup

        resp = httpx.get(
            "https://cn.bing.com/search",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.b_algo")

        if not items:
            return json.dumps({"results": [], "message": "未找到相关结果"}, ensure_ascii=False)

        formatted = []
        for item in items[:max_results]:
            title_el = item.select_one("h2")
            link_el = item.select_one("h2 a")
            snippet_el = item.select_one(".b_caption p")
            formatted.append({
                "title": title_el.get_text() if title_el else "",
                "snippet": snippet_el.get_text()[:200] if snippet_el else "",
                "url": link_el["href"] if link_el and link_el.has_attr("href") else "",
            })
        return json.dumps({"query": query, "results": formatted}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"搜索失败: {str(e)}"}, ensure_ascii=False)


@registry.register(
    name="get_current_time",
    description="获取当前日期和时间信息",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "时区，如 'Asia/Shanghai'，默认为本地时间",
            },
        },
        "required": [],
    },
)
def get_current_time(timezone: str = "") -> str:
    """获取当前时间"""
    now = datetime.now()
    return json.dumps({
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "timezone": timezone or "local",
    }, ensure_ascii=False)


@registry.register(
    name="math_calculator",
    description="执行高级数学计算，支持三角函数、对数、幂运算等",
    parameters={
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["sin", "cos", "tan", "log", "sqrt", "power", "factorial"],
                "description": "运算类型",
            },
            "x": {
                "type": "number",
                "description": "输入数值",
            },
            "y": {
                "type": "number",
                "description": "第二个数值 (power 运算时作为指数)",
            },
        },
        "required": ["operation", "x"],
    },
)
def math_calculator(operation: str, x: float, y: float = 0) -> str:
    """高级数学计算器"""
    try:
        ops = {
            "sin": lambda: math.sin(math.radians(x)),
            "cos": lambda: math.cos(math.radians(x)),
            "tan": lambda: math.tan(math.radians(x)),
            "log": lambda: math.log(x),
            "sqrt": lambda: math.sqrt(x),
            "power": lambda: x ** y,
            "factorial": lambda: math.factorial(int(x)),
        }

        if operation not in ops:
            return json.dumps({"error": f"不支持的运算: {operation}"})

        result = ops[operation]()
        return json.dumps({
            "operation": operation,
            "input": {"x": x, "y": y} if y else {"x": x},
            "result": round(result, 10),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"计算错误: {str(e)}"}, ensure_ascii=False)


@registry.register(
    name="read_file",
    description="读取本地文件内容。仅限读取项目目录内的文本文件。",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件路径 (相对于项目根目录)",
            },
            "max_lines": {
                "type": "integer",
                "description": "最多读取行数，默认 50",
            },
        },
        "required": ["file_path"],
    },
)
def read_file(file_path: str, max_lines: int = 50) -> str:
    """读取文件内容 (带安全限制)"""
    try:
        # 安全限制: 只允许读取项目目录内的文件
        project_root = Path(__file__).resolve().parent.parent
        target = (project_root / file_path).resolve()

        if not str(target).startswith(str(project_root)):
            return json.dumps({"error": "安全限制: 不能读取项目目录外的文件"})

        if not target.exists():
            return json.dumps({"error": f"文件不存在: {file_path}"})

        lines = target.read_text(encoding="utf-8").splitlines()[:max_lines]
        return json.dumps({
            "file": file_path,
            "total_lines": len(target.read_text().splitlines()),
            "content": "\n".join(lines),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"读取失败: {str(e)}"}, ensure_ascii=False)


# ============================================================
# 演示: 使用注册表驱动对话
# ============================================================

def demo_tool_registry():
    """演示: 工具注册表 + LLM 对话"""
    print_separator("工具注册表演示")

    print(f"已注册工具: {registry.list_tools()}\n")

    # 测试问题 (会触发不同工具)
    questions = [
        "现在几点了？",
        "计算 sin(30) 的值",
        "帮我搜索一下 Python 3.12 有什么新特性",
    ]

    for question in questions:
        print(f"[用户]: {question}")

        messages = [
            {"role": "system", "content": "你是一个助手。当用户的问题匹配可用工具时，直接调用工具，不要反问用户。对于未指定的可选参数，使用合理默认值。"},
            {"role": "user", "content": question},
        ]

        response = client().chat.completions.create(
            model=get_model(),
            messages=messages,
            tools=registry.get_openai_tools(),
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append(msg)
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)
                print(f"  → 调用: {name}({args})")

                result = registry.execute(name, args)
                print(f"  ← 结果: {result[:150]}{'...' if len(result) > 150 else ''}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

            final = client().chat.completions.create(
                model=get_model(),
                messages=messages,
                tools=registry.get_openai_tools(),
            )
            print(f"  [回答]: {final.choices[0].message.content}\n")
        else:
            print(f"  [回答]: {msg.content}\n")


def demo_tool_description_impact():
    """演示: 工具描述对 LLM 选择的影响"""
    print_separator("工具描述的重要性")

    print("""
工具描述 (description) 直接影响 LLM 的调用决策:

  差的描述: "计算"
  → LLM 不确定何时该用这个工具

  好的描述: "执行高级数学计算，支持三角函数、对数、幂运算等。
            适用于需要精确数学计算的场合，不适合简单加减法。"
  → LLM 清楚知道什么场景该调用

最佳实践:
  1. 说明工具能做什么 (能力)
  2. 说明什么场景该用 (适用条件)
  3. 说明什么场景不该用 (排除条件)
  4. 参数描述要具体，给出示例值
""")


if __name__ == "__main__":
    print("=== 02 自定义工具 ===\n")

    demo_tool_registry()
    demo_tool_description_impact()

    print_separator("完成")
    print("核心要点:")
    print("  1. ToolRegistry 模式让工具管理更清晰")
    print("  2. 装饰器注册让添加新工具非常简单")
    print("  3. 工具描述的质量直接决定 LLM 调用的准确性")
    print("  4. 错误处理必须完善，返回结构化错误信息")
    print("\n下一步: 03_tool_loop.py - 实现完整的 Agent 工具调用循环")
