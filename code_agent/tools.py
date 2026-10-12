"""工具集：文件系统读取、正则搜索、受控的 Python 代码执行。

设计原则：
- 所有路径限制在 AGENT_WORKSPACE 内，防止越界读写；
- 所有工具有超时与输出截断，避免污染上下文；
- 工具不抛异常给模型，统一返回可读的错误字符串，让 Agent 自行纠错重试。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", ".")).resolve()
MAX_OUTPUT_CHARS = 4000
DEFAULT_TIMEOUT = 15


def _clip(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[输出已截断，原始长度 {len(text)} 字符]"


def _resolve(path: str) -> Path:
    target = (WORKSPACE / path).resolve()
    if target != WORKSPACE and WORKSPACE not in target.parents:
        raise ValueError(f"拒绝访问工作区之外的路径: {path}")
    return target


def list_dir(path: str = ".") -> str:
    """列出工作区内某个目录的文件与子目录。"""
    try:
        target = _resolve(path)
    except ValueError as exc:
        return f"[错误] {exc}"
    if not target.exists():
        return f"[错误] 路径不存在: {path}"
    if target.is_file():
        return f"[错误] {path} 是文件而不是目录，请用 read_file"
    entries = []
    for item in sorted(target.iterdir()):
        if item.name.startswith(".") or item.name == "__pycache__":
            continue
        if item.is_dir():
            entries.append(f"{item.name}/")
        else:
            entries.append(f"{item.name}  ({item.stat().st_size} bytes)")
    return "\n".join(entries) or "(空目录)"


def read_file(path: str, start_line: int = 1, max_lines: int = 300) -> str:
    """按行号读取文件内容，便于精确引用行号。"""
    try:
        target = _resolve(path)
    except ValueError as exc:
        return f"[错误] {exc}"
    if not target.is_file():
        return f"[错误] 文件不存在: {path}"
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"[错误] 读取失败: {exc}"

    start = max(1, int(start_line))
    total = len(lines)
    end = min(total, start - 1 + max(1, int(max_lines)))
    body = "\n".join(f"{i:>4} | {lines[i - 1]}" for i in range(start, end + 1))
    if end < total:
        body += f"\n...文件共 {total} 行，已读到第 {end} 行"
    return _clip(body)


def search_code(pattern: str, path: str = ".", max_results: int = 40) -> str:
    """用正则表达式在工作区的代码文件中搜索。"""
    try:
        regex = re.compile(pattern)
        target = _resolve(path)
    except (re.error, ValueError) as exc:
        return f"[错误] 参数无效: {exc}"

    files = [target] if target.is_file() else sorted(target.rglob("*.py"))
    hits: list[str] = []
    for file in files:
        try:
            content = file.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(content, 1):
            if regex.search(line):
                rel = file.relative_to(WORKSPACE) if file != WORKSPACE else file.name
                hits.append(f"{rel}:{lineno}: {line.strip()[:160]}")
                if len(hits) >= max_results:
                    return _clip("\n".join(hits) + "\n...(结果已截断)")
    return "\n".join(hits) if hits else "(无匹配结果)"


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """在子进程中执行一段 Python 代码并返回 stdout/stderr，用于验证猜想。"""
    import shutil

    tmp_dir = tempfile.mkdtemp(prefix="agent_run_")
    script = Path(tmp_dir) / "snippet.py"
    script.write_text(code, encoding="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=int(timeout),
            cwd=str(WORKSPACE),
        )
    except subprocess.TimeoutExpired:
        return f"[错误] 执行超时（超过 {timeout}s），可能存在死循环"
    except OSError as exc:
        return f"[错误] 无法启动解释器: {exc}"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    parts = [f"exit_code={proc.returncode}"]
    if proc.stdout.strip():
        parts.append(f"stdout:\n{proc.stdout.strip()}")
    if proc.stderr.strip():
        parts.append(f"stderr:\n{proc.stderr.strip()}")
    return _clip("\n".join(parts))


# --------------------------- 工具注册表 ---------------------------

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "列出目录内容，用于了解项目结构。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对工作区的目录路径，默认 '.'"}},
            "required": []}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取文件内容，返回带行号的文本，便于精确引用行号。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对工作区的文件路径"},
            "start_line": {"type": "integer", "description": "起始行，默认 1"},
            "max_lines": {"type": "integer", "description": "最多读取行数，默认 300"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search_code",
        "description": "用正则表达式在代码文件中搜索，用于定位某种写法。",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string", "description": "Python 正则表达式"},
            "path": {"type": "string", "description": "搜索范围，默认整个工作区"}},
            "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "run_python",
        "description": "执行一段 Python 代码并返回输出，用于验证 Bug 猜想。",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "完整可独立运行的 Python 代码"},
            "timeout": {"type": "integer", "description": "超时秒数，默认 15"}},
            "required": ["code"]}}},
]

TOOL_REGISTRY = {
    "list_dir": list_dir,
    "read_file": read_file,
    "search_code": search_code,
    "run_python": run_python,
}


def call(name: str, args: dict) -> str:
    """统一的工具调用入口，保证任何异常都不会中断 Agent 循环。"""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return f"[错误] 未知工具: {name}，可用工具: {list(TOOL_REGISTRY)}"
    if not isinstance(args, dict):
        return "[错误] 工具参数必须是 JSON 对象"
    try:
        return func(**args)
    except TypeError as exc:
        return f"[错误] 参数不匹配: {exc}"
    except Exception as exc:  # noqa: BLE001 —— 兜底，避免单次工具失败终止整个流程
        return f"[错误] 工具执行异常: {type(exc).__name__}: {exc}"
