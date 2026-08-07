"""
sandbox.py - 代码执行沙箱 (阶段 2 "工具"的实战应用)

对研究助手来说, 工具是"搜索"; 对代码助手来说, 最重要的工具是"真的把代码
跑起来"。本模块提供这个能力:

    run_tests(code, test_cases) → TestReport

它把 LLM 生成的代码和测试用例组装成一个独立脚本, 用 **子进程** 运行:
  - 子进程隔离: 生成的代码崩溃/死循环也不会拖垮主程序
  - 超时保护: 死循环会被 timeout 强制杀掉
  - 客观反馈: 返回的 TestReport 是真实运行结果, 是反思循环的事实依据

⚠️ 说明: 这是教学用的轻量沙箱 (子进程 + 超时)。生产环境执行不可信代码
应使用容器 / gVisor / 无网络的严格隔离环境。
"""

import sys
import json
import subprocess
import tempfile
from pathlib import Path

from .schemas import TestCase, TestReport


# 测试运行脚本模板。__USER_CODE__ 和 __TESTS_JSON__ 会在运行时替换。
# 它执行用户代码, 逐个跑测试用例, 最后打印一行 JSON 汇总结果。
_HARNESS = '''
import json, traceback

# ---- 被测代码 ----
{user_code}

# ---- 测试用例 (call / expected 都是字符串表达式) ----
_TESTS = json.loads({tests_json!r})

_failed = []
for t in _TESTS:
    try:
        actual = eval(t["call"])
        expected = eval(t["expected"])
        if actual != expected:
            _failed.append(f"{{t['description']}}: {{t['call']}} 得到 {{actual!r}}, 期望 {{expected!r}}")
    except Exception:
        _failed.append(f"{{t['description']}}: {{t['call']}} 抛出异常\\n{{traceback.format_exc()}}")

print("__RESULT__" + json.dumps({{
    "total": len(_TESTS),
    "failed": len(_failed),
    "details": "\\n".join(_failed),
}}, ensure_ascii=False))
'''


def run_tests(code: str, test_cases: list[TestCase], timeout: int = 10) -> TestReport:
    """
    在子进程中运行代码及其测试用例, 返回客观的 TestReport。

    任何失败模式都会被转成 TestReport (而非抛异常), 以便反思循环消费:
      - 语法错误 / 导入错误 → 子进程非零退出, 用 stderr 作为 details
      - 断言不符 / 运行异常 → 由 harness 收集进 details
      - 死循环 → 超时被杀, details 记为超时
    """
    tests_json = json.dumps([tc.model_dump() for tc in test_cases], ensure_ascii=False)
    script = _HARNESS.format(user_code=code, tests_json=tests_json)

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(script)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return TestReport(passed=False, total=len(test_cases), failed=len(test_cases),
                          details=f"执行超时 (>{timeout}s), 可能存在死循环。")
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # 子进程崩溃 (语法/运行时错误): 用 stderr 作为反馈
    if proc.returncode != 0:
        return TestReport(passed=False, total=len(test_cases), failed=len(test_cases),
                          details=f"代码无法运行:\n{proc.stderr.strip()}")

    # 解析 harness 打印的结果行
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT__"):
            data = json.loads(line[len("__RESULT__"):])
            return TestReport(
                passed=data["failed"] == 0,
                total=data["total"],
                failed=data["failed"],
                details=data["details"] or "全部通过",
            )

    # 兜底: 没拿到结果行
    return TestReport(passed=False, total=len(test_cases), failed=len(test_cases),
                      details=f"未能解析测试结果。stdout:\n{proc.stdout}")
