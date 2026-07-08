# StockAgent 多 Agent 股票分析系统 - 现状与开发计划

> 最后核对：2026-07-08，基于当前工作树实际代码。

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

截至 2026-07-08，默认 Agent 报告路径、LLM/Tavily 前置配置校验、流程日志、subagent 进度回调和 Markdown 报告写入已经落地。下一步重点不再是重搭架构，而是收口伪支持能力、补齐估值确定性计算、扩大 Agent 路径测试，并继续提高 CLI 运行过程的可观察性。

当前默认路径是：

- CLI 输入 ticker。
- `cli.py` 初始化日志并加载应用配置。
- `app.py` 加载 LLM 配置并调用 orchestrator。
- orchestrator 协调 4 个 subagent 完成行业、基本面、估值、风险分析，并通过 callback 输出 subagent / tool 进度日志。
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
│   - callback 进度日志           │
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
| Observability | `observability.py` | CLI 日志初始化、阶段日志、失败日志 | 已实现 |
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
├── observability.py
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

测试文件当前共 16 个测试模块：

- `tests/test_cli.py`
- `tests/test_app.py`
- `tests/test_config.py`
- `tests/test_agent_errors.py`
- `tests/test_financial_tools.py`
- `tests/test_observability.py`
- `tests/test_orchestrator_logging.py`
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
  -> parse_args()
  -> setup_logging(options.log_level)
  -> load_app_config()
  -> app.run_stock_analysis(options, config)
      -> load_llm_config()
      -> orchestrator.run_stock_analysis_agent(ticker, years, llm_config)
          -> create_stock_analysis_agent(llm_config)
              -> apply_llm_environment(llm_config)
              -> _build_model(llm_config)
              -> create_deep_agent(model, tools, system_prompt, subagents)
          -> agent.invoke(messages, callbacks=[_AgentProgressCallbackHandler])
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
- 通过 `_AgentProgressCallbackHandler` 记录 subagent 启动、完成、工具调用和工具失败。
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

### 6.4 日志与可观察性

当前已实现的日志边界：

- `cli.py`：初始化运行环境、应用配置加载完成、主流程完成、失败输出。
- `app.py`：LLM 配置加载、主 agent 启动/完成、报告写入开始。
- `agents/orchestrator.py`：subagent 启动/完成、业务工具调用/返回、agent 汇总报告。
- `report/writer.py`：Markdown 报告写入开始/完成。

当前限制：

- callback 目前只把 `get_full_analysis` 和 `web_search` 识别为业务工具；基本面 subagent 内部的 `fetch_company_financials`、`compute_*` 调用还没有完整纳入进度日志。
- 仍使用 `agent.invoke()`，不是 DeepAgents / LangGraph 的 stream 事件流；因此当前日志是阶段级，而不是 token 或节点级追踪。

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
- `TAVILY_API_KEY` 是默认 Agent 路径和 `web_search` 的必填项。

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
| `observability.py` | 已完成 | 已有 CLI 日志初始化和阶段日志辅助函数 |
| `report/writer.py` | 部分完成 | Markdown 已完成，HTML/PDF 未完成 |
| `fundamentals/valuation.py` | 未完成 | 文件存在但为空 |
| `docs/valuation.md` | 草案 | 已有估值方案 A，但尚未实现到代码 |

## 9. 当前已知问题

### 9.1 高优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| Anthropic builder 未实现 | `agents/orchestrator.py` | `anthropic:*` provider 入口存在，但 `build_anthropic_model()` 为空 |
| 缺少 `langchain-anthropic` 依赖 | `pyproject.toml` | 即使补代码，当前依赖也不完整 |
| CLI 暴露了未实现的报告格式 | `cli.py` / `report/writer.py` | `html`、`pdf` 可被选择，但运行时会抛 `NotImplementedError` |
| 估值路径缺确定性计算 | `fundamentals/valuation.py` / `valuation_agent.py` | 估值仍主要依赖 LLM 文本推理，缺少 PE/PB/PS 等可验证指标 |

### 9.2 中优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| 估值缺实时市场数据 | `valuation_agent.py` | 无法直接获取股价、市值、PE/PB/PS 实时口径 |
| Agent 路径集成测试仍不足 | `tests/` | 已有日志和错误分类测试，但还缺 mock LLM + mock EDGAR + 报告写入的完整流程测试 |
| subagent 工具日志覆盖不完整 | `agents/orchestrator.py` | 当前只覆盖 `get_full_analysis` 和 `web_search`，未覆盖全部 financial tools |
| `app.py` 与 `api.py` 存在部分重复确定性逻辑 | `app.py` / `api.py` | 后续可适度收敛，但不能破坏 fallback |

### 9.3 低优先级

| 问题 | 位置 | 说明 |
|---|---|---|
| `yfinance` 遗留依赖 | `pyproject.toml` | 当前代码未使用 |
| LLM 调用缺少重试机制 | `agents/orchestrator.py` | 当前主要是分类错误后抛出 |

## 10. 后续开发计划

### 第一阶段：收口运行时能力面

目标：先消除“用户能选但实际不可用”的路径，让默认运行体验稳定。

1. 对 `anthropic:` 做明确选择：
   - 要么补齐 `build_anthropic_model()` 和依赖。
   - 要么暂时移除该入口，避免伪支持。
2. 对 `--report-format html/pdf` 做明确选择：
   - 若短期不做，先从 CLI choices 中移除，只保留 `md`。
   - 若要保留参数，则补齐 writer、测试和依赖。
3. 保持 `DEFAULT_LLM_MODEL` 作为模型默认值唯一来源，后续文档、`.env.example`、测试都不要重复硬编码不同默认值。

验收标准：

- 不存在可通过 CLI 选择但运行到中途才发现未实现的功能。
- `_build_model()`、`write_report()`、`load_llm_config()` 的失败路径都有明确测试。

### 第二阶段：补齐日志与 Agent 稳定性

目标：让 `uv run stock TICKER` 的执行过程对用户可见，并让后续新增模块能复用同一套日志边界。

1. 扩展 `_AgentProgressCallbackHandler` 的业务工具识别范围，覆盖：
   - `fetch_company_financials`
   - `compute_profitability_metrics`
   - `compute_growth_metrics`
   - `compute_cash_flow_metrics`
   - `compute_financial_health_metrics`
   - 后续新增的 `compute_valuation_metrics`
2. 为 `extract_final_report()` 增加更多返回结构测试。
3. 增加至少一条“mock LLM + mock EDGAR + mock Tavily + 生成报告文件”的集成测试。
4. 后续如需要更细粒度进度，再评估从 `invoke()` 升级为 `stream()` / `astream_events()`。

验收标准：

- 用户能从日志看到主流程、subagent、关键工具、报告写入的进度。
- Agent 主路径有一条不访问真实外部服务的完整流程测试。

### 第三阶段：增强估值能力

目标：把估值从“LLM 文字判断”推进到“市场数据 + 确定性倍数计算 + LLM 解读”。

现有草案：`docs/valuation.md` 已提出方案 A：通过 Tavily 搜索股价/市值，再用最新财年数据确定性计算 trailing 估值倍数。

建议按草案分小步落地：

1. 在 `financials/models.py` 增加 `ValuationMetrics`。
2. 在 `fundamentals/inputs.py` 增加 `ValuationInput` 和构造函数。
3. 实现 `fundamentals/valuation.py`：
   - PE
   - PB
   - PS
   - EV
   - EV/EBITDA
   - earnings yield
   - FCF yield
   - dividend yield
4. 在 `api.py` 增加 `compute_valuation()`。
5. 在 `tools/financials.py` 增加 `compute_valuation_metrics()`。
6. 更新 `valuation_agent.py`：
   - 加入 `web_search`
   - 加入 `compute_valuation_metrics`
   - 删除“当前工具没有实时股价”的限制描述
7. 增加 valuation 单元测试和 tool JSON 输出测试。

首批字段建议只做：

- 最新价格
- 市值
- PE / PB / PS
- 数据时间戳

验收标准：

- 不访问 LLM 也能对给定 price / market_cap 和财报记录计算估值指标。
- Agent 可以把搜索到的市场数据传入确定性 tool，而不是让 LLM 自己算倍数。

### 第四阶段：继续收敛边界和文档

1. 保持 `cli.py` 薄。
2. 保持 `app.py` 为运行时编排层。
3. 把新增确定性业务能力继续集中到 `api.py` 和 `fundamentals/*`。
4. 不新增平行 runner、adapter 或 integration 目录。
5. 根据实现进度同步 `README.md`、`.env.example` 和本文档。
6. 清理确认未使用的依赖，例如 `yfinance`。

## 11. 当前设计约束

后续继续开发时，默认遵守以下约束：

- 以当前代码为准，不按旧设计稿重搭目录。
- 保留确定性 fallback。
- 新增 Agent 能力优先从 `api.py -> tools/ -> agents/` 进入系统。
- 优先做小步、可验证、可测试的增量修改。
- 对文档里的“执行顺序”和“能力范围”要区分“当前已实现”和“当前目标约定”。
