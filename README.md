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
cd astock-kit-skills/local

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
cd astock-kit-skills/local

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
cd astock-kit-skills/local

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
cd astock-kit-skills/scripts

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

在线数据**大部分**通过 [AKShare](https://github.com/akfamily/akshare) 库调用（开源的 Python 金融数据接口库，封装多个公开数据源，均为**非官方爬虫接口**，不是授权 API，可能随时变动）。**例外：实时行情的雪球/腾讯/东财/新浪四个源都是自写 HTTP 请求，不经 AKShare**，等于不受 AKShare 上游变动连累的独立通道。

> **实时行情四级回退**：共享模块 **`scripts/realtime_source.py`**，回退链 **雪球（自写预热）→ 腾讯财经 → 东方财富 push2 → 新浪**，`get_realtime_quote` / `get_valuation` / `analyze_investment` / `stock_analyzer` 统一调用 `get_spot_dict()`。雪球可用时数据最全；逐级降级。
>
> **雪球为什么自写预热**：AKShare 的 `stock_individual_spot_xq` 在 `akshare/stock/cons.py` 写死了一个 `xq_a_token`，会过期，过期后返回 `error_code 400016`。本 skill 不依赖那个常量，而是先访问 `xueqiu.com` 让服务器**现发新 cookie** 再请求，规避旧 token 过期。所以雪球能稳定拿到含估值的全字段。
>
> **各源字段覆盖**：雪球最全（动/静/TTM PE、股息率、每股、52 周）；腾讯有 PE(TTM)/PB；东财 push2 有行情+换手/量比无估值；新浪仅基础行情。某源缺的字段在结果里留空。

### 脚本 → 函数 → 数据源对照表

| 脚本 | 函数 | 数据源 | 代理兼容 | 说明 |
|------|-------------|--------|---------|------|
| `get_realtime_quote.py` | `realtime_source.get_spot_dict()` → 雪球（自写预热 HTTP） | 雪球 | ✅ 可挂代理 | 实时行情主源，字段最全 |
| `get_realtime_quote.py` | `realtime_source.get_spot_dict()` → `qt.gtimg.cn`（自写 HTTP） | 腾讯财经 | ✅ 可挂代理 | 回退1，国内直连最快 |
| `get_realtime_quote.py` | `realtime_source.get_spot_dict()` → `push2/stock/get`（自写 HTTP） | 东方财富 | ⚠️ 必须直连 | 回退2，反爬激进 |
| `get_realtime_quote.py` | `realtime_source.get_spot_dict()` → `hq.sinajs.cn`（自写 HTTP） | 新浪 | ✅ 可挂代理 | 回退3兜底，仅基础行情 |
| `get_history_kline.py` | 本地 DuckDB 查询 | BaoStock 离线数据 | ✅ 本地 | 优先使用，最快最稳 |
| `get_history_kline.py` | `stock_zh_a_hist()` | 东方财富 | ❌ 已封 | 在线回退1，目前不可用 |
| `get_history_kline.py` | `stock_zh_a_daily()` | 网易163 | ✅ 可挂代理 | 在线回退2 |
| `calc_technical.py` | 同 `get_history_kline.py` | 同上 | 同上 | 获取K线后本地计算指标 |
| `get_fund_flow.py` | `stock_individual_fund_flow()` | 东方财富 | ⚠️ 必须直连 | 个股每日资金流向明细，需关代理 |
| `get_financial.py` | `stock_financial_abstract_ths()` | 同花顺 | ✅ 可挂代理 | 财务摘要（营收、利润、ROE等） |
| `get_valuation.py` | `realtime_source.get_spot_dict()` → 四级回退 | 雪球→腾讯→东财→新浪 | ✅ 可挂代理 | 估值 PE/PB/股息率（雪球满血，降级后部分字段留空） |
| `get_shareholders.py` | `stock_main_stock_holder()` | 同花顺 | ✅ 可挂代理 | 十大股东 |
| `get_dividend.py` | `stock_history_dividend_detail()` | 同花顺 | ✅ 可挂代理 | 历史分红记录 |
| `analyze_investment.py` | 综合以上多个函数（实时行情走 `realtime_source`，K线加网易163回退） | 多数据源 | 部分 | 四维度智能评分 |
| `stock_analyzer.py` | 综合以上多个函数（实时行情走 `realtime_source`，K线加网易163回退） | 多数据源 | 部分 | 全量综合分析报告 |
| `download_fast.py` | BaoStock 原生接口 | BaoStock | ✅ 可挂代理 | 全市场批量下载，免费不限流 |

### 数据源状态汇总

| 数据源 | 域名 | 状态 | 备注 |
|--------|------|------|------|
| 雪球 | xueqiu.com | ✅ 自写预热可用 | 实时行情主源，字段最全。akshare 内置 token 已过期(400016)，本 skill 自写预热拿新 token，不走 akshare 那个常量 |
| 腾讯财经 | qt.gtimg.cn | ✅ 稳定 | 实时行情回退1，自写 HTTP，国内直连最快，有 PE(TTM)/PB |
| 东方财富(实时) | push2.eastmoney.com | ⚠️ 需直连 | 实时行情回退2，`stock/get` 接口，反爬激进需关代理，无估值字段 |
| 新浪(实时) | hq.sinajs.cn | ✅ 稳定 | 实时行情回退3兜底，自写 HTTP，仅基础行情无估值 |
| 同花顺 | data.10jqka.com.cn | ✅ 稳定 | 财务、股东、分红，代理下可用 |
| 网易163 | money.163.com | ✅ 可用 | 历史K线备用源，代理下可用 |
| BaoStock | baostock.com | ✅ 稳定 | 批量历史数据下载，免费不限流 |
| 东方财富 | eastmoney.com | ⚠️ 大部分已封 | 反爬严格，仅资金流向可用且需直连 |

### 代理/网络注意事项

- **东方财富**反爬非常严格，同一 IP 高频请求会被封。还能用的东财接口（资金流向 `push2his.eastmoney.com`、实时行情 `push2.eastmoney.com/stock/get`）都**必须直连**，不能走代理；全市场行情/K线接口已封
- 如果使用 v2rayN/Clash 等代理工具，Python 的 `requests` 库会读取 macOS 系统代理设置（即使环境变量为空），导致请求被代理转发后失败
- 解决方案：关闭代理工具的 TUN 模式 / 系统代理，或将 `eastmoney.com` 加入直连规则
- 其他数据源（雪球、腾讯财经、同花顺、网易、BaoStock）挂代理也能正常使用

### 缓存机制

脚本使用 SQLite 缓存 (`astock-kit-skills/.cache/akshare_cache.db`)，避免重复请求：

| 数据类型 | 缓存过期时间 |
|---------|------------|
| 实时行情 | 1 分钟 |
| 日K线 | 1 小时 |
| 资金流向 | 1 小时 |
| 估值数据 | 1 小时 |
| 财务数据 | 7 天 |
| 股东数据 | 30 天 |
| 分红数据 | 30 天 |

如遇数据异常，先删缓存再重试：`rm astock-kit-skills/.cache/akshare_cache.db`

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
| #15-16 | 实时行情 | `get_realtime_quote.py` | 雪球 → 腾讯 → 东财 → 新浪 |
| #17 | 历史K线 | `get_history_kline.py` | 本地 → 东方财富 → 网易163 |
| #18 | 技术指标 MA/MACD/RSI/KDJ/BOLL | `calc_technical.py` | 本地 → 东方财富 → 网易163 |
| #19 | 资金流向 | `get_fund_flow.py` | 东方财富（需直连） |
| #20 | 财务数据 | `get_financial.py` | 同花顺 |
| #21 | 估值 PE/PB/股息率 | `get_valuation.py` | 雪球 → 腾讯 → 东财 → 新浪 |
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
├── test_all.sh                        # 全量测试（30项）
├── retest_online.sh                   # 在线接口重测（9项）
├── retest_fund_flow.sh                # 资金流向专项测试（5项）
└── astock-kit-skills/                 # Hermes Skill 目录（hermes skills install 安装这个）
    ├── SKILL.md                       # Skill 定义（Hermes 读取）
    ├── config.yaml                    # 配置（股票池、定时任务、缓存）
    ├── references/                    # API 文档
    ├── scripts/                       # 在线查询脚本
    │   ├── realtime_source.py         # 实时行情共享模块（雪球→腾讯→东财→新浪 四级回退）
    │   ├── get_realtime_quote.py      # 实时行情（走共享模块四级回退）
    │   ├── get_history_kline.py       # 历史K线（本地→东方财富→网易163）
    │   ├── calc_technical.py          # 技术指标 MA/MACD/RSI/KDJ/BOLL
    │   ├── get_fund_flow.py           # 资金流向（东方财富，需直连）
    │   ├── get_financial.py           # 财务数据（同花顺）
    │   ├── get_valuation.py           # 估值 PE/PB（走共享模块四级回退）
    │   ├── get_shareholders.py        # 股东信息（同花顺）
    │   ├── get_dividend.py            # 分红记录（同花顺）
    │   ├── analyze_investment.py      # 智能投资分析（四维度评分）
    │   ├── stock_analyzer.py          # 综合分析报告
    │   ├── cache_manager.py           # SQLite 缓存管理
    │   └── scheduler.py               # 定时任务
    ├── local/                         # 本地数据工具
    │   ├── download_fast.py           # 数据下载（多进程，推荐）
    │   ├── download.py                # 数据下载（单进程）
    │   ├── query_data.py              # DuckDB 查询
    │   └── backtest.py                # 策略回测
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

### 安装 Skill

```bash
# 安装 Python 依赖
pip3 install akshare baostock pandas numpy pyarrow duckdb pyyaml

# 从 GitHub 安装 Skill 到 Hermes（一行搞定）
hermes skills install new0hand/astock-kit/astock-kit-skills --force
```

### 下载全市场数据（首次需要）

```bash
# 克隆仓库（需要本地数据工具和测试脚本）
git clone https://github.com/new0hand/astock-kit.git
cd astock-kit/scripts

# 全量日线（约30分钟）
python3 download_fast.py --period daily

# 验证安装
cd ..
bash test_all.sh
```

### 更新 Skill

```bash
hermes skills install new0hand/astock-kit/astock-kit-skills --force
```

### 微信网关

```bash
hermes gateway setup
hermes pairing approve weixin XXXX
```

### 后台运行

```bash
hermes gateway status
```

## Hermes 对话测试

安装完成后，在 Hermes 对话中（微信或终端）发送以下提示词验证功能：

### 本地数据查询

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 查一下平安银行的最新行情 | 个股行情 query_data.py quote | 秒级 |
| 平安银行近60天最高价是哪天 | 历史最高 query_data.py high | 秒级 |
| 平安银行的20日均线买卖信号 | MA20信号 query_data.py ma20 | 秒级 |
| 帮我扫描全市场今天MA20金叉的股票 | 全市场扫描 query_data.py scan-ma20 | 10-30秒 |
| 最近5天涨幅最大的20只股票 | 涨幅榜 query_data.py top-gainers | 秒级 |

### 策略回测

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我回测平安银行的MA20策略 | 单只回测 backtest.py ma20 | 秒级 |
| 帮我回测茅台的MA20策略，初始资金200万 | 高价股回测 backtest.py --capital | 秒级 |
| 全市场MA20回测，显示收益最高的前10只 | 全市场回测 backtest.py --all --top 10 | 1-5分钟 |

### 实时数据（AKShare 在线）

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 查一下茅台的实时股价 | 实时行情 get_realtime_quote.py | 2-3秒 |
| 帮我看看平安银行最近60天的K线走势 | 历史K线 get_history_kline.py | 2-3秒 |
| 帮我算一下平安银行的技术指标 | 技术指标 calc_technical.py | 2-3秒 |
| 查一下平安银行的财务数据 | 财务数据 get_financial.py | 2-3秒 |
| 平安银行的市盈率和市净率是多少 | 估值指标 get_valuation.py | 2-3秒 |
| 平安银行的十大股东有哪些 | 股东信息 get_shareholders.py | 2-3秒 |
| 平安银行的历史分红记录 | 分红数据 get_dividend.py | 2-3秒 |

### 智能分析

| 提示词 | 对应功能 | 耗时 |
|--------|---------|------|
| 帮我分析一下平安银行值不值得投资 | 智能评分 analyze_investment.py | 5-10秒 |
| 给我出一份茅台的完整分析报告 | 综合报告 stock_analyzer.py | 10-15秒 |

> **注意**：资金流向（get_fund_flow.py）依赖东方财富接口，必须直连网络，不能挂代理。如需测试：`帮我查一下平安银行的资金流向`

## 定时更新（crontab）

每天收盘后自动拉取最新数据，无需手动操作。

### 设置步骤

```bash
# 1. 打开 crontab 编辑器（首次会提示选编辑器，选 nano 或 vim 都行）
crontab -e

# 2. 在打开的文件末尾加上这一行（北京时间 18:00，根据你的时区换算）
# 北京时间（UTC+8）：
0 18 * * 1-5 cd ~/.hermes/skills/astock-kit-skills/local && /usr/bin/python3 download_fast.py --period daily --update >> /tmp/astock-update.log 2>&1

# 夏威夷时间（UTC-10，北京18:00 = 夏威夷00:00）：
0 0 * * 1-5 cd ~/.hermes/skills/astock-kit-skills/local && /usr/bin/python3 download_fast.py --period daily --update >> /tmp/astock-update.log 2>&1

# 3. 保存退出（nano: Ctrl+O 回车 Ctrl+X；vim: :wq 回车）

# 4. 验证是否生效
crontab -l
```

### 说明

- `0 18 * * 1-5`（北京时间）/ `0 0 * * 1-5`（夏威夷时间）：每周一到周五，北京时间 18:00 执行（A股15:00收盘，等3小时确保各数据源完全更新）
- `>> /tmp/astock-update.log 2>&1`：日志追加写入，出问题可以查
- macOS 首次使用 crontab 可能弹出"终端想要管理您的文件"权限弹窗，点允许即可

### 常用操作

```bash
# 查看当前定时任务
crontab -l

# 修改定时任务
crontab -e

# 删除所有定时任务
crontab -r

# 查看更新日志
cat /tmp/astock-update.log

# 手动执行一次（测试用）
cd ~/.hermes/skills/astock-kit-skills/local && python3 download_fast.py --period daily --update
```

### macOS 注意事项

macOS 需要给 cron 授权"完全磁盘访问权限"才能正常执行脚本：

1. 打开 系统设置 → 隐私与安全性 → 完全磁盘访问权限
2. 点左下角 + 号
3. 按 `Cmd+Shift+G`，输入 `/usr/sbin/cron`，点打开
4. 确保 cron 的开关是打开状态

如果不授权，crontab 任务可能静默失败且不报错。

### "python 想访问你的照片图库" 弹窗

首次运行时 macOS 可能弹出"python3.x 想访问你的照片图库"权限请求。这是 Python 的依赖库（如 matplotlib、Pillow）初始化时扫描系统资源目录触发的 macOS 误判，**本程序不会访问任何照片数据**。直接点**「不允许」**即可，不影响任何功能。

## 免责声明

本工具仅供学习研究使用，所有分析结果不构成投资建议。投资有风险，入市需谨慎。数据来源为公开接口，准确性以官方数据为准。
