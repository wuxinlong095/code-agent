"""工具层单元测试：python -m pytest -q"""
import pytest

from code_agent import tools


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path.resolve())
    (tmp_path / "sample.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return tmp_path


def test_read_file_with_line_numbers():
    out = tools.read_file("sample.py")
    assert "1 | def add(a, b):" in out


def test_read_missing_file_returns_error_string():
    assert tools.read_file("nope.py").startswith("[错误]")


def test_path_traversal_is_blocked():
    assert tools.read_file("../../etc/passwd").startswith("[错误]")


def test_search_code_finds_match():
    assert "sample.py:2" in tools.search_code(r"return a \+ b")


def test_search_invalid_regex():
    assert tools.search_code("([").startswith("[错误]")


def test_run_python_success_and_failure():
    assert "exit_code=0" in tools.run_python("print(1 + 1)")
    failed = tools.run_python("raise ValueError('boom')")
    assert "exit_code=1" in failed and "boom" in failed


def test_run_python_timeout():
    assert "超时" in tools.run_python("while True: pass", timeout=2)


def test_unknown_tool_returns_error():
    assert tools.call("not_a_tool", {}).startswith("[错误]")
