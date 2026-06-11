# StockAgent 目录架构设计

## 1. 设计目标

StockAgent 的代码结构需要支持以下能力：

- 接入 EDGAR、行情 API、本地文件等不同数据源。
- 将不同来源的数据转换成统一的内部数据模型。
- 为不同基本面类型准备各自所需的输入数据。
- 使用确定性代码计算财务指标。
- 使用 LLM 对计算结果进行解释、归因和风险分析。
- 保持数据采集、指标计算和 LLM 分析相互独立，方便测试和替换。

整体数据流如下：

```text
外部数据源
    -> data/providers 数据采集与标准化
    -> financials 公共财务模型
    -> fundamentals 基本面输入构建与指标计算
    -> analysis LLM 分析
    -> report/cli 输出
```

## 2. 目标目录结构

```text
stockagent/
├── docs/
│   └── architecture.md          # 架构设计文档
├── src/
│   └── stockagent/
│       ├── financials/          # 公共财务数据模型，不依赖任何外部服务或业务逻辑
│       │   ├── __init__.py
│       │   └── models.py        # FinancialRecord（原始事实）、ProfitabilityMetrics / CashFlowMetrics 等指标结果
│       ├── data/
│       │   ├── __init__.py
│       │   └── providers/       # 外部数据采集与标准化，将来源特有格式转换为 financials 公共模型
│       │       ├── __init__.py
│       │       ├── base.py      # FinancialsProvider Protocol 接口，约束所有数据源提供 financial records 的公共能力
│       │       └── edgar.py     # SEC EDGAR 实现：XBRL concept 映射、DataFrame → FinancialRecord 转换
│       ├── fundamentals/        # 确定性基本面指标计算，不访问外部数据源，不调用 LLM
│       │   ├── __init__.py
│       │   ├── inputs.py        # 各类计算的最小输入模型（ProfitabilityInput / CashFlowInput）及从 FinancialRecord 构建的工厂方法
│       │   ├── cash_flow.py     # 现金流指标：自由现金流等
│       │   ├── profitability.py # 盈利能力指标：毛利率、净利率、ROA、ROE、ROCE、费用率等
│       │   ├── financial_health.py  # 财务健康指标：资产负债率、流动比率、现金比率等
│       │   ├── growth.py        # 增长指标：营收/利润同比增长、复合增长率等
│       │   └── valuation.py     # 估值指标：PE、PB、PS、EV/EBITDA 等（需财务数据与市场数据联动）
│       ├── analysis/            # LLM 分析层，对 fundamentals 计算好的结构化指标进行解释与归因
│       │   ├── __init__.py
│       │   ├── base.py          # FundamentalAnalyzer Protocol 接口，支持替换不同模型或规则分析器
│       │   ├── llm.py           # 具体 LLM API 调用、序列化输入、解析输出、超时重试
│       │   └── prompts.py       # Prompt 模板集中管理（盈利、健康、增长、综合等分析 Prompt）
│       ├── report/              # 报告生成层，将指标和分析结果转换为可阅读内容
│       │   ├── __init__.py
│       │   └── builder.py       # 构建终端文本 / Markdown / HTML 报告，使用 templates/ 下的模板
│       ├── config.py            # 集中配置：EDGAR identity、API Key、默认模型、超时重试、默认年份等
│       └── cli.py               # 程序入口：解析参数 → 创建 provider → 调用计算 → 调用分析 → 输出报告
└── tests/                       # 测试目录，结构与源代码对应
    ├── data/
    │   └── providers/           # 用伪造 DataFrame 测试字段映射，不依赖真实网络
    ├── fundamentals/            # 用固定输入测试公式计算和边界情况
    └── analysis/                # mock LLM API，不发起真实请求
```

这是目标结构，不要求一次性创建所有空文件。某个模块开始实现时，再创建对应文件和测试。

## 3. 各目录职责

### 3.1 `financials/`

`financials` 定义 StockAgent 内部统一使用的公共财务数据对象和指标结果对象。

该目录不应该：

- 调用 EDGAR、OpenAI 或其他外部服务。
- 读取环境变量。
- 包含命令行输出逻辑。
- 知道数据来自哪个数据源。
- 编排业务流程或承担报告展示职责。

#### `financials/models.py`

存放公共财务模型，包括：

- 标准化后的年度或季度财务记录。
- 财务指标计算结果。
- LLM 分析前需要传递的结构化结果。

初期可以将模型集中在一个文件中，避免过早拆分。例如：

```python
@dataclass(slots=True, frozen=True)
class FinancialRecord:
    ticker: str
    fiscal_year: int
    revenue: float | None = None
    net_income: float | None = None


@dataclass(slots=True, frozen=True)
class ProfitabilityMetrics:
    fiscal_year: int
    gross_margin: float | None = None
    roe: float | None = None
```

当模型数量明显增加后，可以再拆为 `financial_records.py`、`metric_results.py` 等文件。

### 3.2 `data/providers/`

`data/providers` 负责访问外部数据源，并将来源特有的数据格式转换成 `financials` 中定义的公共模型。

该目录可以依赖第三方数据源 SDK，但不能包含基本面分析逻辑或 LLM 分析逻辑。

#### `data/providers/base.py`

定义数据源需要遵守的公共接口，例如 `FinancialsProvider`。

它不执行真实采集，只约束不同数据源需要提供哪些能力：

```python
class FinancialsProvider(Protocol):
    def fetch_annual_records(
        self,
        ticker: str,
        years: int,
    ) -> list[FinancialRecord]:
        ...
```

CLI 或后续抽出的编排层只依赖这个接口，不直接依赖 EDGAR。未来增加其他数据源时，只需要实现相同接口。

#### `data/providers/edgar.py`

负责所有 EDGAR 特有逻辑，包括：

- 配置 edgartools identity。
- 创建和调用 `edgar.Company`。
- 获取利润表、资产负债表和现金流量表。
- 维护 XBRL concept 与公共字段之间的映射。
- 将 EDGAR DataFrame 转换成 `FinancialRecord`。

当前 EDGAR 逻辑规模较小，先保留为单文件。当代码明显增大后，可以拆成：

```text
data/providers/edgar/
  client.py
  mapper.py
  provider.py
```

`data/providers/edgar.py` 只负责采集和字段标准化，不负责计算 ROE、增长率或其他分析指标。

### 3.3 `fundamentals/`

`fundamentals` 负责确定性的基本面指标计算。

该目录不应该：

- 直接访问 EDGAR 等外部数据源。
- 直接调用 LLM。
- 负责格式化报告。

#### `fundamentals/inputs.py`

定义不同基本面分析类型所需的最小输入模型，并负责从公共 `FinancialRecord` 构建这些输入。

例如，盈利能力分析和财务健康分析所需字段不同：

```python
@dataclass(slots=True, frozen=True)
class ProfitabilityInput:
    fiscal_year: int
    revenue: float | None
    gross_profit: float | None
    net_income: float | None
    total_assets: float | None
    shareholders_equity: float | None
```

使用专用输入模型可以明确每类计算真正依赖哪些数据，避免所有计算函数都依赖完整记录。

#### `fundamentals/profitability.py`

计算盈利能力指标，例如：

- 毛利率。
- 营业利润率。
- 净利率。
- ROA、ROE、ROCE。
- 研发费用率和销售管理费用率。

#### `fundamentals/cash_flow.py`

计算现金流派生指标，例如：

- 自由现金流。

#### `fundamentals/financial_health.py`

计算财务健康指标，例如：

- 资产负债率。
- 流动比率。
- 现金比率。
- 债务与现金流覆盖能力。

#### `fundamentals/growth.py`

计算增长指标，例如：

- 营收同比增长。
- 净利润同比增长。
- 自由现金流增长。
- 多年度复合增长率。

#### `fundamentals/valuation.py`

计算估值指标，例如：

- PE、PB、PS。
- EV/EBIT、EV/EBITDA、EV/FCF。
- 其他需要财务数据与市场数据共同参与的估值指标。

估值模块未来可能同时依赖财务记录和市场数据记录，但仍然不应自行请求外部数据。

### 3.4 `analysis/`

`analysis` 使用 LLM 对已经计算好的结构化指标进行解释。

LLM 不负责基础财务公式计算。毛利率、ROE、增长率等结果必须由 `fundamentals` 中的确定性代码产生。

#### `analysis/base.py`

定义分析器公共接口，例如：

```python
class FundamentalAnalyzer(Protocol):
    def analyze(self, metrics: FundamentalMetrics) -> AnalysisResult:
        ...
```

这样后续可以替换不同模型或增加规则分析器。

#### `analysis/llm.py`

负责：

- 调用具体 LLM API。
- 将结构化指标序列化为模型输入。
- 解析模型输出。
- 处理超时、重试和模型错误。

#### `analysis/prompts.py`

集中管理 Prompt 模板，例如：

- 盈利能力分析 Prompt。
- 财务健康分析 Prompt。
- 增长质量分析 Prompt。
- 综合基本面分析 Prompt。

Prompt 不应散落在 CLI、service 或指标计算文件中。

### 3.5 `report/`

`report` 负责将结构化数据和分析结果转换成用户可阅读的内容。

#### `report/builder.py`

负责：

- 构建终端文本、Markdown 或 HTML 报告。
- 渲染指标表格和 LLM 分析结果。
- 使用 `templates/` 下的报告模板。

该模块只负责展示，不负责重新计算指标。

### 3.6 `config.py`

集中处理运行配置，例如：

- EDGAR identity。
- OpenAI API Key。
- 默认 LLM 模型。
- 请求超时和重试次数。
- 默认采集年份。

配置来源可以是环境变量或 `.env`，但其他业务模块不应到处直接读取环境变量。

### 3.7 `cli.py`

CLI 是程序入口，只负责：

- 解析命令行参数。
- 创建配置和具体 provider。
- 调用 data provider 和 fundamentals 计算模块。
- 调用 analysis 和 report。
- 输出结果并返回明确退出码。

CLI 不应直接操作 `edgar.Company`，也不应包含财务计算公式。

## 4. 依赖方向

允许的主要依赖方向如下：

```text
cli
 -> data/providers
 -> financials

cli
 -> fundamentals
 -> financials

analysis
 -> financials

report
 -> financials
```

需要避免的反向依赖：

- `financials` 不能依赖 `data/providers`、`fundamentals`、`analysis`、`report`。
- `fundamentals` 不能依赖具体数据源。
- `data/providers` 不能调用 `fundamentals` 计算指标。
- `analysis` 不能直接采集外部财务数据。
- `report` 不能承担采集或指标计算职责。

## 5. 派生字段处理原则

`free_cash_flow` 等派生字段不应绑定在 EDGAR 数据源中计算，因为它们与数据来源无关。

推荐采用以下两种方式之一：

1. 在 `fundamentals` 中作为指标计算，不保存到原始 `FinancialRecord`。
2. 增加统一的 enrich/normalize 步骤，在所有数据源标准化完成后统一计算。

初期建议将自由现金流视为指标：

```python
free_cash_flow = operating_cash_flow - capex
```

这样 `FinancialRecord` 只保存从来源归一化得到的基础事实数据。

## 6. 测试目录

测试目录与源代码结构对应：

```text
tests/
  data/
    providers/
      test_edgar.py
  fundamentals/
    test_profitability.py
    test_financial_health.py
    test_growth.py
    test_valuation.py
  analysis/
    test_llm.py
```

测试原则：

- `fundamentals` 使用固定输入测试公式和边界情况。
- `data/providers` 使用伪造 DataFrame 测试字段映射，不依赖真实网络。
- `analysis` mock LLM API，不在单元测试中发起真实请求。
- 真实 EDGAR 或 LLM 请求仅放在单独的集成测试中。
