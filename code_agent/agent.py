"""Agent 核心循环：输入 → 推理 → 工具调用 → 观察 → 输出。

包含三项工程能力：多步工具循环、LLM 调用失败重试、跨轮上下文记忆。
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

from . import config, prompts, tools


class CodeAgent:
    def __init__(self, model: str | None = None, max_steps: int | None = None,
                 verbose: bool = True) -> None:
        if not config.API_KEY:
            raise RuntimeError(
                "未检测到 API Key。请在 .env 中设置 LLM_API_KEY（可参考 .env.example）"
            )
        self.client = OpenAI(api_key=config.API_KEY, base_url=config.BASE_URL)
        self.model = model or config.MODEL
        self.max_steps = max_steps or config.MAX_STEPS
        self.verbose = verbose
        # 上下文记忆：messages 在整个会话中累积，支持多轮追问
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT}
        ]
        self.trace: list[dict[str, Any]] = []

    # ---------------- 底层调用：带指数退避的重试 ----------------
    def _chat(self) -> Any:
        delay = 1.0
        last_error: Exception | None = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=tools.TOOL_SCHEMAS,
                    tool_choice="auto",
                    temperature=config.TEMPERATURE,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == config.MAX_RETRIES:
                    break
                self._log(f"[warn] LLM 调用失败({type(exc).__name__}: {exc})，"
                          f"{delay:.0f}s 后重试（第 {attempt}/{config.MAX_RETRIES} 次）")
                time.sleep(delay)
                delay *= 2
        raise RuntimeError(f"LLM 调用连续失败 {config.MAX_RETRIES} 次: {last_error}")

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    @staticmethod
    def _to_assistant_message(message: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments or "{}",
                    },
                }
                for call in message.tool_calls
            ]
        return payload

    # ---------------- 主循环 ----------------
    def ask(self, user_input: str) -> str:
        """执行一轮完整问答（内部可能包含多次工具调用）。"""
        self.messages.append({"role": "user", "content": user_input})
        for step in range(1, self.max_steps + 1):
            response = self._chat()
            message = response.choices[0].message
            self.messages.append(self._to_assistant_message(message))

            if not message.tool_calls:
                answer = message.content or ""
                self._log(f"\n=== 第 {step} 步：产出最终结论 ===\n")
                return answer

            for call in message.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as exc:
                    args, result = {}, f"[错误] 工具参数不是合法 JSON: {exc}"
                else:
                    result = tools.call(name, args)

                brief = json.dumps(args, ensure_ascii=False)[:120]
                self._log(f"[step {step}] 调用工具 {name}({brief})")
                self._log(f"          → {result.splitlines()[0][:120] if result else '(空结果)'}")

                self.trace.append({
                    "step": step, "tool": name, "args": args,
                    "result_preview": result[:500],
                })
                self.messages.append({
                    "role": "tool", "tool_call_id": call.id, "content": result,
                })

        self._log("[warn] 已达到最大步数限制")
        return "（已达到最大步数限制，未能给出最终结论，请提高 AGENT_MAX_STEPS 或缩小审查范围）"

    def review(self, target: str, focus: str = "Bug、边界情况、代码质量、安全隐患") -> str:
        """面向代码审查场景的语义化封装。"""
        return self.ask(prompts.REVIEW_TEMPLATE.format(target=target, focus=focus))

    def reset(self) -> None:
        """清空上下文，开启新会话。"""
        self.messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]
        self.trace.clear()

    def save_trace(self, path: str = "reports/last_run.json") -> str:
        """把工具调用轨迹落盘，方便复盘与答辩举证。"""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model": self.model,
            "message_count": len(self.messages),
            "trace": self.trace,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output)
