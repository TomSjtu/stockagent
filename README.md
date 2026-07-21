# stockagent

`stockagent` 是一个面向美股的命令行股票分析工具。当前默认流程使用 LangGraph 显式编排多个分析 Agent，结合 SEC EDGAR 财务数据、Tavily 搜索结果和 LLM，生成带可追溯来源的中文 Markdown 股票研究报告。

> 生成内容仅用于研究和学习，不构成投资建议。

## 功能概览

- 拉取 SEC EDGAR 年度财务数据，并标准化为项目内部的财务记录。
- 计算盈利能力、现金流、财务健康度、成长性等基本面指标。
- 基于最新财年数据和外部市场输入，确定性计算 trailing PE / PB / PS。
- 通过 LangGraph DAG 编排行、基本面、估值、风险四类分析 Agent。
- 使用 Tavily 补充行业趋势、公司动态和市场信息。
- 为实际采用的网页信息生成 Markdown 脚注，并为年度财务数据关联具体 SEC 年度 filing 主文档。
- 输出同名 Markdown 报告和 `sources.json` 审计附属文件，并在 CLI 运行过程中打印关键阶段日志。

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
TAVILY_API_KEY=tvly-...
```

变量说明：

- `LLM_API_KEY`：必填，默认 Agent 报告流程。
- `LLM_BASE_URL`：可选，用于 OpenAI 兼容接口。
- `LLM_MODEL`：必填，模型名必须包含 provider 前缀，默认是 `openai:gpt-5.5`。
- `TAVILY_API_KEY`：必填，默认 Agent 报告流程，用于网页搜索工具。

EDGAR 请求身份标识固定为 `stockagent stockagent@example.com`。

当前支持的模型构建路径是 OpenAI 兼容模型，`LLM_MODEL` 使用 `openai:<model-name>` 格式。

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
- `--years`：分析最近几个财年，必须是正整数，默认 `3`。请求的财年必须连续且完整；数据不足时研究会失败，不会缩短窗口。
- `--output-dir`：报告输出目录，默认是当前目录下的 `output/`。
- `--log-level`：日志级别，可选 `debug`、`info`、`warning`、`error`，默认 `info`。

每次运行会生成两个同 stem 的文件：

```text
output/AAPL-YYYY-MM-DD.md
output/AAPL-YYYY-MM-DD.sources.json
```

Markdown 中实际引用的网页和 SEC filing 会在文末“参考来源”中按首次出现顺序生成全局脚注；同一来源在多处使用时只保留一个脚注。`sources.json` 则保存本次运行全部选取的证据、实际引用 ID、用于估值计算的价格/市值输入及年度 10-K filing 元数据。它不归档原始网页全文。

同一 ticker 在同一天重复运行会覆盖该日期的两份产物。CLI 通过日志输出生成路径。

## 当前执行链路

```text
stockagent.cli:main
  -> app.run_stock_analysis()
  -> load_llm_config()
  -> agents.orchestrator.run_stock_analysis_agent()
  -> report.writer.write_report_artifacts()
```

默认分析流程中：

- `industry_analyst` 使用 `web_search` 做行业和近期信息收集。
- `fundamentals_analyst` 使用 EDGAR 财务数据和确定性指标工具做基本面分析，并保留年度 10-K 元数据。
- `valuation_analyst` 会结合 `web_search` 提取的市场输入，调用 `compute_valuation_metrics()` 计算 trailing PE / PB / PS；实际传入的价格和市值会被确定性工具结果覆盖。
- `risk_analyst` 会综合前序结构化分析并补充近期公司风险信息。
- 汇总阶段保留内部来源标记并渲染为脚注；未知标记仅记录 warning 后移除，不会让整份报告失败。

## 项目结构

```text
src/stockagent/
  cli.py                 # CLI 参数解析和入口
  app.py                 # 应用编排入口
  config.py              # .env 和运行配置
  api.py                 # 确定性分析和 Agent 工具统一接口
  agents/                # LangGraph 主编排和分析 Agent
  tools/                 # Agent 可调用工具
  data/providers/        # EDGAR 数据提供方
  fundamentals/          # 基本面指标计算
  financials/models.py   # 财务数据模型
  report/                # 报告生成和写入
  observability.py       # 日志和流程观测
```

## 当前限制

- 当前仅支持 `openai:` provider 的模型构建。
- 网页引用是尽力而为：未标记来源的 LLM 叙事仍可能出现；已选取且被引用的来源会在 Markdown 和 `sources.json` 中保持一致。
- 估值链路已经有 PE / PB / PS 的确定性计算，但市场输入仍来自非结构化搜索结果；价格、市值、币种和日期可能缺失或并非同一时点。
- 财务数据仅覆盖最近可得年度 10-K，未纳入最新 10-Q 与 TTM；P0 不提供 DCF、EV/EBITDA、可比公司表或确定性财务表渲染。
