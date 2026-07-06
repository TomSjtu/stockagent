# StockAgent 多 Agent 股票分析系统 — 现状与待办

> 最后核对：2026-07-06，基于当前工作树实际代码。

## 1. 文档定位

本文档以当前分支代码为准，用来回答三个问题：

- `stockagent` 现在实际是怎么跑起来的。
- 哪些能力已经落地，哪些只是保留入口或半成品。
- 后续应该沿着什么边界继续演进。

如果本文档与代码冲突，以当前实现为准，优先检查：

- `src/stockagent/api.py`
- `src/stockagent/app.py`
- `src/stockagent/cli.py`
- `src/stockagent/agents/*.py`
- `src/stockagent/tools/*.py`
- `src/stockagent/config.py`

## 2. 项目概述

`stockagent` 当前是一套基于 DeepAgents 编排、以 EDGAR 财务数据为底座、以 Tavily 作为行业搜索补充的多 Agent 股票分析系统。

当前默认路径是：

- CLI 输入 ticker。
- `app.py` 加载 LLM 配置并调用 orchestrator。
- orchestrator 协调 4 个 subagent 完成行业、基本面、估值、风险分析。
- 最终由 LLM 输出中文 Markdown 报告，并通过 `report.writer` 写入文件。

同时，项目仍然保留一条确定性 fallback 路径，用于兼容和测试：

- 直接抓取 EDGAR 数据。
- 计算 profitability / growth / cash flow / financial health 指标。
- 返回 `AnalysisResult`，不经过 LLM。

## 3. 整体架构

```text
用户输入 (ticker)
      │
      ▼
┌─────────────────────────────────┐
│   CLI (cli.py)                  │
│   parse_args -> run_stock_analysis
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   app.py                        │
│   run_stock_analysis()          │
│   - load_llm_config()           │
│   - 调 orchestrator             │
│   - write_report()              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Orchestrator Agent            │
│   agents/orchestrator.py        │
│   - write_todos                 │
│   - task/subagent 调度          │
│   - 汇总 final_report.md        │
└────┬───────┬───────┬───────┬────┘
     │       │       │       │
     ▼       ▼       ▼       ▼
┌────────┐┌────────┐┌────────┐┌──────────┐
│行业分析 ││基本面   ││估值分析 ││ 风险评估  │
│SubAgent││SubAgent││SubAgent││ SubAgent │
└────────┘└────────┘└────────┘└──────────┘
     │       │       │       │
     ▼       ▼       ▼       ▼
  ┌──────────────────────────────┐
  │ Tools Layer                  │
  │ tools/financials.py          │
  │ tools/search.py              │
  └──────────────┬───────────────┘
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
┌──────────────┐       ┌──────────────┐
│ api.py       │       │ Tavily       │
│ EDGAR +      │       │ Web Search   │
│ fundamentals │       │              │
└──────┬───────┘       └──────────────┘
       │
       ▼
┌──────────────┐
│ EDGAR / SEC  │
│ 财务数据      │
└──────────────┘
```

### 分层职责

| 层 | 文件 | 职责 | 当前状态 |
|---|---|---|---|
| CLI | `cli.py` | 参数解析、调用 app 层、统一错误输出 | 已实现 |
| App | `app.py` | 默认 Agent 入口和确定性 fallback 编排 | 已实现 |
| API | `api.py` | 纯业务能力、ticker 标准化、缓存、指标计算入口 | 已实现 |
| Tools | `tools/` | 把 Python 对象包装成 LLM 可消费的 JSON 字符串 | 已实现 |
| Agents | `agents/` | prompt、tools、subagent 编排 | 已实现 |
| Fundamentals | `fundamentals/` | 纯指标计算 | 大部分已实现 |
| Data | `data/providers/` | 外部财务数据抓取 | 已实现 |
| Report | `report/` | 报告文件输出 | Markdown 已实现，HTML/PDF 未实现 |

## 4. 当前目录结构

```text
src/stockagent/
├── __init__.py
├── api.py
├── app.py
├── cli.py
├── config.py
├── errors.py
├── agents/
│   ├── __init__.py
│   ├── errors.py
│   ├── orchestrator.py
│   ├── industry_agent.py
│   ├── fundamentals_agent.py
│   ├── valuation_agent.py
│   └── risk_agent.py
├── tools/
│   ├── __init__.py
│   ├── financials.py
│   └── search.py
├── fundamentals/
│   ├── __init__.py
│   ├── inputs.py
│   ├── profitability.py
│   ├── growth.py
│   ├── cash_flow.py
│   ├── financial_health.py
│   └── valuation.py
├── financials/
│   ├── __init__.py
│   └── models.py
├── data/
│   ├── __init__.py
│   ├── errors.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       └── edgar.py
└── report/
    ├── __init__.py
    ├── builder.py
    ├── generator.py
    └── writer.py
```

测试文件当前共 14 个测试模块：

- `tests/test_cli.py`
- `tests/test_app.py`
- `tests/test_config.py`
- `tests/test_agent_errors.py`
- `tests/test_financial_tools.py`
- `tests/test_search_tool.py`
- `tests/data/providers/test_edgar.py`
- `tests/fundamentals/test_cash_flow.py`
- `tests/fundamentals/test_financial_health.py`
- `tests/fundamentals/test_growth.py`
- `tests/fundamentals/test_profitability.py`
- `tests/report/test_builder.py`
- `tests/report/test_generator.py`
- `tests/report/test_writer.py`

补充说明：

- `fundamentals/valuation.py` 文件存在，但当前仍为空文件。

## 5. 核心运行路径

### 5.1 默认 CLI -> Agent -> Report 路径

```text
cli.main()
  -> load_app_config()
  -> parse_args()
  -> app.run_stock_analysis(options, config)
      -> load_llm_config()
      -> orchestrator.run_stock_analysis_agent(ticker, years, llm_config)
          -> create_stock_analysis_agent(llm_config)
              -> apply_llm_environment(llm_config)
              -> _build_model(llm_config)
              -> create_deep_agent(model, tools, system_prompt, subagents)
          -> agent.invoke(messages)
          -> extract_final_report(result)
      -> report.writer.write_report(ticker, report, format, output_dir)
```

这条路径是当前默认入口，不需要额外 `--mode` 或 `--deep` 开关。

### 5.2 确定性 fallback 路径

```text
app.run_sec_fundamentals_analysis()
  -> provider.fetch_annual_records()
  -> compute_profitability_series()
  -> compute_growth_series()
  -> compute_cash_flow_series()
  -> compute_financial_health_series()
  -> AnalysisResult
```

这条路径目前仍然有价值：

- 用于保留纯数据分析能力。
- 用于测试注入和更可控的验证。
- 用于后续 Agent 输出的对照基线。

### 5.3 数据缓存策略

`api.fetch_financials()` 使用 `lru_cache`，按 `ticker.upper()` 和 `years` 维度缓存。

典型效果：

```text
fundamentals agent 调用 compute_profitability_metrics("AAPL", 3)
  -> api.fetch_financials("AAPL", 3) 首次抓取

valuation agent 调用 fetch_company_financials("AAPL", 3)
  -> api.fetch_financials("AAPL", 3) 直接命中缓存
```

## 6. Agent 与 Tool 现状

### 6.1 Orchestrator

文件：`src/stockagent/agents/orchestrator.py`

当前职责：

- 构建主 DeepAgent。
- 提供总控 prompt。
- 挂载两个顶层工具：`get_full_analysis`、`web_search`。
- 注册 4 个 subagent。
- 从 `files["final_report.md"]` 或最后一条消息中提取最终报告。

当前 prompt 约定的执行顺序是：

```text
1. industry_analyst
2. fundamentals_analyst
3. valuation_analyst
4. risk_analyst
5. orchestrator 汇总 final_report.md
```

这里要注意：

- 这是 prompt 约束和 DeepAgents 工作流约定，不是单独实现了一层严格调度器。
- 文档里可以写“目标顺序”或“约定顺序”，但不应写成底层代码显式实现了并行调度框架。

### 6.2 SubAgent 详情

| Agent | 文件 | 当前可用 Tools | 依赖文件 | 输出文件 |
|---|---|---|---|---|
| Orchestrator | `orchestrator.py` | `get_full_analysis`, `web_search` | 四份分析文件 | `final_report.md` |
| 行业分析 | `industry_agent.py` | `web_search` | 无 | `industry_analysis.md` |
| 基本面 | `fundamentals_agent.py` | `fetch_company_financials`, `compute_profitability_metrics`, `compute_growth_metrics`, `compute_cash_flow_metrics`, `compute_financial_health_metrics` | 无 | `fundamentals_analysis.md` |
| 估值分析 | `valuation_agent.py` | `fetch_company_financials` | `industry_analysis.md`, `fundamentals_analysis.md` | `valuation_analysis.md` |
| 风险评估 | `risk_agent.py` | `fetch_company_financials`, `compute_financial_health_metrics` | `industry_analysis.md`, `fundamentals_analysis.md`, `valuation_analysis.md` | `risk_analysis.md` |

### 6.3 Tool 设计边界

`tools/financials.py` 当前暴露 6 个财务相关工具：

- `fetch_company_financials`
- `compute_profitability_metrics`
- `compute_growth_metrics`
- `compute_cash_flow_metrics`
- `compute_financial_health_metrics`
- `get_full_analysis`

`tools/search.py` 当前暴露：

- `web_search`

当前边界是清晰的：

- `api.py` 返回 Python 对象。
- `tools/*` 负责序列化为 JSON 字符串。
- `agents/*` 只负责 prompt 和工具编排。

## 7. 配置与依赖

### 7.1 当前环境变量

```env
LLM_API_KEY=sk-...
LLM_BASE_URL=
LLM_MODEL=openai:gpt-5.5
STOCKAGENT_EDGAR_IDENTITY=Your Name your.email@example.com
TAVILY_API_KEY=tvly-...
```

说明：

- `LLM_API_KEY` 是默认 Agent 路径的必填项。
- `LLM_MODEL` 当前默认值是 `openai:gpt-5.5`。
- `STOCKAGENT_EDGAR_IDENTITY` 在代码中有默认兜底值，但生产使用仍应显式配置。
- `TAVILY_API_KEY` 是 `web_search` 的必填项。

### 7.2 模型构建

`orchestrator._build_model()` 目前按 `provider:model_name` 格式分发：

- `openai:*` -> `langchain_openai.ChatOpenAI`
- `anthropic:*` -> 预留 builder 入口，但实现仍为空

OpenAI 分支当前还有一条额外逻辑：

- 当 `base_url` 为空或指向原生 OpenAI 域名时，会启用 `use_responses_api=True`。

### 7.3 当前依赖

`pyproject.toml` 当前包含：

- `yfinance>=0.2`
- `openai>=1.0`
- `python-dotenv>=1.0`
- `curl_cffi>=0.15`
- `edgartools>=5.35.1`
- `deepagents>=0.6`
- `tavily-python>=0.5`
- `langchain-openai>=1.3.3`

当前尚未包含：

- `langchain-anthropic`

## 8. 已完成能力

| 模块 | 状态 | 说明 |
|---|---|---|
| `api.py` | 已完成 | 已有 fetch / compute / analyze 主链路和缓存 |
| `tools/financials.py` | 已完成 | 已有 6 个财务工具 |
| `tools/search.py` | 已完成 | 已有 Tavily 搜索工具 |
| `config.py` | 已完成 | 已支持 `.env` 加载和 `LLM_MODEL` 配置 |
| `agents/*.py` | 已完成 | 已有 orchestrator 和 4 个 subagent |
| `cli.py` | 已完成 | 默认走 Agent 路径 |
| `report/writer.py` | 部分完成 | Markdown 已完成，HTML/PDF 未完成 |
| `fundamentals/valuation.py` | 未完成 | 文件存在但为空 |

## 9. 当前已知问题

### 9.1 高优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| Anthropic builder 未实现 | `agents/orchestrator.py` | `anthropic:*` provider 入口存在，但 `build_anthropic_model()` 为空 |
| 缺少 `langchain-anthropic` 依赖 | `pyproject.toml` | 即使补代码，当前依赖也不完整 |
| 默认 Agent 路径的前置配置校验仍偏弱 | `config.py` / `tools/search.py` | `LLM_API_KEY`、`TAVILY_API_KEY` 缺失时分别在不同层报错，体验不统一 |

### 9.2 中优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| `fundamentals/valuation.py` 空文件 | `fundamentals/valuation.py` | 估值仍主要依赖 LLM 文本推理 |
| 估值缺实时市场数据 | `valuation_agent.py` | 无法直接获取股价、市值、PE/PB/PS 实时口径 |
| 缺少 Agent 路径集成测试 | `tests/` | 现有测试偏单元测试，缺完整流程 mock |
| `app.py` 与 `api.py` 存在部分重复确定性逻辑 | `app.py` / `api.py` | 后续可适度收敛，但不能破坏 fallback |

### 9.3 低优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| `yfinance` 遗留依赖 | `pyproject.toml` | 当前代码未使用 |
| HTML/PDF 报告未实现 | `report/writer.py` | 相关分支目前抛 `NotImplementedError` |
| LLM 调用缺少重试机制 | `agents/orchestrator.py` | 当前主要是分类错误后抛出 |

## 10. 推荐的后续推进顺序

### 第一阶段：统一运行时一致性

1. 统一默认模型值、`.env.example`、测试和文档口径。
2. 对 `anthropic:` 做明确选择：
   - 要么补齐 `build_anthropic_model()` 和依赖。
   - 要么暂时移除该入口，避免伪支持。
3. 增加默认 Agent 路径的配置预检，让缺失配置时更早失败。

### 第二阶段：补测试和稳定性

1. 为 `extract_final_report()` 增加更多返回结构测试。
2. 为 `_build_model()` 增加 provider 分支测试。
3. 增加至少一条“mock LLM + mock EDGAR + 生成报告文件”的集成测试。

### 第三阶段：增强估值能力

1. 先引入最小市场数据 tool，不要一开始扩成完整行情层。
2. 首批字段建议只做：
   - 最新价格
   - 市值
   - PE / PB / PS
   - 数据时间戳
3. 有了市场数据后，再升级估值 agent prompt。

### 第四阶段：继续收敛边界

1. 保持 `cli.py` 薄。
2. 保持 `app.py` 为运行时编排层。
3. 把新增确定性业务能力继续集中到 `api.py` 和 `fundamentals/*`。
4. 不新增平行 runner、adapter 或 integration 目录。

## 11. 当前设计约束

后续继续开发时，默认遵守以下约束：

- 以当前代码为准，不按旧设计稿重搭目录。
- 保留确定性 fallback。
- 新增 Agent 能力优先从 `api.py -> tools/ -> agents/` 进入系统。
- 优先做小步、可验证、可测试的增量修改。
- 对文档里的“执行顺序”和“能力范围”要区分“当前已实现”和“当前目标约定”。
