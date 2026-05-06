---
name: astock-kit-skills
description: 使用 AKShare 库获取和分析中国 A 股市场数据。支持：股票实时行情、历史K线、财务报表、估值指标、资金流向、技术指标、智能投资评分、综合分析报告。多数据源自动回退（雪球/同花顺/网易163/本地BaoStock），当用户需要获取 A 股股价、分析个股基本面、查询财务数据、计算技术指标、分析资金流向时使用此 skill。
---

# AKShare A股数据分析 Skill

> **⚠️ 重要规则：所有数据查询必须使用 scripts/ 目录下的 Python 脚本。禁止自己用 curl 调用任何 API。禁止自己编写或生成 curl_fallback.md 等文件。脚本内部已实现多数据源自动回退，不需要额外的回退方案。**

使用 AKShare 库获取中国 A 股市场数据并进行分析。多数据源自动回退，无需注册或 Token。

## 快速开始

### 环境准备

```bash
pip install akshare pandas numpy pyyaml duckdb
```

### 使用脚本

```bash
cd scripts

# 智能投资分析（推荐）
python analyze_investment.py 002475

# 实时行情
python get_realtime_quote.py 002475

# 历史K线
python get_history_kline.py 002475 --days 60

# 技术指标
python calc_technical.py 002475

# 综合分析报告
python stock_analyzer.py 002475 -o report.md
```

## 脚本列表

### 数据获取脚本

| 脚本 | 功能 | 数据源 | 示例 |
|------|------|--------|------|
| `get_realtime_quote.py` | 实时行情 | 雪球（主）→ 东方财富（备） | `python get_realtime_quote.py 002475` |
| `get_history_kline.py` | 历史K线 | 本地BaoStock → 东方财富 → 网易163 | `python get_history_kline.py 002475 --days 60` |
| `get_valuation.py` | 估值指标 | 雪球 | `python get_valuation.py 002475` |
| `get_fund_flow.py` | 资金流向 | 东方财富（⚠️需直连） | `python get_fund_flow.py 002475 --days 10` |
| `get_financial.py` | 财务数据 | 同花顺 | `python get_financial.py 002475` |
| `get_shareholders.py` | 股东信息 | 同花顺 | `python get_shareholders.py 002475` |
| `get_dividend.py` | 分红数据 | 同花顺 | `python get_dividend.py 002475` |

### 分析脚本

| 脚本 | 功能 | 说明 |
|------|------|------|
| `analyze_investment.py` | 智能投资分析 | 四维度评分（估值/成长/资金/技术）+ 投资建议 |
| `calc_technical.py` | 技术指标计算 | MA/MACD/RSI/KDJ/BOLL |
| `stock_analyzer.py` | 综合分析报告 | 合并所有数据的完整报告 |

### 工具脚本

| 脚本 | 功能 | 说明 |
|------|------|------|
| `cache_manager.py` | 数据缓存 | SQLite 本地缓存，自动过期 |
| `scheduler.py` | 定时任务 | 自动获取数据和生成报告 |

## 数据源与回退策略

脚本内置多数据源自动回退，单个源挂了不影响使用：

| 数据 | 优先级1 | 优先级2 | 优先级3 |
|------|---------|---------|---------|
| 实时行情/估值 | 雪球 `stock_individual_spot_xq` | — | — |
| 历史K线 | 本地 BaoStock Parquet | 东方财富 `stock_zh_a_hist` | 网易163 `stock_zh_a_daily` |
| 技术指标 | 同上（获取K线后本地计算） | | |
| 资金流向 | 东方财富 `stock_individual_fund_flow` | — | — |
| 财务数据 | 同花顺 `stock_financial_abstract_ths` | — | — |
| 股东信息 | 同花顺 `stock_main_stock_holder` | — | — |
| 分红记录 | 同花顺 `stock_history_dividend_detail` | — | — |

### 代理/网络注意事项

- 大部分接口（雪球、同花顺、网易163）**挂代理也能正常使用**
- **资金流向**（东方财富 `push2his.eastmoney.com`）**必须直连**，不能走代理
- 东方财富反爬严格，K线和全市场行情接口已封，已切换到其他数据源
- 如用 v2rayN/Clash，Python 的 requests 会读 macOS 系统代理，需关闭 TUN 模式或将 `eastmoney.com` 加入直连规则

## 核心功能

### 1. 智能投资分析

```bash
python analyze_investment.py 002475
```

四维度加权评分（满分100）：
- 📊 估值分析（30%）：PE/PB/股息率
- 📈 成长性分析（30%）：营收/利润增速
- 💵 资金面分析（20%）：主力资金流向
- 📉 技术面分析（20%）：均线/MACD/RSI/KDJ

评分参考：80+ 强烈推荐 / 65-80 推荐 / 50-65 持有观望 / <35 建议回避

### 2. 技术指标

```bash
python calc_technical.py 002475
```

支持指标：
- **MA**: 5/10/20/60日均线
- **MACD**: DIF, DEA, MACD柱（12/26/9）
- **RSI**: 6/12/24日
- **KDJ**: K, D, J
- **BOLL**: 上轨/中轨/下轨（20日 ± 2标准差）

### 3. 数据缓存

自动缓存避免重复请求（SQLite）：
- 实时行情：1分钟
- 日K线/资金流向/估值：1小时
- 财务数据：7天
- 股东/分红数据：30天

如遇数据异常，删缓存重试：`rm .cache/akshare_cache.db`

### 4. 定时任务

```bash
# 立即执行
python scheduler.py --run-now

# 后台运行调度器
python scheduler.py
```

配置 `config.yaml` 设置监控股票和执行时间。

## 输出格式

所有脚本默认输出 **Markdown** 格式，可直接预览或保存：

```bash
python analyze_investment.py 002475 -o 分析报告.md
python stock_analyzer.py 002475 -o 综合报告.txt
```

## 文件结构

```
astock-kit-skills/
├── SKILL.md                     # 本文档
├── config.yaml                  # 配置文件（股票池、定时任务、缓存）
├── references/
│   ├── api_reference.md         # AKShare API 参考
│   └── official_docs.md         # 官方文档索引
├── scripts/                     # AKShare 在线查询脚本
│   ├── get_realtime_quote.py    # 实时行情（雪球）
│   ├── get_history_kline.py     # 历史K线（本地→东方财富→网易163）
│   ├── calc_technical.py        # 技术指标 MA/MACD/RSI/KDJ/BOLL
│   ├── get_fund_flow.py         # 资金流向（东方财富，需直连）
│   ├── get_financial.py         # 财务数据（同花顺）
│   ├── get_valuation.py         # 估值指标（雪球）
│   ├── get_shareholders.py      # 股东信息（同花顺）
│   ├── get_dividend.py          # 分红数据（同花顺）
│   ├── analyze_investment.py    # 智能投资分析（四维度评分）
│   ├── stock_analyzer.py        # 综合分析报告
│   ├── cache_manager.py         # SQLite 缓存管理
│   └── scheduler.py             # 定时任务
├── local/                       # 本地数据工具
│   ├── download_fast.py         # 数据下载（多进程，推荐）
│   ├── download.py              # 数据下载（单进程）
│   ├── query_data.py            # DuckDB 查询
│   └── backtest.py              # 策略回测
└── data/                        # 数据目录（.gitignore，不提交）
```

## 参考资源

- [API 参考文档](references/api_reference.md)
- [AKShare 官方文档](references/official_docs.md)
- **官网**: https://akshare.akfamily.xyz
- **GitHub**: https://github.com/akfamily/akshare

## AKShare 版本

AKShare 更新频繁，接口变动时升级通常能修复：

```bash
pip install akshare --upgrade
```
