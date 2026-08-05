"""
03 / server.py - 实用工具集 MCP Server

学习目标:
- 把 02 号文件学到的 MCP Server 概念用到「真实、有用」的工具上
- 掌握三类最常见的工具能力: 文件操作 / 数据库 / 外部 API 集成
- 学会给工具做「安全边界」(路径沙箱、参数校验、错误处理)

本 Server 暴露的工具:
    文件操作 (沙箱在本目录的 sandbox/ 下):
      • write_file(name, content)   写入文件
      • read_file(name)             读取文件
      • list_files()                列出所有文件

    数据库 (SQLite, notes.db):
      • add_note(title, content)    新增一条笔记
      • list_notes()                列出所有笔记
      • search_notes(keyword)       按关键词搜索笔记

    外部 API 集成:
      • http_get(url)               发起 GET 请求, 返回状态码与正文摘要

    工具 (无副作用):
      • calculate(expression)       计算数学表达式

运行方式:
    # 作为 stdio Server 启动 (通常由 client_demo.py / agent.py 拉起)
    python 05_mcp/03_mcp_tools/server.py serve

    # 直接运行则打印说明 (真正跑起来请加 serve 参数, 或运行 client_demo.py)
    python 05_mcp/03_mcp_tools/server.py
"""

import sqlite3
import sys
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

# ============================================================
# 沙箱与数据库路径 (都放在本目录下, 且已被 .gitignore 忽略)
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
SANDBOX_DIR = BASE_DIR / "sandbox"      # 文件操作只允许在这个目录内进行
DB_PATH = BASE_DIR / "notes.db"         # SQLite 数据库文件

SANDBOX_DIR.mkdir(exist_ok=True)


server = MCPServer(
    name="toolkit-server",
    version="0.1.0",
    instructions=(
        "一个实用工具集 Server, 提供文件读写、笔记数据库、HTTP 请求、"
        "数学计算等能力。文件操作被限制在沙箱目录内, 请放心调用。"
    ),
)


# ============================================================
# 1. 文件操作工具 (带路径沙箱, 防止越权访问)
# ============================================================

def _safe_path(name: str) -> Path:
    """
    把用户给的文件名解析到沙箱内, 并阻止「路径穿越」攻击。

    比如用户传入 "../../etc/passwd", 直接拼接会读到系统敏感文件。
    这里先解析成绝对路径, 再校验它确实位于沙箱目录之下。
    这是工具开发中最容易被忽视、却最重要的安全边界。
    """
    target = (SANDBOX_DIR / name).resolve()
    if not target.is_relative_to(SANDBOX_DIR):
        raise ValueError(f"非法路径: {name} (只允许访问沙箱目录内的文件)")
    return target


@server.tool(description="把内容写入沙箱内的文件, 返回写入结果")
def write_file(name: str, content: str) -> str:
    path = _safe_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"已写入 {name} ({len(content)} 字符)"


@server.tool(description="读取沙箱内某个文件的内容")
def read_file(name: str) -> str:
    path = _safe_path(name)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {name}")
    return path.read_text(encoding="utf-8")


@server.tool(description="列出沙箱内的所有文件")
def list_files() -> str:
    files = sorted(p.name for p in SANDBOX_DIR.iterdir() if p.is_file())
    if not files:
        return "(沙箱目录为空)"
    return "\n".join(files)


# ============================================================
# 2. 数据库工具 (SQLite 笔记本)
# ============================================================

def _db() -> sqlite3.Connection:
    """
    每次调用都开一个新连接 —— 简单且线程安全。
    (MCP 工具函数可能在不同线程被调用, 复用连接容易出问题。)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS notes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "content TEXT NOT NULL)"
    )
    return conn


@server.tool(description="新增一条笔记, 返回新笔记的 id")
def add_note(title: str, content: str) -> str:
    conn = _db()
    try:
        cur = conn.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?)",
            (title, content),
        )
        conn.commit()
        return f"已添加笔记 #{cur.lastrowid}: {title}"
    finally:
        conn.close()


@server.tool(description="列出所有笔记的标题")
def list_notes() -> str:
    conn = _db()
    try:
        rows = conn.execute("SELECT id, title FROM notes ORDER BY id").fetchall()
    finally:
        conn.close()
    if not rows:
        return "(还没有任何笔记)"
    return "\n".join(f"#{rid} {title}" for rid, title in rows)


@server.tool(description="按关键词搜索笔记 (匹配标题或正文)")
def search_notes(keyword: str) -> str:
    conn = _db()
    try:
        like = f"%{keyword}%"
        rows = conn.execute(
            "SELECT id, title, content FROM notes "
            "WHERE title LIKE ? OR content LIKE ? ORDER BY id",
            (like, like),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return f"没有找到包含 '{keyword}' 的笔记"
    return "\n".join(f"#{rid} {title}: {content}" for rid, title, content in rows)


# ============================================================
# 3. 外部 API 集成工具 (HTTP 请求)
# ============================================================

@server.tool(description="对给定 URL 发起 HTTP GET 请求, 返回状态码和正文摘要")
def http_get(url: str, max_chars: int = 500) -> str:
    """
    演示「把外部 API 包装成 MCP 工具」。
    真实项目里, 你可以据此封装天气、搜索、股票等任意 REST API。
    注意: 设了超时, 并对异常做了处理, 避免拖垮 Server。
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError("url 必须以 http:// 或 https:// 开头")
    resp = httpx.get(url, timeout=10.0, follow_redirects=True)
    body = resp.text.strip().replace("\n", " ")
    if len(body) > max_chars:
        body = body[:max_chars] + f"... (共 {len(resp.text)} 字符)"
    return f"HTTP {resp.status_code} | {body}"


# ============================================================
# 4. 纯计算工具 (无副作用)
# ============================================================

@server.tool(description="计算一个数学表达式, 如 '2 * (3 + 4)'")
def calculate(expression: str) -> str:
    """
    用受限的 eval 计算表达式: 禁用内建函数, 只允许数字与算术运算,
    避免 eval 被用来执行任意代码。
    """
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        raise ValueError("表达式只能包含数字和 + - * / ( ) . % 运算符")
    result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 (已做字符白名单)
    return f"{expression} = {result}"


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        server.run("stdio")
        sys.exit(0)

    print("这是一个 MCP Server 脚本, 本身不产生可读输出。")
    print("请运行以下命令来体验它:")
    print("  python 05_mcp/03_mcp_tools/client_demo.py   # 用 Client 驱动全部工具")
    print("  python 05_mcp/03_mcp_tools/agent.py         # 让 LLM 自动调用这些工具")
    print("\n或作为真正的 stdio Server 启动 (会阻塞等待输入):")
    print("  python 05_mcp/03_mcp_tools/server.py serve")
