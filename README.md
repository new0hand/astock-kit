# astock-kit

A 股全市场数据下载、查询、策略回测工具箱。配合 Hermes Agent 使用，支持微信对话交互。

## 功能

- **数据下载**：基于 BaoStock，全市场 5200+ 只 A 股，支持日线/60分钟/5分钟/除权分红，不限流
- **本地查询**：基于 DuckDB，毫秒级查询，支持个股行情、历史最高价、MA20 信号、全市场扫描、涨幅榜、自定义 SQL
- **策略回测**：MA20 金叉死叉策略，支持单只和全市场回测，输出胜率、最大回撤、交易明细
- **实时分析**：基于 AKShare（Hermes Skill），实时行情、技术指标、资金流向、财务数据、投资评分

## 安装

```bash
pip3 install baostock pandas numpy pyarrow duckdb
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
# 单只股票 MA20 回测
python3 backtest.py ma20 000001

# 输出 Markdown 报告
python3 backtest.py ma20 000001 -o report.md

# 全市场回测
python3 backtest.py ma20 --all

# 全市场回测，显示前 20
python3 backtest.py ma20 --all --top 20
```

## 项目结构

```
astock-kit/
├── README.md
├── .gitignore
├── scripts/                    # 本地数据工具
│   ├── download.py             # 数据下载（单进程）
│   ├── download_fast.py        # 数据下载（推荐）
│   ├── query_data.py           # DuckDB 查询
│   └── backtest.py             # 策略回测
├── skill/                      # Hermes Skill（实时查询）
│   ├── SKILL.md                # Skill 定义
│   ├── config.yaml             # 配置（股票池、定时任务、缓存）
│   ├── references/             # API 文档
│   └── scripts/                # AKShare 实时查询脚本
│       ├── get_realtime_quote.py
│       ├── get_history_kline.py
│       ├── calc_technical.py
│       ├── analyze_investment.py
│       ├── stock_analyzer.py
│       └── ...
└── data/                       # 数据目录（.gitignore，不提交）
    ├── stock_list.parquet
    ├── all_daily.parquet
    ├── all_60m.parquet
    ├── all_5m.parquet
    ├── all_dividend.parquet
    ├── daily/                  # 每只股票单独的日线文件
    ├── 60m/
    ├── 5m/
    └── dividend/
```

## 数据源

| 用途 | 数据源 | 说明 |
|------|--------|------|
| 历史 K 线批量下载 | BaoStock | 免费、不限流、无需注册 |
| 实时行情/财务/资金流 | AKShare | 东方财富/同花顺公开接口 |

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
