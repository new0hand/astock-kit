#!/usr/bin/env python3
"""
全市场 A 股数据下载器（BaoStock 版）
免费、不限流、无需注册。

用法：
    python3 download.py                          # 下载全部（日线+60m+5m）
    python3 download.py --period daily            # 只下日线
    python3 download.py --period 60m              # 只下60分钟线
    python3 download.py --period 5m               # 只下5分钟线
    python3 download.py --test 10                 # 测试模式，只下 10 只
    python3 download.py --resume                  # 断点续传
    python3 download.py --update                  # 增量更新（追加最近7天）
    python3 download.py --summary                 # 查看数据摘要
    python3 download.py --merge-only              # 只合并，不下载
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

try:
    import baostock as bs
    import pandas as pd
except ImportError:
    print("请先安装依赖: pip3 install baostock pandas pyarrow")
    sys.exit(1)

# ========== 配置 ==========
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STOCK_LIST_FILE = os.path.join(DATA_DIR, "stock_list.parquet")
DAYS_BACK = 730  # 两年

# 各周期配置
PERIODS = {
    "daily": {
        "dir": os.path.join(DATA_DIR, "daily"),
        "merged": os.path.join(DATA_DIR, "all_daily.parquet"),
        "frequency": "d",
        "fields_daily": "date,code,open,high,low,close,volume,amount,turn,pctChg",
        "desc": "日线",
    },
    "60m": {
        "dir": os.path.join(DATA_DIR, "60m"),
        "merged": os.path.join(DATA_DIR, "all_60m.parquet"),
        "frequency": "60",
        "fields_intra": "date,time,code,open,high,low,close,volume,amount",
        "desc": "60分钟线",
    },
    "5m": {
        "dir": os.path.join(DATA_DIR, "5m"),
        "merged": os.path.join(DATA_DIR, "all_5m.parquet"),
        "frequency": "5",
        "fields_intra": "date,time,code,open,high,low,close,volume,amount",
        "desc": "5分钟线",
    },
}


def ensure_dirs():
    """创建所有数据目录"""
    for p in PERIODS.values():
        os.makedirs(p["dir"], exist_ok=True)


def get_stock_list():
    """获取全部 A 股股票列表"""
    print("正在获取 A 股股票列表...")
    rs = bs.query_stock_basic()
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())

    df = pd.DataFrame(rows, columns=rs.fields)
    # 只保留 A 股股票（type=1），且在市（status=1）
    df = df[(df["type"] == "1") & (df["status"] == "1")].copy()
    # code 格式: sh.600000 / sz.000001
    stock_list = df[["code", "code_name"]].copy()
    stock_list.columns = ["code", "name"]
    stock_list = stock_list.reset_index(drop=True)
    stock_list.to_parquet(STOCK_LIST_FILE, index=False)
    print(f"共 {len(stock_list)} 只 A 股（在市）")
    return stock_list


def download_kline(bs_code, start_date, end_date, period_key):
    """下载 K 线数据"""
    cfg = PERIODS[period_key]
    freq = cfg["frequency"]
    if freq == "d":
        fields = cfg["fields_daily"]
    else:
        fields = cfg["fields_intra"]

    try:
        rs = bs.query_history_k_data_plus(
            bs_code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency=freq,
            adjustflag="2"  # 前复权
        )
        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())

        if rows:
            df = pd.DataFrame(rows, columns=rs.fields)
            # 转换数值列
            numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
            if "turn" in df.columns:
                numeric_cols.append("turn")
            if "pctChg" in df.columns:
                numeric_cols.append("pctChg")
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            # 统一列名，跟 akshare 格式对齐方便回测脚本使用
            rename_map = {
                "date": "日期",
                "open": "开盘",
                "high": "最高",
                "low": "最低",
                "close": "收盘",
                "volume": "成交量",
                "amount": "成交额",
            }
            if "turn" in df.columns:
                rename_map["turn"] = "换手率"
            if "pctChg" in df.columns:
                rename_map["pctChg"] = "涨跌幅"
            df = df.rename(columns=rename_map)

            # code 列统一为纯数字（去掉 sh./sz. 前缀）
            df["code"] = df["code"].str.replace(r"^[a-z]{2}\.", "", regex=True)
            return df
    except Exception as e:
        print(f"  ✗ {bs_code} 下载失败: {e}")
    return None


def download_period(stock_list, period_key, resume=False, test_count=0, update=False):
    """下载指定周期的数据"""
    cfg = PERIODS[period_key]
    print(f"\n{'='*60}")
    print(f"开始下载 {cfg['desc']}...")
    print(f"{'='*60}")

    end_date = datetime.now().strftime("%Y-%m-%d")

    if update:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"增量更新模式：只拉 {start_date} ~ {end_date}")
    else:
        start_date = (datetime.now() - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")

    total = len(stock_list)
    if test_count > 0:
        stock_list = stock_list.head(test_count)
        total = test_count
        print(f"测试模式：只下载 {total} 只")

    success = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for i, row in stock_list.iterrows():
        bs_code = row["code"]  # sh.600000 格式
        name = row["name"]
        pure_code = bs_code.replace("sh.", "").replace("sz.", "")
        parquet_path = os.path.join(cfg["dir"], f"{pure_code}.parquet")

        # 断点续传
        if resume and not update and os.path.exists(parquet_path):
            skipped += 1
            continue

        progress = success + skipped + failed + 1
        print(f"[{progress}/{total}] {cfg['desc']} {pure_code} {name} ...", end=" ")

        df = download_kline(bs_code, start_date, end_date, period_key)
        if df is not None and len(df) > 0:
            if update and os.path.exists(parquet_path):
                old_df = pd.read_parquet(parquet_path)
                df = pd.concat([old_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["code", "日期"], keep="last")
                df = df.sort_values("日期").reset_index(drop=True)

            df.to_parquet(parquet_path, index=False)
            print(f"✓ {len(df)} 条")
            success += 1
        else:
            print(f"✗ 无数据")
            failed += 1

        # BaoStock 不限流，间隔短一点就行
        time.sleep(0.1)

    elapsed = time.time() - start_time
    print(f"\n{cfg['desc']}完成！成功 {success}，跳过 {skipped}，无数据 {failed}，耗时 {elapsed:.0f} 秒")


def merge_period(period_key):
    """合并指定周期的数据"""
    cfg = PERIODS[period_key]
    print(f"正在合并 {cfg['desc']} → {os.path.basename(cfg['merged'])} ...")
    _merge_dir(cfg["dir"], cfg["merged"])


def _merge_dir(src_dir, dst_file):
    """通用合并函数"""
    parquet_files = [
        os.path.join(src_dir, f)
        for f in os.listdir(src_dir)
        if f.endswith(".parquet")
    ]
    if not parquet_files:
        print("  没有找到数据文件")
        return

    dfs = []
    for f in parquet_files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception as e:
            print(f"  跳过损坏文件: {f} ({e})")

    if not dfs:
        print("  没有有效数据")
        return

    merged = pd.concat(dfs, ignore_index=True)
    merged.to_parquet(dst_file, index=False)
    size_mb = os.path.getsize(dst_file) / 1024 / 1024
    print(f"  合并完成：{len(merged):,} 条记录，{size_mb:.1f} MB")


def print_summary():
    """打印数据摘要"""
    print(f"\n{'='*60}")
    print("数据下载汇总")
    print(f"{'='*60}")
    print(f"数据目录: {DATA_DIR}\n")

    if os.path.exists(STOCK_LIST_FILE):
        sl = pd.read_parquet(STOCK_LIST_FILE)
        print(f"  股票列表: {len(sl)} 只\n")

    for name, cfg in PERIODS.items():
        path = cfg["merged"]
        if os.path.exists(path):
            size = os.path.getsize(path) / 1024 / 1024
            df = pd.read_parquet(path)
            stocks = df["code"].nunique()
            print(f"  {cfg['desc']:8s}  {len(df):>12,} 条  {stocks:>5} 只股票  {size:>8.1f} MB")

    # 单文件目录统计
    for name, cfg in PERIODS.items():
        d = cfg["dir"]
        if os.path.exists(d):
            files = [f for f in os.listdir(d) if f.endswith(".parquet")]
            if files and not os.path.exists(cfg["merged"]):
                print(f"  {cfg['desc']:8s}  {len(files)} 个文件（未合并）")

    print(f"\n合并后的数据可以用 query_data.py 和 backtest.py 查询和回测")


def main():
    parser = argparse.ArgumentParser(description="全市场 A 股数据下载器（BaoStock 版，不限流）")
    parser.add_argument("--period", choices=["daily", "60m", "5m", "all"],
                        default="all", help="下载周期（默认 all）")
    parser.add_argument("--resume", action="store_true", help="断点续传，跳过已下载的")
    parser.add_argument("--test", type=int, default=0, help="测试模式，只下载指定数量")
    parser.add_argument("--update", action="store_true", help="增量更新（只拉最近7天追加）")
    parser.add_argument("--merge-only", action="store_true", help="只合并，不下载")
    parser.add_argument("--no-merge", action="store_true", help="只下载，不合并")
    parser.add_argument("--summary", action="store_true", help="只打印数据摘要")
    args = parser.parse_args()

    ensure_dirs()

    if args.summary:
        lg = bs.login()
        print_summary()
        bs.logout()
        return

    if args.merge_only:
        if args.period == "all":
            for pk in PERIODS:
                merge_period(pk)
        else:
            merge_period(args.period)
        print_summary()
        return

    # 登录 BaoStock
    lg = bs.login()
    if lg.error_code != '0':
        print(f"BaoStock 登录失败: {lg.error_msg}")
        sys.exit(1)
    print(f"BaoStock 登录成功")

    stock_list = get_stock_list()

    # 下载
    periods_to_download = list(PERIODS.keys()) if args.period == "all" else [args.period]
    for pk in periods_to_download:
        download_period(stock_list, pk, args.resume, args.test, args.update)

    # 合并
    if not args.no_merge:
        for pk in periods_to_download:
            merge_period(pk)

    bs.logout()
    print("BaoStock 已退出")
    print_summary()


if __name__ == "__main__":
    main()
