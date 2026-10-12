"""集中管理配置：全部通过环境变量注入，避免硬编码密钥。"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# 兼容 OpenAI / Claude 网关 / 通义千问(DashScope 兼容模式) / DeepSeek 等任何 OpenAI 兼容接口
API_KEY: str = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

MAX_STEPS: int = int(os.getenv("AGENT_MAX_STEPS", "8"))     # Agent 最大循环步数
MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))   # LLM 调用重试次数
TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))
