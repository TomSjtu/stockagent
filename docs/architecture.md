# StockAgent 架构说明

> 本文描述当前 `refactor_langgraph` 分支中受版本控制的实现。它是面向维护者的架构与目录索引，不替代 [README](../README.md) 的安装和运行说明，也不把本地缓存、生成报告或未跟踪的设计草案当作正式架构的一部分。

## 1. 系统目标与边界

StockAgent 是一个面向美股的命令行研究报告生成器。一次运行会：

1. 接收股票代码和财年数；
2. 从 SEC EDGAR 获取并标准化年度财务数据；
3. 以纯 Python 计算基本面和估值指标；
4. 使用 Tavily 搜索行业、市场和近期风险信息；
5. 以 LangGraph 编排四个独立的 LLM 分析 Agent；
6. 生成中文 Markdown，并由本地文件写入器保存报告。

系统只支持 `openai:<model>` 格式的 LLM 配置。它不提供 Web 服务、数据库、长期记忆、checkpoint、异步/流式响应、质量重试或部分成功报告。

## 2. 总体架构

```text
命令行与交付层
  stock CLI
    -> cli.py -> app.py -> report/writer.py -> output/<TICKER>-<DATE>.md
                         |
                         v
编排层（agents）
  run_stock_analysis_agent()
    -> LangGraph StateGraph
       START ─┬─> industry ────────┐
              └─> fundamentals ────┴─> valuation -> risk -> synthesize -> END
                         |                |            |
                         |                |            +-> Tavily 搜索
                         |                +-> Tavily 搜索 + 确定性估值工具
                         +-> EDGAR + 确定性基本面工具

能力适配层（tools）
  web_search() -------------------------------> Tavily API
  financial tools -> api.py -> data/providers -> SEC EDGAR

领域层（financials + fundamentals）
  FinancialRecord / Metrics 数据模型
  输入投影 -> 盈利能力、现金流、健康度、成长性、估值的纯函数计算
```

### 2.1 分层职责

| 层 | 目录/模块 | 职责 | 不负责的事情 |
| --- | --- | --- | --- |
| 入口与交付 | `cli.py`、`app.py`、`report/` | 参数解析、配置加载、生命周期日志、写文件 | 财务计算、Agent 调度细节 |
| 编排 | `agents/` | LLM 构造、节点拓扑、提示词、结构化输出和失败传播 | 直接解析 EDGAR 表格、持久化报告 |
| 工具适配 | `tools/` | 将搜索和确定性计算暴露给 Agent，统一为 JSON 文本工具结果 | 业务决策和跨节点状态 |
| 应用/领域服务 | `api.py` | 取数、完整财年窗口校验、缓存、调用各指标计算 | LLM 提示词、HTTP 搜索 |
| 数据适配 | `data/` | 把外部数据源转换为内部 `FinancialRecord` | 指标计算和报告生成 |
| 领域模型与计算 | `financials/`、`fundamentals/` | 财务记录、指标 DTO 与无副作用的公式 | 网络、环境变量、LLM |
| 横切能力 | `config.py`、`errors.py`、`observability.py`、`llm.py` | 配置、错误边界、日志、模型客户端 | 业务流程编排 |
| 验证 | `tests/` | 镜像生产模块，使用 fake/mocking 验证确定性行为 | 真实 LLM、EDGAR、Tavily 集成测试 |

### 2.2 运行时主流程

1. `stockagent.cli:main()` 解析参数，设置日志，并将预期异常转换为命令行错误。
2. `app.run_stock_analysis()` 调用 `load_llm_config()`；配置层读取 `.env` 并要求 LLM 凭据，应用层随后校验 Tavily 凭据。
3. 应用层调用 `agents.run_stock_analysis_agent()`；包级入口延迟导入真正的 orchestrator，避免普通模块导入时初始化重型依赖。
4. orchestrator 通过 `LLMConfig` 显式参数创建 `ChatOpenAI`，将四个 Agent builder 和汇总节点组装为 `AnalysisNodes`。
5. `StateGraph` 以只有 `ticker`、`years` 的初始 State 启动。行业与基本面节点是两个起始分支；估值节点通过联合入边等待它们都返回。
6. 行业、估值和风险 Agent 通过 `web_search()` 调用 Tavily；基本面和估值工具通过 `api.py` 读取 EDGAR 数据。
7. 每个分析节点只把经 Pydantic 验证的局部输出写回 `AnalysisState`，不会把 LangChain 的完整 messages 放入主 State。
8. 估值节点从成功的 `compute_valuation_metrics` 工具消息中解析 PE/PB/PS，检查 `ticker`、`years` 与 JSON 字段后覆盖模型抄写的数值。
9. 风险节点消费前三项 typed output；汇总节点消费四项 output，要求模型生成完整 Markdown，写入 `final_report`。
10. 应用层将 `final_report` 传给 `write_markdown_report()`，后者创建输出目录并写入 `TICKER-YYYY-MM-DD.md`。

## 3. 关键设计与契约

### 3.1 确定性与生成式职责分离

- EDGAR 记录归一化和所有财务公式在 `data/`、`api.py`、`financials/`、`fundamentals/` 中完成，均可不调用 LLM 测试。
- LLM 负责搜索策略、叙事说明、来源汇集、同行对比、风险判断和最终报告写作。
- PE/PB/PS 属于确定性字段：即使估值 Agent 的结构化输出包含这些字段，orchestrator 仍只信任工具返回的计算结果。

### 3.2 财务数据契约

`FinancialRecord` 是外部财务数据进入领域层的唯一标准形状，覆盖利润表、资产负债表和现金流量表的核心年度字段。所有金额字段均允许为 `None`，以保留来源缺失事实；公式通过安全除法返回 `None`，而不是虚构数值。

`api.fetch_financials()` 会将 ticker 规范化为大写，从缓存中取记录，并要求以最新财年为结尾的连续窗口恰好包含 `years` 个年度。数据缺年会抛出 `MissingFiscalYearsError`，不会缩短分析窗口。

### 3.3 Agent State 契约

`AnalysisState` 的必填字段只有 `ticker`、`years`；后续字段在各节点成功后才存在。

| State 字段 | 生产者 | 消费者 | 类型 |
| --- | --- | --- | --- |
| `industry` | 行业节点 | 估值、风险、汇总 | `IndustryOutput` |
| `fundamentals` | 基本面节点 | 估值、风险、汇总 | `FundamentalsOutput` |
| `valuation` | 估值节点 | 风险、汇总 | `ValuationOutput` |
| `risk` | 风险节点 | 汇总 | `RiskOutput` |
| `final_report` | 汇总节点 | `run_stock_analysis_agent()`、报告写入器 | 非空 Markdown 字符串 |

所有结构化 Agent 都配置 `ToolStrategy(OutputType, handle_errors=False)`。orchestrator 在接受输出前检查局部 `ToolMessage`：任何 `status == "error"`、缺失 `structured_response`、Pydantic 校验失败或估值工具合同不满足都会抛出 `AgentOutputError` 并终止 Graph。未知基础设施异常则分类为 `LLMTimeoutError` 或 `LLMResponseError`。

### 3.4 外部边界与缓存

| 外部系统 | 接入点 | 输入 | 输出/失败处理 |
| --- | --- | --- | --- |
| OpenAI 或兼容端点 | `llm.build_openai_model()` | `LLMConfig` | `ChatOpenAI`；原生 OpenAI 端点使用 Responses API，兼容代理不强制使用 |
| SEC EDGAR | `EdgarFinancialsProvider` | ticker、years | 年度 `FinancialRecord`；外部异常包装为 provider 错误 |
| Tavily | `tools.search.web_search()` | query、topic、时间范围 | 裁剪后的 JSON 搜索结果；缺 API key 抛出配置错误 |
| 本地文件系统 | `report.writer` | ticker、Markdown、输出目录 | UTF-8 Markdown 文件 |

`api._fetch_financials_cached()` 以 `(normalized_ticker, years)` 为键，使用容量 32 的进程内 LRU 缓存。缓存位于 API 层，因此多个财务工具在同一进程内请求相同窗口时不会重复访问 EDGAR。

## 4. 目录与文件索引

以下索引覆盖当前 Git 受控文件。`__init__.py` 仅作包标记或集中导出时也会列出，避免其隐含的公共 API 被忽略。

### 4.1 仓库根目录

| 路径 | 作用 | 与其他部分的关系 |
| --- | --- | --- |
| `.env.example` | 提供 LLM 与 Tavily 环境变量模板，不含真实凭据。 | 用户复制为未跟踪的 `.env`；`config.py` 用 `python-dotenv` 加载。 |
| `.gitignore` | 忽略 `.env`、虚拟环境、构建产物、缓存字节码和 `output/`。 | 保证密钥与生成报告不进入版本控制。 |
| `README.md` | 面向使用者的简介、安装、配置、命令示例和简化架构图。 | 与本文互补；本文提供维护级细节。 |
| `pyproject.toml` | Python 版本、运行依赖、`stock` 命令入口、Hatch 构建和 Ruff import 排序配置。 | `stock` 映射到 `stockagent.cli:main`；`uv.lock` 锁定其解析结果。 |
| `uv.lock` | `uv` 生成的精确依赖锁文件。 | 应与 `pyproject.toml` 同步更新；不承载业务逻辑。 |

### 4.2 `docs/`

| 路径 | 作用 |
| --- | --- |
| `docs/architecture.md` | 本文：模块边界、执行流、契约、目录和测试索引。 |
| `docs/fundamentals.md` | 解释利润表、现金流量表、资产负债表和基本面分析概念，属于领域知识说明而非运行时模块。 |

### 4.3 `src/stockagent/`：顶层应用模块

| 路径 | 作用 | 直接协作对象 |
| --- | --- | --- |
| `src/stockagent/__init__.py` | 顶层包标记；当前没有公开业务 API。 | 使 `stockagent` 可作为包导入。 |
| `src/stockagent/cli.py` | 定义 argparse 参数、正整数校验、日志初始化和进程级错误处理。 | 调用 `app.run_stock_analysis()`；使用 `RuntimeOptions` 和 `StockAgentError`。 |
| `src/stockagent/app.py` | 应用服务入口，连接配置、Agent 报告生成和 Markdown 文件写入。 | 延迟导入 `agents` 与 `report.writer`，保持 CLI 到交付层的窄入口。 |
| `src/stockagent/config.py` | 定义 `LLMConfig`、`RuntimeOptions`、默认模型/EDGAR identity、`.env` 加载和 OpenAI 环境变量映射。 | 被 CLI、应用层、LLM 工厂、API 和 orchestrator 使用。 |
| `src/stockagent/errors.py` | 定义所有预期运行时错误的根类 `StockAgentError` 及 `ConfigurationError`。 | CLI 统一捕获；数据和 Agent 错误继承该根类。 |
| `src/stockagent/llm.py` | 校验 `provider:model`，构建 `ChatOpenAI`，并区分原生 OpenAI 与兼容 base URL。 | 由 orchestrator 使用；依赖 `LLMConfig`。 |
| `src/stockagent/observability.py` | 配置 stderr 日志格式与第三方 logger 等级，提供 logger 和阶段日志辅助函数。 | CLI、应用层、Agent 回调和报告写入器使用。 |
| `src/stockagent/api.py` | 确定性应用服务：获取/缓存/校验财年窗口，协调四类基本面计算与估值计算。 | 调用 `data.providers`、`financials`、`fundamentals`；被财务工具调用。 |

### 4.4 `src/stockagent/agents/`：LangGraph 编排层

| 路径 | 作用 | 依赖与输出 |
| --- | --- | --- |
| `src/stockagent/agents/__init__.py` | 对外暴露稳定的 `run_stock_analysis_agent()`，并延迟导入实现。 | `app.py` 的唯一 Agent 包入口。 |
| `src/stockagent/agents/state.py` | 定义四种 Pydantic Agent 输出及 `AnalysisState` TypedDict。 | Graph 节点间唯一业务数据合同。 |
| `src/stockagent/agents/errors.py` | 定义 Agent 输出、超时和响应错误；将底层异常分类。 | orchestrator 的 fail-fast 错误边界。 |
| `src/stockagent/agents/industry_agent.py` | 定义行业研究 prompt，构建仅含 `web_search` 的 structured Agent。 | 返回 `IndustryOutput`。 |
| `src/stockagent/agents/fundamentals_agent.py` | 定义基本面 prompt，构建仅含聚合财务工具的 structured Agent。 | 调用 `get_fundamentals_analysis`，返回 `FundamentalsOutput`。 |
| `src/stockagent/agents/valuation_agent.py` | 定义估值 prompt，构建搜索与估值计算工具 Agent。 | 返回 `ValuationOutput`；数值随后被 orchestrator 的工具结果校正。 |
| `src/stockagent/agents/risk_agent.py` | 定义风险 prompt，构建仅含搜索工具的 structured Agent。 | 消费上游 State 后返回 `RiskOutput`。 |
| `src/stockagent/agents/subagent_progress.py` | `AgentProgressCallbackHandler` 将固定 Agent 的工具开始、完成和失败事件映射为中文日志。 | 每次 Agent invoke 由 orchestrator 注入 callback。 |
| `src/stockagent/agents/orchestrator.py` | 核心编排：定义 `AnalysisNodes`、Graph 拓扑、五个节点、输出校验、估值覆盖、报告提取和公开运行函数。 | 汇聚全部 Agent builder、State、模型、日志和错误模块。 |

### 4.5 `src/stockagent/tools/`：给 LLM 的能力适配器

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/tools/__init__.py` | 重新导出允许被 Agent 使用的搜索和财务工具。 | Agent modules 只从此包导入工具，形成清晰工具面。 |
| `src/stockagent/tools/search.py` | 校验 Tavily key，调用 Tavily，并把原始结果裁剪成标题、URL、摘要、评分和发布日期 JSON。 | 被行业、估值、风险 Agent 调用。 |
| `src/stockagent/tools/financials.py` | 将 `api.py` 的 dataclass 结果序列化为 JSON；提供取记录、单项指标、估值和聚合基本面工具。 | 被基本面与估值 Agent 调用；不直接访问 EDGAR SDK。 |

### 4.6 `src/stockagent/data/`：外部财务数据适配

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/data/__init__.py` | 数据包标记；当前不导出符号。 | 为 provider 子包提供命名空间。 |
| `src/stockagent/data/errors.py` | 定义 provider 错误层级：无数据、缺失财年、限流、未配置和响应归一化失败。 | 继承全局 `StockAgentError`；API 与 EDGAR provider 抛出。 |
| `src/stockagent/data/providers/__init__.py` | 集中导出 provider Protocol 和当前 EDGAR 实现。 | `api.py` 通过此公共入口实例化 provider。 |
| `src/stockagent/data/providers/base.py` | `FinancialsProvider` Protocol，约束 `fetch_annual_records(ticker, years)`。 | 新数据源实现此接口后可替换/扩展。 |
| `src/stockagent/data/providers/edgar.py` | 用 `edgartools.Company` 读取三张年报 DataFrame，按 XBRL concept 优先级映射字段，处理别名、重复行、空值、排序和异常包装。 | 输出 `FinancialRecord`；是当前唯一生产数据提供方。 |

### 4.7 `src/stockagent/financials/`：财务领域模型

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/financials/__init__.py` | 导出所有财务记录与指标 dataclass。 | 领域计算、API、provider 和测试的稳定导入面。 |
| `src/stockagent/financials/models.py` | 定义 `FinancialRecord` 及 Profitability、CashFlow、FinancialHealth、Growth、Valuation 五类指标结果。 | 外部数据归一化的终点，也是纯计算的输入/输出。 |

### 4.8 `src/stockagent/fundamentals/`：无副作用的指标计算

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/fundamentals/__init__.py` | 重新导出输入投影函数和全部指标计算函数。 | `api.py` 的统一计算入口。 |
| `src/stockagent/fundamentals/_utils.py` | 提供 `safe_divide`、自由现金流计算和按财年排序的通用 series 执行器。 | 被各指标模块复用，统一缺失值语义。 |
| `src/stockagent/fundamentals/inputs.py` | 将完整 `FinancialRecord` 投影为每类公式所需的不可变输入 dataclass。 | 防止公式模块依赖无关字段。 |
| `src/stockagent/fundamentals/profitability.py` | 计算毛利率、营业/净利率、ROA、ROE、ROCE、研发和销售管理费率。 | 使用 `ProfitabilityInput` 与通用安全除法。 |
| `src/stockagent/fundamentals/cash_flow.py` | 计算自由现金流及多年度序列。 | 使用 `CashFlowInput` 与 `compute_free_cash_flow`。 |
| `src/stockagent/fundamentals/financial_health.py` | 计算权益比率、负债率、流动/现金比率和经营现金流覆盖负债。 | 使用 `FinancialHealthInput`。 |
| `src/stockagent/fundamentals/growth.py` | 计算收入、净利润、自由现金流的同比增长和 CAGR。 | 对单年、缺失值、零或负基数返回 `None`。 |
| `src/stockagent/fundamentals/valuation.py` | 用最新财年和市场输入计算 trailing PE/PB/PS；PE 可从 `price / EPS` 回退到 `market_cap / net_income`。 | 使用 `ValuationInput`；不从价格推断市值。 |

### 4.9 `src/stockagent/report/`：报告交付

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/report/__init__.py` | 报告包标记；当前不导出符号。 | 保持交付模块命名空间。 |
| `src/stockagent/report/writer.py` | 创建目标目录，以 UTF-8 写入 `TICKER-YYYY-MM-DD.md`，并记录开始/结束日志。 | 由 `app.py` 调用；不理解 LLM、财务数据或 State。 |

### 4.10 `tests/`：验证层

测试使用 Python 标准库 `unittest`。没有测试会访问真实 LLM、EDGAR 或 Tavily；外部边界均通过 mock/fake 模拟。

| 路径 | 覆盖职责 |
| --- | --- |
| `tests/test_cli.py` | 参数默认值、输出目录/日志级别、非法年份、入口错误处理和 stdout 行为。 |
| `tests/test_app.py` | 应用层连接 Agent、报告写入器和主阶段日志。 |
| `tests/test_config.py` | 必需环境变量、默认模型与 OpenAI 环境变量映射。 |
| `tests/test_observability.py` | 日志格式、时间精度及第三方日志等级。 |
| `tests/test_api.py` | ticker/年份校验、连续财年窗口、缓存、无数据错误和最新财年估值选择。 |
| `tests/test_financial_tools.py` | 财务工具 JSON 序列化、当前工具导出、估值市场输入与缺失原因。 |
| `tests/test_search_tool.py` | Tavily 调用参数与裁剪后的搜索接口。 |
| `tests/test_agent_builders.py` | 四个 Agent builder 的工具集合、prompt 和 `ToolStrategy` 输出合同。 |
| `tests/test_agent_state.py` | Pydantic 输出模型、风险评级和 State 必填/可选字段。 |
| `tests/test_analysis_graph.py` | 真实 Graph builder 的完整数据流与联合 fan-in 只执行一次。 |
| `tests/test_analysis_nodes.py` | 节点局部更新、工具错误、结构化输出校验、估值覆盖和报告汇总。 |
| `tests/test_agent_progress.py` | 固定 Agent 的工具开始、完成、失败日志。 |
| `tests/test_agent_errors.py` | Agent 错误类型、模型 provider 校验、Graph 异常分类和 OpenAI client 配置。 |
| `tests/test_orchestrator_logging.py` | 公开 Agent runner 的 Graph 构建、初始 State 与最终报告校验。 |
| `tests/data/__init__.py` | `tests.data` 测试包标记。 |
| `tests/data/providers/__init__.py` | `tests.data.providers` 测试包标记。 |
| `tests/data/providers/test_edgar.py` | XBRL 映射、概念别名/优先级、空值、重复概念、无期间和异常包装。 |
| `tests/fundamentals/__init__.py` | `tests.fundamentals` 测试包标记。 |
| `tests/fundamentals/test_utils.py` | 安全除法与自由现金流的缺失值语义。 |
| `tests/fundamentals/test_profitability.py` | 盈利能力输入投影、公式、缺失值与排序。 |
| `tests/fundamentals/test_cash_flow.py` | 现金流输入投影、自由现金流和排序。 |
| `tests/fundamentals/test_financial_health.py` | 财务健康输入投影、比率、缺失值与排序。 |
| `tests/fundamentals/test_growth.py` | 增长输入投影、同比/CAGR、空序列和异常基数。 |
| `tests/fundamentals/test_valuation.py` | 估值输入投影、PE 回退、市场输入约束和非正值处理。 |
| `tests/report/__init__.py` | `tests.report` 测试包标记。 |
| `tests/report/test_writer.py` | 输出目录创建、文件命名、内容写入和日志。 |

建议运行：

```bash
uv run python -m unittest discover -s tests -v
```

## 5. 目录间依赖关系

```text
cli -> app -> agents ----------------------> tools -> api -> data/providers -> EDGAR
            |                                 |       |
            |                                 |       +-> financials + fundamentals
            |                                 +-> Tavily
            |
            +-> config + llm + observability

app -> report/writer

financials <- data/providers
financials <-> fundamentals (models are inputs/outputs; calculations never do I/O)
tests -> every production layer, but production code never imports tests
```

依赖方向的核心规则是：领域计算不能依赖 Agent、工具、配置、网络或文件系统；工具不能直接理解 Graph State；报告写入器只接受 Markdown；只有 orchestrator 知道 Agent 拓扑和跨 Agent 输出。

## 6. 当前存在但不属于正式源码树的目录

| 路径 | 当前状态 | 架构含义 |
| --- | --- | --- |
| `.git/` | Git 内部元数据。 | 版本控制实现细节，不应被应用代码读取。 |
| `.venv/` | 本地 Python 环境，已忽略。 | 依赖安装产物。 |
| `.pytest_cache/`、`.ruff_cache/`、各级 `__pycache__/` | 工具/解释器缓存，已忽略。 | 可删除再生，不承载业务状态。 |
| `.codegraph/` | 本地代码索引，未跟踪。 | 开发辅助索引，不参与程序运行。 |
| `output/` | 报告写入器创建的已忽略目录。 | 仅保存运行产物；文件名由 ticker 和日期决定。 |
| `templates/` | 当前为空且未被 Git 跟踪。 | 没有运行时加载点，不是当前报告渲染架构的一部分。 |
| `src/stockagent/integrations/` | 当前为空且未被 Git 跟踪。 | 不是 Python 包，也没有被生产代码导入。 |

## 7. 维护与扩展指南

### 新增数据源

在 `data/providers/` 新建实现 `FinancialsProvider` 的 adapter，输出完整 `FinancialRecord`。随后在 `api.py` 明确选择该 provider，并为其字段映射和错误包装添加测试；不要让 Agent 或 `fundamentals/` 直接依赖外部 SDK。

### 新增指标

先在 `financials/models.py` 增加结果字段或新指标 dataclass；在 `fundamentals/inputs.py` 定义最小输入投影；再在独立纯函数模块实现计算，并由 `api.py` 选择性编排。需要暴露给 LLM 时，最后才在 `tools/financials.py` 添加 JSON 工具。

### 新增 Agent 或 Graph 节点

必须同步修改 `agents/state.py` 的 output/State、对应 Agent builder、`AnalysisNodes`、`build_analysis_graph()` 的显式边、下游 prompt，以及 fake-node 图测试。不要用动态 registry 隐藏领域拓扑；节点依赖是业务规则的一部分。

### 调整错误与可观测性

预期业务错误应继承 `StockAgentError`，这样 CLI 能以用户可读的方式终止。工具生命周期日志应通过 `AgentProgressCallbackHandler` 扩展映射，不要把完整模型 messages、原始工具参数或敏感信息写入日志。
