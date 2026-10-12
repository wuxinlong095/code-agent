"""命令行入口。

用法示例：
    python main.py examples/buggy_sample.py
    python main.py code_agent -q "重点检查异常处理是否完整"
"""
from __future__ import annotations

import argparse
import sys

from code_agent import CodeAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code-agent",
        description="代码审查 Agent：读取代码 → 验证猜想 → 输出结构化审查报告",
    )
    parser.add_argument("target", help="要审查的文件或目录路径（相对工作区）")
    parser.add_argument("-q", "--question", default=None, help="自定义审查问题")
    parser.add_argument("--model", default=None, help="覆盖默认模型，如 deepseek-chat")
    parser.add_argument("--max-steps", type=int, default=None, help="Agent 最大循环步数")
    parser.add_argument("--quiet", action="store_true", help="只输出最终报告")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        agent = CodeAgent(model=args.model, max_steps=args.max_steps,
                          verbose=not args.quiet)
    except RuntimeError as exc:
        print(f"[启动失败] {exc}", file=sys.stderr)
        return 2

    if args.question:
        result = agent.ask(f"目标：{args.target}\n\n用户问题：{args.question}")
    else:
        result = agent.review(args.target)

    print("\n" + "=" * 60 + "\n审查报告\n" + "=" * 60)
    print(result)
    print(f"\n[轨迹已保存] {agent.save_trace()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
