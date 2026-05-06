# astock-kit

A 股全市场数据下载、查询、策略回测、实时分析工具箱。配合 Hermes Agent 使用，支持微信对话交互。

## 功能概览

- **数据下载**：基于 BaoStock，全市场 5200+ 只 A 股，支持日线/60分钟/5分钟/除权分红，免费不限流
- **本地查询**：基于 DuckDB + Parquet，毫秒级查询，支持个股行情、历史最高价、MA20 信号、全市场扫描、涨幅榜、自定义 SQL
- **策略回测**：MA20 金叉死叉策略，支持单只和全市场回测，输出胜率、最大回撤、交易明细、Markdown 报告
- **实时分析**：基于 AKShare，实时行情、技术指标（MA/MACD/RSI/KDJ/BOLL）、资金流向、财务数据、估值、股东、分红
- **智能评分**：四维度加权投资评分模型（估值30% + 成长性30% + 资金面20% + 技术面20%）

## 安装

```bash
# 核心依赖
pip3 install baostock pandas numpy pyarrow duckdb

# AKShare 实时数据（Hermes Skill 需要）
pip3 install akshare
```

## 快速开始

### 1. 下载数据

```bash
cd scripts

# 测试（下载 10 只）
python3 download_fast.py --period daily --test 10

# 全量日线（约 30 分钟）
python3 download_fast.py --period daily

# 全量 60 分钟线
python3 download_fast.py --period 60m

# 全量 5 分钟线
python3 download_fast.py --period 5m

# 除权分红
python3 download_fast.py --period dividend

# 断点续传（跳过已下载的）
python3 download_fast.py --period daily --resume

# 增量更新（每天跑，只拉最近 7 天）
python3 download_fast.py --period daily --update

# 查看数据摘要
python3 download_fast.py --summary
```

### 2. 查询数据

```bash
cd scripts

# 个股最新行情
python3 query_data.py quote 000001

# 近 60 天最高价
python3 query_data.py high 000001 --days 60

# 20 日均线买卖信号
python3 query_data.py ma20 000001

# 全市场扫描：今日 MA20 金叉突破
python3 query_data.py scan-ma20

# 近 5 天涨幅 TOP 20
python3 query_data.py top-gainers --days 5

# 自定义 SQL
python3 query_data.py sql "SELECT * FROM data WHERE code='000001' LIMIT 10"
```

### 3. 策略回测

```bash
cd scripts

# 单只股票 MA20 回测
python3 backtest.py ma20 000001

# 指定初始资金（默认100万，高价股如茅台需要更多）
python3 backtest.py ma20 600519 --capital 2000000

# 输出 Markdown 报告
python3 backtest.py ma20 000001 -o report.md

# 全市场回测（显示前 20）
python3 backtest.py ma20 --all --top 20
```

### 4. 实时分析（AKShare）

```bash
cd skill/scripts

# 实时行情
python3 get_realtime_quote.py 000001

# 历史K线（优先本地数据，--online 强制在线）
python3 get_history_kline.py 000001 --days 60
python3 get_history_kline.py 000001 --days 60 --online

# 技术指标（MA/MACD/RSI/KDJ/BOLL）
python3 calc_technical.py 000001

# 资金流向
python3 get_fund_flow.py 000001 --days 10

# 财务数据
python3 get_financial.py 000001

# 估值指标（PE/PB/股息率）
python3 get_valuation.py 000001

# 股东信息
python3 get_shareholders.py 000001

# 分红记录
python3 get_dividend.py 000001

# 智能投资分析（多维度评分）
python3 analyze_investment.py 000001

# 综合分析报告
python3 stock_analyzer.py 000001
python3 stock_analyzer.py 000001 -o report.txt
```

## 数据源详情

所有在线数据均通过 [AKShare](https://github.com/akfamily/akshare) 库调用，AKShare 是开源的 Python 金融数据接口库，封装了多个公开数据源。这些接口均为**非官方爬虫接口**，不是授权 API，可能随时变动。

### 脚本 → AKShare 函数 → 数据源对照表

| 脚本 | AKShare 函数 | 数据源 | 代理兼容 | 说明 |
|------|-------------|--------|---------|------|
| `get_realtime_quote.py` | `stock_individual_spot_xq()` | 雪球 | ✅ 可挂代理 | 单只股票实时行情、PE/PB/股息率 |
| `get_realtime_quote.py` | `stock_zh_a_spot_em()` | 东方财富 | ❌ 已封 | 备用回退，目前不可用 |
| `get_history_kline.py` | 本地 DuckDB 查询 | BaoStock 离线数据 | ✅ 本地 | 优先使用，最快最稳 |
| `get_history_kline.py` | `stock_zh_a_hist()` | 东方财富 | ❌ 已封 | 在线回退1，目前不可用 |
| `get_history_kline.py` | `stock_zh_a_daily()` | 网易163 | ✅ 可挂代理 | 在线回退2 |
| `calc_technical.py` | 同 `get_history_kline.py` | 同上 | 同上 | 获取K线后本地计算指标 |
| `get_fund_flow.py` | `stock_individual_fund_flow()` | 东方财富 | ⚠️ 必须直连 | 个股每日资金流向明细，需关代理 |
| `get_financial.py` | `stock_financial_abstract_ths()` | 同花顺 | ✅ 可挂代理 | 财务摘要（营收、利润、ROE等） |
| `get_valuation.py` | `stock_individual_spot_xq()` | 雪球 | ✅ 可挂代理 | 估值指标 PE/PB/股息率 |
| `get_shareholders.py` | `stock_main_stock_holder()` | 同花顺 | ✅ 可挂代理 | 十大股东 |
| `get_dividend.py` | `stock_history_dividend_detail()` | 同花顺 | ✅ 可挂代理 | 历史分红记录 |
| `analyze_investment.py` | 综合以上多个函数 | 多数据源 | 部分 | 四维度智能评分 |
| `stock_analyzer.py` | 综合以上多个函数 | 多数据源 | 部分 | 全量综合分析报告 |
| `download_fast.py` | BaoStock 原生接口 | BaoStock | ✅ 可挂代理 | 全市场批量下载，免费不限流 |

### 数据源状态汇总

| 数据源 | 域名 | 状态 | 备注 |
|--------|------|------|------|
| 雪球 | xueqiu.com | ✅ 稳定 | 实时行情、估值，代理下可用 |
| 同花顺 | data.10jqka.com.cn | ✅ 稳定 | 财务、股东、分红，代理下可用 |
| 网易163 | money.163.com | ✅ 可用 | 历史K线备用源，代理下可用 |
| BaoStock | baostock.com | ✅ 稳定 | 批量历史数据下载，免费不限流 |
| 东方财富 | eastmoney.com | ⚠️ 大部分已封 | 反爬严格，仅资金流向可用且需直连 |

### 代理/网络注意事项

- **东方财富**反爬非常严格，同一 IP 高频请求会被封。资金流向接口 (`push2his.eastmoney.com`) 是目前唯一还能用的东方财富接口，但**必须直连**，不能走代理
- 如果使用 v2rayN/Clash 等代理工具，Python 的 `requests` 库会读取 macOS 系统代理设置（即使环境变量为空），导致请求被代理转发后失败
- 解决方案：关闭代理工具的 TUN 模式 / 系统代理，或将 `eastmoney.com` 加入直连规则
- 其他数据源（雪球、同花顺、网易、BaoStock）挂代理也能正常使用

### 缓存机制

脚本使用 SQLite 缓存 (`skill/.cache/akshare_cache.db`)，避免重复请求：

| 数据类型 | 缓存过期时间 |
|---------|------------|
| 实时行情 | 1 分钟 |
| 日K线 | 1 小时 |
| 资金流向 | 1 小时 |
| 估值数据 | 1 小时 |
| 财务数据 | 7 天 |
| 股东数据 | 30 天 |
| 分红数据 | 30 天 |

如遇数据异常，先删缓存再重试：`rm skill/.cache/akshare_cache.db`

## 智能投资分析评分模型

`analyze_investment.py` 使用四维度加权评分（满分 100）：

| 维度 | 权重 | 加分项 | 减分项 |
|------|------|--------|--------|
| 估值 | 30% | PE<15, PB<2, 股息率>2% | PE>40, PB>5 |
| 成长性 | 30% | 营收/利润增速>30% | 负增长 |
| 资金面 | 20% | 10日主力净流入为正 | 持续流出 |
| 技术面 | 20% | MA金叉, MACD金叉, RSI超卖 | MA死叉, RSI超买 |

评分参考：80+ 强烈推荐 / 65-80 推荐买入 / 50-65 谨慎持有 / 35-50 不建议 / <35 建议回避

## 测试

提供 3 个测试脚本，运行前自动清缓存、显示 AKShare 版本。

### 全量测试（30 项）

```bash
bash test_all.sh
```

覆盖全部功能，按客户需求逐条测试：

| 编号 | 测试内容 | 对应脚本 | 数据源 |
|------|---------|---------|--------|
| **第一部分：本地数据查询** | | | |
| #1-2 | 个股最新行情 | `query_data.py quote` | 本地 BaoStock |
| #3-4 | 近N天最高价 | `query_data.py high` | 本地 BaoStock |
| #5-6 | MA20 均线买卖信号 | `query_data.py ma20` | 本地 BaoStock |
| #7 | 全市场 MA20 金叉扫描 | `query_data.py scan-ma20` | 本地 BaoStock |
| #8-9 | 涨幅榜 TOP20 | `query_data.py top-gainers` | 本地 BaoStock |
| #10 | 自定义 SQL 查询 | `query_data.py sql` | 本地 BaoStock |
| **第二部分：策略回测** | | | |
| #11-12 | 单只 MA20 回测 | `backtest.py ma20` | 本地 BaoStock |
| #13 | Markdown 回测报告 | `backtest.py ma20 -o` | 本地 BaoStock |
| #14 | 全市场回测 TOP10 | `backtest.py ma20 --all` | 本地 BaoStock |
| **第三部分：实时数据（AKShare 在线）** | | | |
| #15-16 | 实时行情 | `get_realtime_quote.py` | 雪球 |
| #17 | 历史K线 | `get_history_kline.py` | 本地 → 东方财富 → 网易163 |
| #18 | 技术指标 MA/MACD/RSI/KDJ/BOLL | `calc_technical.py` | 本地 → 东方财富 → 网易163 |
| #19 | 资金流向 | `get_fund_flow.py` | 东方财富（需直连） |
| #20 | 财务数据 | `get_financial.py` | 同花顺 |
| #21 | 估值 PE/PB/股息率 | `get_valuation.py` | 雪球 |
| #22 | 股东信息 | `get_shareholders.py` | 同花顺 |
| #23 | 分红数据 | `get_dividend.py` | 同花顺 |
| **第四部分：智能分析** | | | |
| #24-25 | 智能投资分析（评分） | `analyze_investment.py` | 多数据源 |
| #26-27 | 综合分析报告 | `stock_analyzer.py` | 多数据源 |
| **第五部分：数据下载与更新** | | | |
| #28 | 数据摘要 | `download_fast.py --summary` | 本地 |
| #29 | 增量更新 | `download_fast.py --update` | BaoStock |
| #30 | 断点续传 | `download_fast.py --resume` | BaoStock |

### 在线接口重测（9 项）

换网络后验证 AKShare 在线数据是否正常：

```bash
bash retest_online.sh
```

如果全部失败 → 代理/网络问题；部分失败 → 脚本 bug 或 API 变更。

### 资金流向专项测试（5 项）

资金流向依赖东方财富，需直连网络：

```bash
bash retest_fund_flow.sh
```

测 3 只不同股票的资金流向 + 清缓存后的财务数据。

## 项目结构

```
astock-kit/
├── README.md
├── .gitignore
├── test_all.sh                    # 全量测试（30项）
├── retest_online.sh               # 在线接口重测（9项）
├── retest_fund_flow.sh            # 资金流向专项测试（5项）
├── scripts/                       # 本地数据工具
│   ├── download_fast.py           # 数据下载（多进程，推荐）
│   ├── download.py                # 数据下载（单进程）
│   ├── query_data.py              # DuckDB 查询
│   └── backtest.py                # 策略回测
├── skill/                         # Hermes Skill（实时查询）
│   ├── SKILL.md                   # Skill 定义（Hermes 读取）
│   ├── config.yaml                # 配置（股票池、定时任务、缓存）
│   ├── references/                # API 文档
│   └── scripts/                   # AKShare 在线查询脚本
│       ├── get_realtime_quote.py  # 实时行情（雪球）
│       ├── get_history_kline.py   # 历史K线（本地→东方财富→网易163）
│       ├── calc_technical.py      # 技术指标 MA/MACD/RSI/KDJ/BOLL
│       ├── get_fund_flow.py       # 资金流向（东方财富，需直连）
│       ├── get_financial.py       # 财务数据（同花顺）
│       ├── get_valuation.py       # 估值 PE/PB（雪球）
│       ├── get_shareholders.py    # 股东信息（同花顺）
│       ├── get_dividend.py        # 分红记录（同花顺）
│       ├── analyze_investment.py  # 智能投资分析（四维度评分）
│       ├── stock_analyzer.py      # 综合分析报告
│       ├── cache_manager.py       # SQLite 缓存管理
│       └── scheduler.py           # 定时任务
└── data/                          # 数据目录（.gitignore，不提交）
    ├── stock_list.parquet         # 股票列表
    ├── all_daily.parquet          # 全市场日线（合并）
    ├── all_60m.parquet            # 全市场60分钟线
    ├── all_5m.parquet             # 全市场5分钟线
    ├── all_dividend.parquet       # 全市场除权分红
    └── daily/                     # 每只股票单独文件
```

## AKShare 版本

AKShare 更新非常频繁（几乎每周），主要修复各数据源接口变动和反爬适配。**不会自动更新**，需要手动升级：

```bash
pip3 install akshare --upgrade
```

如果某个接口突然不能用了，第一件事就是升级 AKShare 试试。测试脚本会自动检测并提示版本更新。

## Hermes 部署

```bash
# 安装 Skill
hermes skills install ./skill --force

# 微信网关
hermes gateway setup
hermes pairing approve weixin XXXX

# 后台运行
hermes gateway status
```

## 定时更新

每天收盘后跑增量更新：

```bash
python3 scripts/download_fast.py --period daily --update
```

可配合 crontab 或 Hermes scheduler 自动执行。

## 免责声明

本工具仅供学习研究使用，所有分析结果不构成投资建议。投资有风险，入市需谨慎。数据来源为公开接口，准确性以官方数据为准。
