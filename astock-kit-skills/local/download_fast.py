#!/usr/bin/env python3
"""
全市场 A 股数据下载器（BaoStock 版，单进程稳定版）

用法：
    python3 download_fast.py                          # 下载全部（日线+60m+5m+除权）
    python3 download_fast.py --period daily            # 只下日线
    python3 download_fast.py --period 60m              # 只下60分钟线
    python3 download_fast.py --period 5m               # 只下5分钟线
    python3 download_fast.py --period dividend          # 只下除权分红
    python3 download_fast.py --test 10                 # 测试模式
    python3 download_fast.py --resume                  # 断点续传
    python3 download_fast.py --update                  # 增量更新
    python3 download_fast.py --summary                 # 查看数据摘要
    python3 download_fast.py --merge-only              # 只合并
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
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
STOCK_LIST_FILE = os.path.join(DATA_DIR, "stock_list.parquet")
DAYS_BACK = 730

PERIODS = {
    "daily": {
        "dir": os.path.join(DATA_DIR, "daily"),
        "merged": os.path.join(DATA_DIR, "all_daily.parquet"),
        "frequency": "d",
        "fields": "date,code,open,high,low,close,volume,amount,turn,pctChg",
        "desc": "日线",
    },
    "60m": {
        "dir": os.path.join(DATA_DIR, "60m"),
        "merged": os.path.join(DATA_DIR, "all_60m.parquet"),
        "frequency": "60",
        "fields": "date,time,code,open,high,low,close,volume,amount",
        "desc": "60分钟线",
    },
    "5m": {
        "dir": os.path.join(DATA_DIR, "5m"),
        "merged": os.path.join(DATA_DIR, "all_5m.parquet"),
        "frequency": "5",
        "fields": "date,time,code,open,high,low,close,volume,amount",
        "desc": "5分钟线",
    },
}

DIVIDEND_DIR = os.path.join(DATA_DIR, "dividend")
DIVIDEND_MERGED = os.path.join(DATA_DIR, "all_dividend.parquet")


def ensure_dirs():
    for p in PERIODS.values():
        os.makedirs(p["dir"], exist_ok=True)
    os.makedirs(DIVIDEND_DIR, exist_ok=True)


def get_stock_list():
    print("正在获取 A 股股票列表...")
    rs = bs.query_stock_basic()
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())
    df = pd.DataFrame(rows, columns=rs.fields)
    df = df[(df["type"] == "1") & (df["status"] == "1")].copy()
    stock_list = df[["code", "code_name"]].copy()
    stock_list.columns = ["code", "name"]
    stock_list = stock_list.reset_index(drop=True)
    stock_list.to_parquet(STOCK_LIST_FILE, index=False)
    print(f"共 {len(stock_list)} 只 A 股（在市）")
    return stock_list


def download_kline(bs_code, start_date, end_date, period_key):
    cfg = PERIODS[period_key]
    rs = bs.query_history_k_data_plus(
        bs_code,
        cfg["fields"],
        start_date=start_date,
        end_date=end_date,
        frequency=cfg["frequency"],
        adjustflag="2"
    )
    rows = []
    while rs.error_code == '0' and rs.next():
        rows.append(rs.get_row_data())

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=rs.fields)
    for col in ["open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    rename_map = {
        "date": "日期", "open": "开盘", "high": "最高", "low": "最低",
        "close": "收盘", "volume": "成交量", "amount": "成交额",
        "turn": "换手率", "pctChg": "涨跌幅",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["code"] = df["code"].str.replace(r"^[a-z]{2}\.", "", regex=True)
    return df


def download_period(stock_list, period_key, resume=False, test_count=0, update=False):
    cfg = PERIODS[period_key]
    print(f"\n{'='*60}")
    print(f"开始下载 {cfg['desc']}...")
    print(f"{'='*60}")

    end_date = datetime.now().strftime("%Y-%m-%d")
    if update:
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"增量更新模式：{start_date} ~ {end_date}")
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

    for _, row in stock_list.iterrows():
        bs_code = row["code"]
        name = row["name"]
        pure_code = bs_code.replace("sh.", "").replace("sz.", "")
        parquet_path = os.path.join(cfg["dir"], f"{pure_code}.parquet")

        if resume and not update and os.path.exists(parquet_path):
            skipped += 1
            continue

        progress = success + skipped + failed + 1
        try:
            df = download_kline(bs_code, start_date, end_date, period_key)
        except Exception as e:
            failed += 1
            print(f"[{progress}/{total}] ✗ {pure_code} {name} 失败: {e}")
            continue

        if df is not None and len(df) > 0:
            if update and os.path.exists(parquet_path):
                old_df = pd.read_parquet(parquet_path)
                df = pd.concat([old_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["code", "日期"], keep="last")
                df = df.sort_values("日期").reset_index(drop=True)

            df.to_parquet(parquet_path, index=False)
            success += 1
            print(f"[{progress}/{total}] ✓ {pure_code} {name} {len(df)} 条")
        else:
            failed += 1
            print(f"[{progress}/{total}] ✗ {pure_code} {name} 无数据")

        time.sleep(0.05)

    elapsed = time.time() - start_time
    print(f"\n{cfg['desc']}完成！成功 {success}，跳过 {skipped}，无数据 {failed}，耗时 {elapsed:.0f} 秒")


def download_dividends(stock_list, resume=False, test_count=0):
    print(f"\n{'='*60}")
    print("开始下载除权分红...")
    print(f"{'='*60}")

    total = len(stock_list)
    if test_count > 0:
        stock_list = stock_list.head(test_count)
        total = test_count

    success = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for _, row in stock_list.iterrows():
        bs_code = row["code"]
        name = row["name"]
        pure_code = bs_code.replace("sh.", "").replace("sz.", "")
        parquet_path = os.path.join(DIVIDEND_DIR, f"{pure_code}.parquet")

        if resume and os.path.exists(parquet_path):
            skipped += 1
            continue

        progress = success + skipped + failed + 1

        try:
            all_rows = []
            fields = None
            for year in range(datetime.now().year - 2, datetime.now().year + 1):
                rs = bs.query_dividend_data(code=bs_code, year=str(year))
                if fields is None:
                    fields = rs.fields
                while rs.error_code == '0' and rs.next():
                    all_rows.append(rs.get_row_data())
        except Exception as e:
            failed += 1
            print(f"[{progress}/{total}] ✗ {pure_code} {name} 失败: {e}")
            continue

        if all_rows and fields:
            df = pd.DataFrame(all_rows, columns=fields)
            df.to_parquet(parquet_path, index=False)
            success += 1
            if progress % 200 == 0 or progress == total:
                print(f"[{progress}/{total}] 除权分红进度: 成功 {success}，跳过 {skipped}，无数据 {failed}")
        else:
            failed += 1

        time.sleep(0.05)

    elapsed = time.time() - start_time
    print(f"\n除权分红完成！成功 {success}，跳过 {skipped}，无数据 {failed}，耗时 {elapsed:.0f} 秒")


def merge_period(period_key):
    cfg = PERIODS[period_key]
    print(f"正在合并 {cfg['desc']} → {os.path.basename(cfg['merged'])} ...")
    _merge_dir(cfg["dir"], cfg["merged"])


def merge_dividends():
    print("正在合并除权分红 → all_dividend.parquet ...")
    _merge_dir(DIVIDEND_DIR, DIVIDEND_MERGED)


def _merge_dir(src_dir, dst_file):
    files = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(".parquet")]
    if not files:
        print("  没有数据文件")
        return
    dfs = []
    for f in files:
        try:
            dfs.append(pd.read_parquet(f))
        except Exception as e:
            print(f"  跳过: {f} ({e})")
    if not dfs:
        return
    merged = pd.concat(dfs, ignore_index=True)
    merged.to_parquet(dst_file, index=False)
    size_mb = os.path.getsize(dst_file) / 1024 / 1024
    print(f"  合并完成：{len(merged):,} 条记录，{size_mb:.1f} MB")


def print_summary():
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
        else:
            d = cfg["dir"]
            if os.path.exists(d):
                fc = len([f for f in os.listdir(d) if f.endswith(".parquet")])
                if fc > 0:
                    print(f"  {cfg['desc']:8s}  {fc} 个文件（未合并）")
    if os.path.exists(DIVIDEND_MERGED):
        size = os.path.getsize(DIVIDEND_MERGED) / 1024 / 1024
        df = pd.read_parquet(DIVIDEND_MERGED)
        stocks = df["code"].nunique() if "code" in df.columns else 0
        print(f"  {'除权分红':8s}  {len(df):>12,} 条  {stocks:>5} 只股票  {size:>8.1f} MB")
    else:
        d = DIVIDEND_DIR
        if os.path.exists(d):
            fc = len([f for f in os.listdir(d) if f.endswith(".parquet")])
            if fc > 0:
                print(f"  {'除权分红':8s}  {fc} 个文件（未合并）")


def main():
    parser = argparse.ArgumentParser(description="全市场 A 股下载器（BaoStock，不限流）")
    parser.add_argument("--period", choices=["daily", "60m", "5m", "dividend", "all"],
                        default="all", help="下载周期（默认 all）")
    parser.add_argument("--resume", action="store_true", help="断点续传")
    parser.add_argument("--test", type=int, default=0, help="测试模式")
    parser.add_argument("--update", action="store_true", help="增量更新")
    parser.add_argument("--merge-only", action="store_true", help="只合并")
    parser.add_argument("--no-merge", action="store_true", help="只下载不合并")
    parser.add_argument("--summary", action="store_true", help="数据摘要")
    args = parser.parse_args()

    ensure_dirs()

    if args.summary:
        print_summary()
        return

    if args.merge_only:
        if args.period in ("all", "daily", "60m", "5m"):
            periods = list(PERIODS.keys()) if args.period == "all" else [args.period]
            for pk in periods:
                merge_period(pk)
        if args.period in ("all", "dividend"):
            merge_dividends()
        print_summary()
        return

    # 获取股票列表
    if os.path.exists(STOCK_LIST_FILE):
        stock_list = pd.read_parquet(STOCK_LIST_FILE)
        print(f"使用已有股票列表: {len(stock_list)} 只")
    else:
        lg = bs.login()
        stock_list = get_stock_list()
        bs.logout()

    # 登录
    lg = bs.login()
    if lg.error_code != '0':
        print(f"BaoStock 登录失败: {lg.error_msg}")
        sys.exit(1)
    print("BaoStock 登录成功\n")

    test_count = args.test if args.test > 0 else 0

    # 下载
    if args.period == "all":
        for pk in PERIODS:
            download_period(stock_list, pk, args.resume, test_count, args.update)
        download_dividends(stock_list, args.resume, test_count)
    elif args.period == "dividend":
        download_dividends(stock_list, args.resume, test_count)
    else:
        download_period(stock_list, args.period, args.resume, test_count, args.update)

    bs.logout()

    # 合并
    if not args.no_merge:
        if args.period == "all":
            for pk in PERIODS:
                merge_period(pk)
            merge_dividends()
        elif args.period == "dividend":
            merge_dividends()
        else:
            merge_period(args.period)

    print_summary()


if __name__ == "__main__":
    main()
