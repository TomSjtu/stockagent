# stockagent

`stockagent` 是一个面向美股的命令行股票分析工具。当前默认流程会用 DeepAgents 编排多个分析子 Agent，结合 SEC EDGAR 财务数据、Tavily 搜索结果和 LLM，生成中文 Markdown 股票研究报告。

> 生成内容仅用于研究和学习，不构成投资建议。

## 功能概览

- 拉取 SEC EDGAR 年度财务数据，并标准化为项目内部的财务记录。
- 计算盈利能力、现金流、财务健康度、成长性等基本面指标。
- 基于最新财年数据和外部市场输入，确定性计算 trailing PE / PB / PS。
- 通过 DeepAgents 编排行业、基本面、估值、风险四类子 Agent。
- 使用 Tavily 补充行业趋势、公司动态和市场信息。
- 输出中文 Markdown 报告，并在 CLI 运行过程中打印关键阶段日志。

## 环境要求

- Python 3.11+
- 推荐使用 `uv`

## 安装

```bash
uv sync
```

也可以使用可编辑安装：

```bash
pip install -e .
```

## 配置

复制环境变量示例文件：

```bash
cp .env.example .env
```

填写 `.env`：

```bash
# LLM configuration
LLM_API_KEY=sk-...
LLM_BASE_URL=
LLM_MODEL=openai:gpt-5.5

# Data providers
STOCKAGENT_EDGAR_IDENTITY=Your Name your.email@example.com
TAVILY_API_KEY=tvly-...
```

变量说明：

- `LLM_API_KEY`：必填，默认 Agent 报告流程。
- `LLM_BASE_URL`：可选，用于 OpenAI 兼容接口。
- `LLM_MODEL`：必填，模型名必须包含 provider 前缀，默认是 `openai:gpt-5.5`。
- `TAVILY_API_KEY`：必填，默认 Agent 报告流程，用于网页搜索工具。
- `STOCKAGENT_EDGAR_IDENTITY`：EDGAR 请求身份标识；代码有默认值，但实际使用建议显式配置。

当前已实现的模型构建路径是 OpenAI 兼容模型。`anthropic:` provider 的环境变量映射已预留，但模型构建函数尚未完成。

## 运行

```bash
uv run stock AAPL
```

常用参数：

```bash
uv run stock AAPL --years 5 --output-dir output --log-level info
```

参数说明：

- `ticker`：必填，美股 ticker，例如 `AAPL`。
- `--years`：分析最近几个财年，默认 `3`。
- `--output-dir`：报告输出目录，默认是当前目录下的 `output/`。
- `--log-level`：日志级别，可选 `debug`、`info`、`warning`、`error`，默认 `info`。

报告文件名格式：

```text
output/AAPL-YYYY-MM-DD.md
```

补充说明：

- 当前 CLI 默认只暴露 Agent 报告路径。
- 代码中仍保留 `app.run_sec_fundamentals_analysis()` 这条确定性 fallback 路径，主要用于测试、基线对照和后续模式切换。
- 报告文件会写入 `output/`，写入路径通过日志输出。

## 当前执行链路

```text
stockagent.cli:main
  -> load_app_config()
  -> app.run_stock_analysis()
  -> load_llm_config()
  -> agents.orchestrator.run_stock_analysis_agent()
  -> report.writer.write_markdown_report()
```

默认分析流程中：

- `industry_analyst` 使用 `web_search` 做行业和近期信息收集。
- `fundamentals_analyst` 使用 EDGAR 财务数据和确定性指标工具做基本面分析。
- `valuation_analyst` 会结合 `web_search` 提取的市场输入，调用 `compute_valuation_metrics()` 计算 trailing PE / PB / PS。
- `risk_analyst` 会综合前序分析与财务健康指标给出风险评估。

## 项目结构

```text
src/stockagent/
  cli.py                 # CLI 参数解析和入口
  app.py                 # 应用编排入口
  config.py              # .env 和运行配置
  api.py                 # 确定性分析和 DeepAgents 工具统一接口
  agents/                # DeepAgents 主编排和分析子 Agent
  tools/                 # Agent 可调用工具
  data/providers/        # EDGAR 数据提供方
  fundamentals/          # 基本面指标计算
  financials/models.py   # 财务数据模型
  report/                # 报告生成和写入
  observability.py       # 日志和流程观测
```

## 当前限制

- 当前仅完成 `openai:` provider 的模型构建；`anthropic:` 入口预留但未实现。
- 估值链路已经有 PE / PB / PS 的确定性计算，但市场输入仍来自非结构化搜索结果，可靠性依赖来源质量。
- CLI 尚未正式暴露 deterministic / agent 模式切换，确定性 fallback 目前主要通过代码入口使用。
