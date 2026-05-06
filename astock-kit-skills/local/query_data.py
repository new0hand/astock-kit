#!/usr/bin/env python3
"""
DuckDB 本地数据查询工具
基于 Parquet 数据，用 DuckDB 做全市场查询和策略回测。

用法：
    python3 query_data.py quote 000001                    # 查个股最新行情
    python3 query_data.py high 000001 --days 60            # 查近60天最高价
    python3 query_data.py ma20 000001                      # 20日均线买卖信号
    python3 query_data.py scan-ma20                        # 全市场扫描20日均线金叉
    python3 query_data.py top-gainers --days 5             # 近5天涨幅榜
    python3 query_data.py sql "SELECT * FROM data WHERE code='000001' LIMIT 10"  # 自定义SQL
"""

import os
import sys
import argparse

try:
    import duckdb
except ImportError:
    print("请先安装 DuckDB: pip3 install duckdb")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
MERGED_FILE = os.path.join(DATA_DIR, "all_daily.parquet")
STOCK_LIST_FILE = os.path.join(DATA_DIR, "stock_list.parquet")


def get_db():
    """创建 DuckDB 连接并注册数据"""
    if not os.path.exists(MERGED_FILE):
        print(f"数据文件不存在: {MERGED_FILE}")
        print("请先运行: python3 download_all_data.py")
        sys.exit(1)

    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{MERGED_FILE}')")
    if os.path.exists(STOCK_LIST_FILE):
        con.execute(f"""
            CREATE VIEW stock_list AS
            SELECT REGEXP_REPLACE(code, '^[a-z]{{2}}\\.', '') AS code, name
            FROM read_parquet('{STOCK_LIST_FILE}')
        """)
    return con


def cmd_quote(con, code):
    """查个股最新行情"""
    result = con.execute(f"""
        SELECT * FROM data
        WHERE code = '{code}'
        ORDER BY 日期 DESC
        LIMIT 5
    """).fetchdf()
    print(result.to_markdown(index=False))


def cmd_high(con, code, days):
    """查近 N 天最高价"""
    result = con.execute(f"""
        SELECT code, 日期, 最高, 最低, 收盘, 成交量
        FROM data
        WHERE code = '{code}'
        ORDER BY 日期 DESC
        LIMIT {days}
    """).fetchdf()

    if len(result) == 0:
        print(f"未找到 {code} 的数据")
        return

    max_row = result.loc[result["最高"].idxmax()]
    print(f"\n{code} 近 {days} 天最高价:")
    print(f"  日期: {max_row['日期']}")
    print(f"  最高价: {max_row['最高']}")
    print(f"\n详细数据:")
    print(result.to_markdown(index=False))


def cmd_ma20(con, code):
    """20日均线买卖信号"""
    result = con.execute(f"""
        WITH step1 AS (
            SELECT *,
                AVG(收盘) OVER (
                    PARTITION BY code ORDER BY 日期
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) AS ma20
            FROM data
            WHERE code = '{code}'
        ),
        step2 AS (
            SELECT *,
                LAG(收盘) OVER (PARTITION BY code ORDER BY 日期) AS prev_close,
                LAG(ma20) OVER (PARTITION BY code ORDER BY 日期) AS prev_ma20
            FROM step1
        )
        SELECT 日期, 收盘, ROUND(ma20, 2) AS ma20,
            CASE
                WHEN prev_close < prev_ma20 AND 收盘 >= ma20 THEN '买入信号'
                WHEN prev_close > prev_ma20 AND 收盘 <= ma20 THEN '卖出信号'
                WHEN 收盘 > ma20 THEN '均线上方'
                ELSE '均线下方'
            END AS 信号
        FROM step2
        ORDER BY 日期 DESC
        LIMIT 30
    """).fetchdf()
    print(f"\n{code} 20日均线分析（近30天）:")
    print(result.to_markdown(index=False))


def cmd_scan_ma20(con):
    """全市场扫描：今天刚刚突破20日均线的股票"""
    result = con.execute("""
        WITH latest AS (
            SELECT code, MAX(日期) AS max_date FROM data GROUP BY code
        ),
        step1 AS (
            SELECT d.*,
                AVG(d.收盘) OVER (
                    PARTITION BY d.code ORDER BY d.日期
                    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                ) AS ma20
            FROM data d
        ),
        step2 AS (
            SELECT *,
                LAG(收盘) OVER (PARTITION BY code ORDER BY 日期) AS prev_close,
                LAG(ma20) OVER (PARTITION BY code ORDER BY 日期) AS prev_ma20
            FROM step1
        )
        SELECT m.code, s.name, m.日期, m.收盘, ROUND(m.ma20, 2) AS ma20, '金叉突破' AS 信号
        FROM step2 m
        LEFT JOIN stock_list s ON m.code = s.code
        INNER JOIN latest l ON m.code = l.code AND m.日期 = l.max_date
        WHERE m.prev_close < m.prev_ma20 AND m.收盘 >= m.ma20
        ORDER BY m.收盘 / m.ma20 DESC
        LIMIT 50
    """).fetchdf()
    print(f"\n全市场 20 日均线金叉突破（今日）:")
    print(f"共找到 {len(result)} 只\n")
    print(result.to_markdown(index=False))


def cmd_top_gainers(con, days):
    """近 N 天涨幅榜"""
    result = con.execute(f"""
        WITH ranked AS (
            SELECT code, 日期, 收盘,
                ROW_NUMBER() OVER (PARTITION BY code ORDER BY 日期 DESC) AS rn
            FROM data
        ),
        recent AS (
            SELECT
                r1.code,
                r1.收盘 AS latest_close,
                r2.收盘 AS prev_close,
                ROUND((r1.收盘 - r2.收盘) / r2.收盘 * 100, 2) AS 涨幅
            FROM ranked r1
            JOIN ranked r2 ON r1.code = r2.code AND r2.rn = {days}
            WHERE r1.rn = 1 AND r2.收盘 > 0
        )
        SELECT r.code, s.name, r.latest_close AS 最新价, r.prev_close AS "{days}天前价", r.涨幅
        FROM recent r
        LEFT JOIN stock_list s ON r.code = s.code
        ORDER BY r.涨幅 DESC
        LIMIT 20
    """).fetchdf()
    print(f"\n近 {days} 天涨幅 TOP 20:")
    print(result.to_markdown(index=False))


def cmd_sql(con, sql):
    """自定义 SQL 查询"""
    result = con.execute(sql).fetchdf()
    print(result.to_markdown(index=False))


def main():
    parser = argparse.ArgumentParser(description="DuckDB 本地数据查询工具")
    subparsers = parser.add_subparsers(dest="command")

    # quote
    p_quote = subparsers.add_parser("quote", help="查个股最新行情")
    p_quote.add_argument("code", help="股票代码")

    # high
    p_high = subparsers.add_parser("high", help="查近N天最高价")
    p_high.add_argument("code", help="股票代码")
    p_high.add_argument("--days", type=int, default=60, help="天数（默认60）")

    # ma20
    p_ma20 = subparsers.add_parser("ma20", help="20日均线买卖信号")
    p_ma20.add_argument("code", help="股票代码")

    # scan-ma20
    subparsers.add_parser("scan-ma20", help="全市场扫描20日均线金叉")

    # top-gainers
    p_top = subparsers.add_parser("top-gainers", help="近N天涨幅榜")
    p_top.add_argument("--days", type=int, default=5, help="天数（默认5）")

    # sql
    p_sql = subparsers.add_parser("sql", help="自定义SQL查询")
    p_sql.add_argument("query", help="SQL语句")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    con = get_db()

    if args.command == "quote":
        cmd_quote(con, args.code)
    elif args.command == "high":
        cmd_high(con, args.code, args.days)
    elif args.command == "ma20":
        cmd_ma20(con, args.code)
    elif args.command == "scan-ma20":
        cmd_scan_ma20(con)
    elif args.command == "top-gainers":
        cmd_top_gainers(con, args.days)
    elif args.command == "sql":
        cmd_sql(con, args.query)


if __name__ == "__main__":
    main()
