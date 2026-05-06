# -*- coding: utf-8 -*-
"""
获取历史 K 线数据

优先从本地 BaoStock Parquet 数据读取，本地无数据时回退到在线 API。

用法:
    python get_history_kline.py 002475
    python get_history_kline.py 002475 --days 60
    python get_history_kline.py 002475 --start 20240101 --end 20241231
    python get_history_kline.py 002475 --online   # 强制在线获取
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
except ImportError:
    print("请先安装依赖: pip install pandas")
    sys.exit(1)

# 本地数据路径（astock-kit-skills/data/all_daily.parquet）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DAILY_FILE = os.path.join(DATA_DIR, "all_daily.parquet")


def get_from_local(code, start_date, end_date):
    """从本地 Parquet 读取"""
    if not os.path.exists(DAILY_FILE):
        return None

    try:
        import duckdb
        con = duckdb.connect()
        df = con.execute(f"""
            SELECT 日期, 开盘 AS 开盘, 最高, 最低, 收盘, 成交量, 成交额
            FROM read_parquet('{DAILY_FILE}')
            WHERE code = '{code}'
              AND 日期 >= '{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
              AND 日期 <= '{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
            ORDER BY 日期
        """).fetchdf()
        con.close()

        if len(df) > 0:
            return df
    except Exception:
        pass
    return None


def get_from_online(code, start_date, end_date, period='daily', adjust='qfq'):
    """在线获取（优先东方财富，回退网易163）"""
    try:
        import akshare as ak
    except ImportError:
        print("在线模式需要 akshare: pip install akshare")
        return None

    # 尝试东方财富
    try:
        df = ak.stock_zh_a_hist(
            symbol=code, period=period,
            start_date=start_date, end_date=end_date,
            adjust=adjust
        )
        if df is not None and not df.empty:
            print("  数据来源: 东方财富")
            return df
    except Exception:
        pass

    # 回退：网易163
    try:
        df = ak.stock_zh_a_daily(symbol=f"sz{code}" if code.startswith(('0', '3')) else f"sh{code}",
                                  start_date=start_date, end_date=end_date, adjust=adjust)
        if df is not None and not df.empty:
            print("  数据来源: 网易163")
            return df
    except Exception:
        pass

    return None


def get_history_kline(code, period='daily', start_date=None, end_date=None,
                      adjust='qfq', use_cache=True, force_online=False):
    """获取历史行情数据"""
    if not end_date:
        end_date = datetime.now().strftime('%Y%m%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

    print(f"获取数据: {code} ({start_date} - {end_date})")

    # 优先本地数据
    if not force_online:
        df = get_from_local(code, start_date, end_date)
        if df is not None and len(df) > 0:
            print(f"  从本地数据加载: {len(df)} 条记录")
            return df

    # 在线获取
    df = get_from_online(code, start_date, end_date, period, adjust)
    if df is not None and not df.empty:
        print(f"  获取成功: {len(df)} 条记录")
        return df

    print("  所有数据源均获取失败")
    return None


def main():
    parser = argparse.ArgumentParser(description='获取历史K线数据')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--days', type=int, default=60, help='最近N天')
    parser.add_argument('--start', help='开始日期 YYYYMMDD')
    parser.add_argument('--end', help='结束日期 YYYYMMDD')
    parser.add_argument('--period', default='daily', help='周期: daily/weekly/monthly')
    parser.add_argument('--adjust', default='qfq', help='复权: qfq/hfq/""')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')
    parser.add_argument('--online', action='store_true', help='强制在线获取（跳过本地数据）')

    args = parser.parse_args()

    start_date = args.start
    if not start_date and not args.end:
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')

    df = get_history_kline(
        args.code, args.period, start_date, args.end,
        args.adjust, use_cache=not args.no_cache,
        force_online=args.online
    )

    if df is not None:
        print("\n数据预览 (最近10天):")
        print(df.tail(10).to_string(index=False))


if __name__ == '__main__':
    main()
