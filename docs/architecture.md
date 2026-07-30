# StockAgent 架构说明

> 本文描述当前受版本控制的实现。它是面向维护者的架构与目录索引，不替代 [README](../README.md) 的安装和运行说明，也不把本地缓存、生成报告或未跟踪的设计草案当作正式架构的一部分。

## 1. 系统目标与边界

StockAgent 是一个面向美股的命令行研究报告生成器。一次运行会：

1. 接收股票代码和财年数；
2. 从 SEC EDGAR 获取并标准化年度财务数据；
3. 以纯 Python 计算基本面和估值指标；
4. 使用 Tavily 搜索行业、市场和近期风险信息；
5. 以 LangGraph 编排四个独立的 LLM 分析 Agent；
6. 生成带网页与年度 SEC 10-K 引用的中文 Markdown；
7. 写入 Markdown 与同名 `sources.json` 审计附属文件。

系统只支持 `openai:<model>` 格式的 LLM 配置。它不提供 Web 服务、数据库、长期记忆、checkpoint、异步/流式响应、质量重试或部分成功报告。

## 2. 总体架构

```text
命令行与应用层
  stock CLI
    -> cli.py -> app.py -> run_stock_analysis_agent()

编排层（agents）
  LangGraph StateGraph
       START ─┬─> industry ────────┐
              └─> fundamentals ────┴─> valuation -> risk -> synthesize -> END
                         |                |            |    +-> 摘要与投资建议叙事片段
                         |                |            +-> Tavily 搜索
                         |                +-> Tavily 搜索 + 确定性估值工具（供叙事使用）
                         +-> EDGAR + 确定性基本面工具（供叙事使用）

  orchestrator.py
    LLM typed output + facts.build_*_facts(ticker, years, market inputs)
      -> 完整的 State output

图外报告交付层（report）
  final AnalysisState -> delivery.deliver_report()
    -> composer 编排完整 Markdown
    -> 单次聚合网页与 SEC filing evidence -> citations 渲染脚注
    -> GeneratedReport(Markdown, EvidenceBundle)
    -> app.py -> writer.py -> output/<TICKER>-<DATE>.md
                              output/<TICKER>-<DATE>.sources.json

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
| 入口与应用 | `cli.py`、`app.py` | 参数解析、配置加载、生命周期日志、调用报告工作流并持久化交付产物 | 财务计算、Agent 调度细节、报告构造 |
| 编排 | `agents/orchestrator.py`、各 Agent builder | Graph 拓扑、Agent 调用、工具错误扫描、facts interface 调用、LLM output 与确定性字段合并、汇总节点的叙事生成 | 解析工具 JSON、重复校验取数层不变量、直接解析 EDGAR 表格、构造或持久化报告 |
| 报告交付 | `report/` | 在 Graph 返回后编排完整报告、单次聚合网页与 filing 证据、渲染引用、构造匹配的 Markdown 与 `EvidenceBundle`，并写入双文件产物 | Agent 调度、Graph State 写入、财务计算 |
| 确定性事实处理 | `agents/facts.py` | 用股票代码与财年数直接调用确定性财务分析并投影 State 所需字段；估值另接收 LLM 声明的价格与市值 | 工具 JSON、LangChain 消息、LLM 调用、Graph State 写入、叙事语义和报告渲染 |
| 工具适配 | `tools/` | 将搜索和确定性计算暴露给 Agent，统一为 JSON 文本工具结果 | 业务决策和跨节点状态 |
| 应用/领域服务 | `api.py` | 取数、完整财年窗口校验、缓存、调用各指标计算 | LLM 提示词、HTTP 搜索 |
| 数据适配 | `data/` | 把外部数据源转换为带可空 10-K 引用的 `FinancialRecord` | 指标计算和报告生成 |
| 领域模型与计算 | `financials/`、`fundamentals/` | 财务记录、指标 DTO 与无副作用的公式 | 网络、环境变量、LLM |
| 横切能力 | `config.py`、`errors.py`、`observability.py`、`llm.py` | 配置、错误边界、日志、模型客户端 | 业务流程编排 |
| 验证 | `tests/` | 镜像生产模块，使用 fake/mocking 验证确定性行为 | 真实 LLM、EDGAR、Tavily 集成测试 |

### 2.2 运行时主流程

1. `stockagent.cli:main()` 解析参数，设置日志，并将预期异常转换为命令行错误。
2. `app.run_stock_analysis()` 调用 `load_llm_config()`；配置层读取 `.env` 并要求 LLM 凭据，应用层随后校验 Tavily 凭据。
3. 应用层调用 `agents.run_stock_analysis_agent()`；包级入口延迟导入真正的 orchestrator，避免普通模块导入时初始化重型依赖。
4. orchestrator 通过 `LLMConfig` 显式参数创建 `ChatOpenAI`，将四个 Agent builder 和汇总节点组装为 `AnalysisNodes`。
5. `StateGraph` 以只有 `ticker`、`years` 的初始 State 启动。行业与基本面节点是两个起始分支；估值节点通过联合入边等待它们都返回。
6. 行业、估值和风险 Agent 通过 `web_search()` 调用 Tavily；其 typed output 只保留实际采用的 `Evidence`，不会保存全部搜索结果。
7. 基本面和估值 Agent 保留财务工具供各自叙事使用；工具通过 `api.py` 读取 EDGAR 数据。EDGAR Provider 为匹配的年度记录附加可空 `SecFilingReference`；缺失 filing 元数据只记录 warning，不阻断财务记录。同一股票代码与财年数的重复分析由 API 层缓存复用。
8. 每个分析节点先校验 LLM 侧的局部 typed output，再由编排层用 State 中的 `ticker`、`years` 直接调用 `build_fundamentals_facts()` 或 `build_valuation_facts()`；估值调用还传入 LLM 在 `market_inputs` 中声明的 `price` 与 `market_cap`。编排层把两部分构造成完整 State 模型。LangChain messages 只用于扫描明确的工具错误，工具返回文本和原始 JSON 均不进入 `AnalysisState`。
9. 风险节点消费前三项 typed output；汇总节点消费四项 output，只调用一次模型生成 `SynthesisOutput` 中的摘要与投资建议两个叙事片段，并保留可复用的内部证据标记。完整报告排版、证据聚合和引用渲染都不在该节点内发生。
10. Graph 返回最终 `AnalysisState` 后，`run_stock_analysis_agent()` 在图外调用一次 `report.delivery.deliver_report()`。交付 module 解包四个分析 output 与 `SynthesisOutput`，以 `ReportComposer` 编排完整 Markdown，只聚合一次网页 Evidence 与年度 filing Evidence，再用同一清单渲染引用并构造唯一的 `EvidenceBundle`。引用 ID 直接来自这次渲染，因此“正文脚注 ⊆ 审计证据”由单次构造保证，不依赖两处代码重复算出相同结果。
11. `run_stock_analysis_agent()` 返回匹配的 Markdown 与 `EvidenceBundle`。应用层调用 `write_report_artifacts()`，写入 `TICKER-YYYY-MM-DD.md` 和 `TICKER-YYYY-MM-DD.sources.json`。

## 3. 关键设计与契约

### 3.1 确定性与生成式职责分离

- EDGAR 记录归一化和所有财务公式在 `data/`、`api.py`、`financials/`、`fundamentals/` 中完成，均可不调用 LLM 测试。
- LLM 负责搜索策略、叙事说明、来源选择、同行对比、风险判断，以及摘要与投资建议两个叙事片段；它只能为实际采用的外部事实返回结构化证据和内部标记。完整报告由确定性的报告交付层编排。
- 基本面与估值都将 LLM schema 和 State 模型分开：`FundamentalsAgentOutput` 只含 `narrative`、`concerns`，`ValuationAgentOutput` 只含估值叙事、所选 evidence 与完整 `market_inputs`；对应的 State 模型再增加确定性字段。
- `FundamentalsOutput.annual_financials` 和 `financial_filings` 的最终权威来源是编排层按本次 `ticker`、`years` 直接调用的确定性财务分析 module；基本面工具结果只服务于 Agent 叙事，不回流 State。
- `ValuationOutput` 的 PE/PB/PS 由确定性财务分析 module 使用 `ValuationAgentOutput.market_inputs` 中声明的 `price`、`market_cap` 计算。价格、市值、币种、时点和证据 ID 均以 LLM 的结构化声明为准；估值工具结果不再是报告状态的权威来源。
- 引用渲染是确定性的：有效内部标记按首次出现顺序成为全局脚注；未知标记记录 warning 后移除；未引用 evidence 只保留在 `sources.json`。
- 报告交付也是确定性的：`deliver_report()` 从最终 State 一次构造 Markdown 与 `EvidenceBundle`，证据聚合和年度 filing 投影只有这一条路径。

### 3.2 确定性事实处理 seam

`agents/facts.py` 是编排层与确定性财务分析 module 之间的 deep module，只公开两个 interface：

```python
build_fundamentals_facts(ticker, years) -> _FundamentalsFacts
build_valuation_facts(ticker, years, price, market_cap) -> _ValuationFacts
```

两个 interface 的输入由编排代码直接给定，不接收 LLM output、LangChain messages 或工具 JSON 文本。基本面 interface 接收本次 State 的股票代码与财年数；估值 interface 在相同上下文之外，再接收 LLM 结构化输出声明的价格与市值。返回值只包含要合入完整 State 模型的确定性字段。

基本面路径调用 `api.analyze(ticker, years)`，把强类型的年度记录、盈利能力、现金流和成长性结果投影为按财年升序排列的 `AnnualFinancialSnapshot`，并收集记录上已有的 filing。完整且连续的财年窗口、财年唯一性，以及 filing 与年度记录的配对都由 API 与取数层构造保证；facts module 不再重复实现上下文匹配、逐字段类型、重复、断档或错年配对校验。显式数值 `None` 原样传播，单年 filing 缺失也不会丢弃该年财务数据。

估值路径复用 `api.analyze(ticker, years)` 的年度记录，并把 LLM 声明的 `price`、`market_cap` 传给 `api.compute_valuation()`，只返回 PE/PB/PS。市场输入本身保留在 `ValuationAgentOutput`；其非空 `evidence_id` 必须指向该 Agent 已选择 evidence 的自洽性校验也归属于这个 LLM 侧模型，而不是 facts module。

依赖方向为 `orchestrator.py -> facts.py -> api.py -> data/providers + financials + fundamentals`；facts module 另使用 `SecFilingReference` 和 `AnnualFinancialSnapshot` 作为报告侧投影类型。它不依赖 LangChain、不调用 LLM、不构建 LangGraph、不读写完整 `AnalysisState`，也不判断 narrative 的语义。orchestrator 保留 LangChain seam：它扫描明确的工具错误并校验 `structured_response`，但不再从消息中查找工具结果 content。

这条 seam 没有修改给 LLM 使用的财务工具 JSON 格式、LangGraph 拓扑、报告 Markdown 格式、引用格式、CLI 或应用层 interface。当前实现也不包含报告质量验证、TTM、前瞻估值或新的估值工具合同；为什么确定性事实不应改回工具回流路径，见 [ADR 0001](adr/0001-deterministic-facts-at-source.md)。

### 3.3 财务数据契约

`FinancialRecord` 是外部财务数据进入领域层的唯一标准形状，覆盖利润表、资产负债表和现金流量表的核心年度字段。所有金额字段均允许为 `None`，以保留来源缺失事实；公式通过安全除法返回 `None`，而不是虚构数值。每个记录还可带 `SecFilingReference`，其中包含实际 10-K/10-K/A 的报告期、提交日、CIK、accession、主文档和 SEC Archive URL；未匹配到时该字段为 `None`，不改变计算接口。

`api.fetch_financials()` 会将 ticker 规范化为大写，从缓存中取记录，并要求以最新财年为结尾的连续窗口恰好包含 `years` 个年度。数据缺年会抛出 `MissingFiscalYearsError`，不会缩短分析窗口。

### 3.4 Agent State 契约

`AnalysisState` 的必填字段只有 `ticker`、`years`；后续字段在各节点成功后才存在。

| State 字段 | 生产者 | 消费者 | 类型 |
| --- | --- | --- | --- |
| `industry` | 行业节点 | 估值、风险、汇总、报告交付层 | `IndustryOutput`，含已选网页 `evidence` |
| `fundamentals` | 基本面节点 | 估值、风险、汇总、报告交付层 | `FundamentalsAgentOutput` 的叙事字段加 facts module 直接取得的年度快照与 filing，构造成 `FundamentalsOutput` |
| `valuation` | 估值节点 | 风险、汇总、报告交付层 | `ValuationAgentOutput` 的叙事、`evidence`、`market_inputs` 加 facts module 由同一市场输入计算的 PE/PB/PS，构造成 `ValuationOutput` |
| `risk` | 风险节点 | 汇总、报告交付层 | `RiskOutput`，含已选网页 `evidence` |
| `synthesis` | 汇总节点 | 图外的报告交付层 | `SynthesisOutput`，只含 `summary` 与 `investment_recommendation` 两个 Markdown 叙事片段 |

所有结构化 Agent 都配置 `ToolStrategy(OutputType, handle_errors=False)`。orchestrator 在接受 output 前检查局部 `ToolMessage`：任何 `status == "error"`、缺失 `structured_response` 或 LLM 侧 Pydantic 校验失败都会抛出 `AgentOutputError`。随后，基本面和估值节点调用 facts interface，并由完整 State 模型的构造执行最终字段校验；取数层或估值计算失败同样会在无效数据进入 State 前终止 Graph。未知基础设施异常则分类为 `LLMTimeoutError` 或 `LLMResponseError`。

### 3.5 外部边界与缓存

| 外部系统 | 接入点 | 输入 | 输出/失败处理 |
| --- | --- | --- | --- |
| OpenAI 或兼容端点 | `llm.build_openai_model()` | `LLMConfig` | `ChatOpenAI`；原生 OpenAI 端点使用 Responses API，兼容代理不强制使用 |
| SEC EDGAR | `EdgarFinancialsProvider` | ticker、years | 年度 `FinancialRecord` 与可空 filing 引用；财务取数失败包装为 provider 错误，filing 元数据失败仅降级 |
| Tavily | `tools.search.web_search()` | query、topic、时间范围 | 裁剪后的 JSON 搜索结果；Agent 只保存实际采用的结果，缺 API key 抛出配置错误 |
| 本地文件系统 | `report.writer` | ticker、已渲染 Markdown、`EvidenceBundle`、输出目录 | UTF-8 Markdown 与同名 JSON 审计附属文件 |

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
| `docs/adr/0001-deterministic-facts-at-source.md` | 记录确定性事实由编排层直接取得、不经 LLM 工具边界回流的决策与理由。 |
| `docs/fundamentals.md` | 解释利润表、现金流量表、资产负债表和基本面分析概念，属于领域知识说明而非运行时模块。 |

### 4.3 `src/stockagent/`：顶层应用模块

| 路径 | 作用 | 直接协作对象 |
| --- | --- | --- |
| `src/stockagent/__init__.py` | 顶层包标记；当前没有公开业务 API。 | 使 `stockagent` 可作为包导入。 |
| `src/stockagent/cli.py` | 定义 argparse 参数、正整数校验、日志初始化和进程级错误处理。 | 调用 `app.run_stock_analysis()`；使用 `CLIOptions` 和 `StockAgentError`。 |
| `src/stockagent/app.py` | 应用服务入口，连接配置、Agent 报告生成和双文件报告交付。 | 延迟导入 `agents` 与 `report.writer`，以同一报告日期写入 Markdown 和 JSON。 |
| `src/stockagent/config.py` | 定义 `LLMConfig`、`CLIOptions`、默认模型/EDGAR identity、`.env` 加载和 OpenAI 环境变量映射。 | 被 CLI、应用层、LLM 工厂、API 和 orchestrator 使用。 |
| `src/stockagent/errors.py` | 定义所有预期运行时错误的根类 `StockAgentError` 及 `ConfigurationError`。 | CLI 统一捕获；数据和 Agent 错误继承该根类。 |
| `src/stockagent/llm.py` | 校验 `provider:model`，构建 `ChatOpenAI`，并区分原生 OpenAI 与兼容 base URL。 | 由 orchestrator 使用；依赖 `LLMConfig`。 |
| `src/stockagent/observability.py` | 配置 stderr 日志格式与第三方 logger 等级，提供 logger 和阶段日志辅助函数。 | CLI、应用层、Agent 回调和报告写入器使用。 |
| `src/stockagent/api.py` | 确定性应用服务：获取/缓存/校验财年窗口，协调四类基本面计算与估值计算。 | 调用 `data.providers`、`financials`、`fundamentals`；被财务工具调用。 |

### 4.4 `src/stockagent/agents/`：LangGraph 编排层

| 路径 | 作用 | 依赖与输出 |
| --- | --- | --- |
| `src/stockagent/agents/__init__.py` | 对外暴露稳定的 `run_stock_analysis_agent()`，并延迟导入实现。 | `app.py` 的唯一 Agent 包入口。 |
| `src/stockagent/agents/state.py` | 分别定义 LLM 侧 output schema、带确定性字段的 State 模型、汇总叙事输出，以及 `AnalysisState` TypedDict。 | 通过类型明确 LLM 与确定性事实各自拥有的字段，并约束节点间业务数据；State 不保存已渲染报告或引用 ID。 |
| `src/stockagent/agents/errors.py` | 定义 Agent 输出、超时和响应错误；将底层异常分类。 | orchestrator 的 fail-fast 错误边界。 |
| `src/stockagent/agents/facts.py` | 公开两个 `build_*_facts()` interface，按股票代码、财年数和可选市场输入调用确定性财务分析并投影 State 所需事实。 | 返回基本面或估值的确定性字段；不接收工具 JSON、LangChain messages、LLM output 或完整 Graph State。 |
| `src/stockagent/agents/industry_agent.py` | 定义行业研究 prompt，构建仅含 `web_search` 的 structured Agent。 | 返回 `IndustryOutput`。 |
| `src/stockagent/agents/fundamentals_agent.py` | 定义基本面 prompt，构建仅含聚合财务工具的 structured Agent。 | 调用 `get_fundamentals_analysis` 辅助叙事，返回只含叙事与关注点的 `FundamentalsAgentOutput`。 |
| `src/stockagent/agents/valuation_agent.py` | 定义估值 prompt，构建搜索与估值计算工具 Agent。 | 返回含叙事、证据与声明市场输入的 `ValuationAgentOutput`；报告比率由编排层另行计算。 |
| `src/stockagent/agents/risk_agent.py` | 定义风险 prompt，构建仅含搜索工具的 structured Agent。 | 消费上游 State 后返回 `RiskOutput`。 |
| `src/stockagent/agents/subagent_progress.py` | `AgentProgressCallbackHandler` 将固定 Agent 的工具开始、完成和失败事件映射为中文日志。 | 每次 Agent invoke 由 orchestrator 注入 callback。 |
| `src/stockagent/agents/orchestrator.py` | 核心编排：定义 `AnalysisNodes`、Graph 拓扑和五个节点，调用 Agent、扫描工具错误、以 State 参数调用 facts interface，并在 Graph 返回后调用报告交付 interface。 | 连接 Agent builder、facts、State、模型、交付 module、日志和错误模块；不消费工具返回文本，也不自行构造交付产物。 |

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
| `src/stockagent/data/providers/edgar.py` | 用 `edgartools.Company` 读取三张年报 DataFrame，按 XBRL concept 优先级映射字段，并为年度记录附加 filing 引用。 | 输出 `FinancialRecord`；是当前唯一生产数据提供方。 |
| `src/stockagent/data/providers/edgar_filings.py` | 隔离 `edgartools` filing API，解析 10-K/10-K/A 元数据并构造 SEC Archive 主文档 URL。 | 由 `edgar.py` 通过可 fake resolver 调用；缺失元数据不会中断财务记录。 |

### 4.7 `src/stockagent/financials/`：财务领域模型

| 路径 | 作用 | 关系 |
| --- | --- | --- |
| `src/stockagent/financials/__init__.py` | 导出财务记录、指标 dataclass 和 `SecFilingReference`。 | 领域计算、API、provider 和测试的稳定导入面。 |
| `src/stockagent/financials/models.py` | 定义 `FinancialRecord`、`SecFilingReference` 及 Profitability、CashFlow、FinancialHealth、Growth、Valuation 五类指标结果。 | 外部数据归一化的终点，也是纯计算的输入/输出。 |

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
| `src/stockagent/report/citations.py` | 将 `[industry-1]` 等内部标记按首次出现顺序渲染为全局 Markdown 脚注。 | 未知标记 warning 后移除；返回实际引用的证据 ID。 |
| `src/stockagent/report/composer.py` | 从六个叙事片段、年度财务快照和 filing 编排固定章节的完整 Markdown。 | 由交付 module 调用；保留内部证据标记，供引用渲染器处理。 |
| `src/stockagent/report/delivery.py` | 定义图外唯一报告交付 interface 与 `GeneratedReport`，从最终 State 单次构造 Markdown 和 `EvidenceBundle`。 | 统一报告编排、证据聚合、年度 filing 投影和引用渲染；由 orchestrator 在 Graph 返回后调用。 |
| `src/stockagent/report/evidence.py` | 定义 `EvidenceBundle` 与 `sources.json` 序列化契约。 | 记录选取证据、市场输入、实际引用 ID 和年度 filing。 |
| `src/stockagent/report/writer.py` | 创建目标目录，以 UTF-8 写入 Markdown 和同 stem 的 `.sources.json`。 | 由 `app.py` 调用；接收已渲染内容和证据包，不理解 LLM 或 Graph 拓扑。 |

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
| `tests/test_agent_state.py` | LLM schema 与 State 模型拆分、确定性字段默认值、证据 ID 唯一性、市场输入证据关联、年度 filing、风险评级和 State 必填/可选字段。 |
| `tests/test_deterministic_facts.py` | 两个公开 facts interface 的类型化投影：年度快照字段来源、缺失值、排序、filing 缺失，以及声明市场输入驱动的估值比率。 |
| `tests/test_analysis_graph.py` | 真实 Graph builder 的完整数据流、联合 fan-in，以及从取数层到最终 Markdown 财务表和 SEC 脚注的穿透行为。 |
| `tests/test_analysis_nodes.py` | LangChain 工具错误 seam、State 参数到 facts interface 的连接、声明市场输入驱动估值、节点局部 State 更新，以及汇总节点的叙事输出与上游提示词。 |
| `tests/test_agent_progress.py` | 固定 Agent 的工具开始、完成、失败日志。 |
| `tests/test_agent_errors.py` | Agent 错误类型、模型 provider 校验、Graph 异常分类和 OpenAI client 配置。 |
| `tests/test_orchestrator_logging.py` | 公开 Agent runner 的 Graph 构建、初始 State、最终报告和 SEC evidence bundle 校验。 |
| `tests/data/__init__.py` | `tests.data` 测试包标记。 |
| `tests/data/providers/__init__.py` | `tests.data.providers` 测试包标记。 |
| `tests/data/providers/test_edgar.py` | XBRL 映射、概念别名/优先级、空值、重复概念、无期间、异常包装和 filing 降级。 |
| `tests/data/providers/test_edgar_filings.py` | fake filing resolver 的年度匹配、10-K/A 优先、缺失元数据与 SEC Archive URL。 |
| `tests/fundamentals/__init__.py` | `tests.fundamentals` 测试包标记。 |
| `tests/fundamentals/test_utils.py` | 安全除法与自由现金流的缺失值语义。 |
| `tests/fundamentals/test_profitability.py` | 盈利能力输入投影、公式、缺失值与排序。 |
| `tests/fundamentals/test_cash_flow.py` | 现金流输入投影、自由现金流和排序。 |
| `tests/fundamentals/test_financial_health.py` | 财务健康输入投影、比率、缺失值与排序。 |
| `tests/fundamentals/test_growth.py` | 增长输入投影、同比/CAGR、空序列和异常基数。 |
| `tests/fundamentals/test_valuation.py` | 估值输入投影、PE 回退、市场输入约束和非正值处理。 |
| `tests/report/__init__.py` | `tests.report` 测试包标记。 |
| `tests/report/test_citations.py` | 脚注顺序、重复引用、未知标记、缺失日期、SEC 格式和普通 Markdown 链接保留。 |
| `tests/report/test_composer.py` | 固定章节顺序、财务快照格式、缺失 filing 提示和内部证据标记保留。 |
| `tests/report/test_delivery.py` | 以普通最终 State 验证完整报告、单次证据清单、引用 ID、SEC evidence 投影、市场输入及缺字段错误。 |
| `tests/report/test_evidence.py` | evidence bundle 一致性及 `sources.json` 的缺失值序列化。 |
| `tests/report/test_writer.py` | 输出目录创建、同 stem 双文件命名、内容写入和日志。 |

建议运行：

```bash
uv run python -m unittest discover -s tests -v
```

## 5. 目录间依赖关系

```text
cli -> app -> agents -> orchestrator -> tools -> api -> data/providers -> EDGAR
                    |              |         |         +-> financials + fundamentals
                    |              |         +-> Tavily
                    |              +-> facts -> api
                    |                        +-> financials + report/composer
                    +-> report/delivery -> report/composer
                                        +-> report/citations
                                        +-> report/evidence
                    +-> state + config + llm + observability

app -> report/writer -> Markdown + sources.json

financials <- data/providers
financials <-> fundamentals (models are inputs/outputs; calculations never do I/O)
tests -> every production layer, but production code never imports tests
```

依赖方向的核心规则是：领域计算不能依赖 Agent、工具、配置、网络或文件系统；工具不能直接理解 Graph State；facts module 可以调用确定性 API，但不能依赖 LangChain、LLM 或完整 Graph State；报告写入器只接受已渲染 Markdown 与证据包。只有 orchestrator 知道 Graph 拓扑和 Agent 调用顺序；只有报告交付 module 知道如何从跨 Agent 输出编排完整报告、聚合证据、渲染引用并构造审计证据包；只有 facts module 理解强类型财务分析结果到 State 确定性字段的投影。

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

### 调整证据与交付

网页证据必须从 Agent 的 typed output 进入 `AnalysisState`，不要把 LangChain 原始 messages 放入主 State。新增正文引用时复用稳定 evidence ID，由 `report.delivery` 在一次交付构造中聚合证据，再由 `report.citations` 统一分配脚注编号；正文脚注与审计证据的包含关系必须由这条单一路径保证，不能在 orchestrator 或 app 中重复聚合。`sources.json` 必须由同一次构造得到的 `EvidenceBundle` 序列化，不能手工拼接 JSON。年度财务来源通过 `FinancialRecord.filing` 进入基本面 output；缺失引用保留为缺失事实，不伪造 SEC URL。

### 新增 Agent 或 Graph 节点

必须同步修改 `agents/state.py` 的 output/State、对应 Agent builder、`AnalysisNodes`、`build_analysis_graph()` 的显式边、下游 prompt，以及 fake-node 图测试。不要用动态 registry 隐藏领域拓扑；节点依赖是业务规则的一部分。

### 调整确定性事实字段

先在确定性财务分析的 typed interface 与对应 State/报告投影中明确字段所有权和缺失语义，再修改 `agents/facts.py` 的显式投影，并优先通过 `tests/test_deterministic_facts.py` 验证公开 interface。orchestrator 只负责传入 State 上下文和显式市场输入、合并 LLM output 与确定性字段，不应消费工具返回文本。季度/TTM 应扩展确定性财务分析 module 的 interface，再由 facts module 投影；不要为编排层新增工具 JSON 契约、手写解析器和畸形 JSON 测试。若字段属于 narrative 质量或前瞻估值，应先设计独立合同，不能把尚未落地的能力当作当前 facts module 职责。

### 调整错误与可观测性

预期业务错误应继承 `StockAgentError`，这样 CLI 能以用户可读的方式终止。工具生命周期日志应通过 `AgentProgressCallbackHandler` 扩展映射，不要把完整模型 messages、原始工具参数或敏感信息写入日志。
