# Code Review Agent（HW1）

一个基于 LLM 原生 API 的多工具代码审查 Agent：自动读取代码、验证 Bug 猜想、输出结构化审查报告。

## 功能
- Agent 循环：输入 → 推理 → 工具调用 → 观察 → 输出，单轮最多 8 步，可配置
- 4 个工具：`list_dir`、`read_file`、`search_code`（正则）、`run_python`（受控执行）
- 上下文记忆：同一会话内支持多轮追问
- 错误处理：工具异常不中断循环；LLM 调用指数退避重试 3 次；路径越界、超时、非法正则均返回可读错误
- 轨迹落盘：每次运行的工具调用记录保存到 `reports/last_run.json`

## 快速开始
```bash
git clone https://github.com/wuxinlong095/code-agent.git
cd code-agent
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # 填入 LLM_API_KEY
python main.py examples/buggy_sample.py
