# AKShare A股接口参考文档

本文档包含 AKShare 库中本项目实际使用的 A 股数据接口说明。

## 数据源状态总览

| 数据源 | 域名 | 状态 | 代理兼容 |
|--------|------|------|---------|
| 雪球 | xueqiu.com | ✅ 稳定 | ✅ 可挂代理 |
| 同花顺 | data.10jqka.com.cn | ✅ 稳定 | ✅ 可挂代理 |
| 网易163 | money.163.com | ✅ 可用 | ✅ 可挂代理 |
| BaoStock | baostock.com | ✅ 稳定 | ✅ 可挂代理 |
| 东方财富 | eastmoney.com | ⚠️ 大部分已封 | ❌ 资金流向需直连 |

> 以上均为非官方爬虫接口，非授权 API，可能随时变动。AKShare 更新频繁，接口挂了先 `pip install akshare --upgrade`。

---

## 1. 实时行情接口

### stock_individual_spot_xq（主用）

获取雪球个股实时行情 + 估值数据。**本项目实时行情的主数据源。**

```python
import akshare as ak
df = ak.stock_individual_spot_xq(symbol="SZ002475")
```

**注意**：symbol 需要带交易所前缀：`SZ002475`（深交所）、`SH600519`（上交所）

**返回字段**：

| 字段 | 说明 |
|------|------|
| 名称 | 股票名称 |
| 现价 | 当前价格 |
| 涨幅 | 涨跌幅(%) |
| 最高 | 今日最高 |
| 最低 | 今日最低 |
| 今开 | 今日开盘 |
| 昨收 | 昨日收盘 |
| 成交量 | 成交量 |
| 成交额 | 成交额 |
| 换手率 | 换手率 |
| 市盈率(动) | 动态市盈率 |
| 市盈率(TTM) | TTM市盈率 |
| 市净率 | 市净率 |
| 股息率(TTM) | TTM股息率(%) |
| 52周最高 | 52周最高价 |
| 52周最低 | 52周最低价 |
| 今年以来涨幅 | 年初至今涨跌幅 |

### ~~stock_zh_a_spot_em~~（已废弃）

东方财富全市场实时行情。**接口已被封，不可用。** 保留为备用回退，实际不会命中。

---

## 2. 历史K线接口

本项目使用三级回退：本地 BaoStock → 东方财富 → 网易163

### 本地 BaoStock Parquet（优先）

使用 DuckDB 查询本地预下载的 Parquet 文件，毫秒级响应，无网络依赖。

```python
import duckdb
con = duckdb.connect()
df = con.execute("""
    SELECT 日期, 开盘, 最高, 最低, 收盘, 成交量
    FROM read_parquet('data/all_daily.parquet')
    WHERE code = '000001' AND 日期 >= '2024-01-01'
    ORDER BY 日期
""").fetchdf()
```

### stock_zh_a_hist（回退1）

东方财富历史K线。**目前大部分情况被封，作为回退保留。**

```python
df = ak.stock_zh_a_hist(
    symbol="002475",
    period="daily",
    start_date="20240101",
    end_date="20241231",
    adjust="qfq"
)
```

**返回字段**：日期、开盘、收盘、最高、最低、成交量、成交额、振幅、涨跌幅、涨跌额、换手率

### stock_zh_a_daily（回退2）

网易163历史K线。**代理下可用，作为最终回退。**

```python
df = ak.stock_zh_a_daily(symbol="sz002475", adjust="qfq")
```

**注意**：symbol 格式为 `sz002475` 或 `sh600519`（小写前缀）

**返回字段**：date, open, high, low, close, volume（英文字段名，脚本内部会映射为中文）

---

## 3. 估值指标接口

### stock_individual_spot_xq

同实时行情接口，包含 PE/PB/股息率等估值字段。见第1节。

---

## 4. 财务数据接口

### stock_financial_abstract_ths（主用）

同花顺财务摘要。**本项目财务数据的主数据源。**

```python
df = ak.stock_financial_abstract_ths(symbol="002475", indicator="按报告期")
```

**注意**：返回数据需按报告期降序排列取最新：`df.sort_values('报告期', ascending=False)`

**主要返回字段**：

| 字段 | 说明 |
|------|------|
| 报告期 | 财报所属期间 |
| 净利润 | 净利润 |
| 净利润同比增长率 | 净利润增速 |
| 扣非净利润 | 扣除非经常损益后净利润 |
| 营业总收入 | 营业总收入 |
| 营业总收入同比增长率 | 营收增速 |
| 基本每股收益 | EPS |
| 每股净资产 | BPS |
| 每股经营现金流 | 每股经营现金流 |
| 销售净利率 | 销售净利率 |
| 销售毛利率 | 销售毛利率 |
| 净资产收益率 | ROE |
| 资产负债率 | 资产负债率 |

---

## 5. 资金流向接口

### stock_individual_fund_flow

东方财富个股资金流向。**⚠️ 必须直连，不能走代理。**

```python
df = ak.stock_individual_fund_flow(stock="002475", market="sz")
```

**参数**：
- `stock`：股票代码（纯数字）
- `market`：市场，`"sh"` 上海 / `"sz"` 深圳

**代理问题**：东方财富 `push2his.eastmoney.com` 反爬严格，v2rayN/Clash 等代理工具的系统代理模式会导致 Python requests 走代理后被拒绝连接。解决方案：关闭 TUN 模式，或将 `eastmoney.com` 加入直连规则。

**返回字段**：日期、收盘价、涨跌幅、主力净流入-净额、主力净流入-净占比、超大单净流入-净额、大单净流入-净额、中单净流入-净额、小单净流入-净额

---

## 6. 股东信息接口

### stock_main_stock_holder

同花顺十大股东信息。

```python
df = ak.stock_main_stock_holder(stock="002475")
```

**返回字段**：编号、股东名称、持股数量、持股比例、股本性质、截至日期、公告日期、股东总数、平均持股数

---

## 7. 分红配股接口

### stock_history_dividend_detail

同花顺历史分红明细。

```python
df = ak.stock_history_dividend_detail(symbol="002475", indicator="分红")
```

**indicator 可选值**：`"分红"`、`"配股"`

**返回字段**：公告日期、送股、转增、派息、进度、除权除息日、股权登记日、红股上市日

---

## 8. 其他可用接口（参考）

以下接口本项目未直接使用，但 AKShare 支持，可扩展：

| 接口 | 功能 | 数据源 |
|------|------|--------|
| `stock_board_industry_name_em` | 行业板块列表 | 东方财富 |
| `stock_board_concept_name_em` | 概念板块列表 | 东方财富 |
| `stock_lhb_detail_em` | 龙虎榜详情 | 东方财富 |
| `stock_yjyg_em` | 业绩预告 | 东方财富 |
| `stock_individual_fund_flow_rank` | 资金流向排名 | 东方财富 |
| `stock_fund_flow_individual` | 个股资金排行 | 同花顺 |
| `stock_market_fund_flow` | 大盘资金流向 | 东方财富 |

---

## 常见问题

### 1. 股票代码格式

不同接口对股票代码格式要求不同：
- 行情/资金流向：纯数字 `"002475"`
- 雪球接口：大写前缀 `"SZ002475"` / `"SH600519"`
- 网易163接口：小写前缀 `"sz002475"` / `"sh600519"`
- 同花顺财务/股东/分红：纯数字 `"002475"`

### 2. 接口突然不能用了

1. 先升级 AKShare：`pip install akshare --upgrade`
2. 删缓存重试：`rm .cache/akshare_cache.db`
3. 检查代理设置（资金流向必须直连）
4. 如果是东方财富的接口，可能是 IP 被临时封禁，换网络或等一会儿

### 3. 数据更新时间

- 实时行情：交易时间实时更新
- 历史K线：收盘后更新
- 财务数据：财报披露后更新
- 资金流向：收盘后更新
