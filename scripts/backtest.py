#!/usr/bin/env python3
"""
策略回测工具
基于本地 Parquet 数据 + DuckDB，支持全市场回测。

用法：
    python3 backtest.py ma20 000001                 # 单只股票 MA20 金叉策略
    python3 backtest.py ma20 --all                  # 全市场 MA20 回测
    python3 backtest.py ma20 --all --top 20         # 全市场回测，只显示前20
    python3 backtest.py ma20 000001 -o report.md    # 输出 Markdown 报告
"""

import os
import sys
import argparse
import math
from datetime import datetime

try:
    import duckdb
    import pandas as pd
    import numpy as np
except ImportError:
    print("请先安装依赖: pip3 install duckdb pandas numpy pyarrow")
    sys.exit(1)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DAILY_FILE = os.path.join(DATA_DIR, "all_daily.parquet")
STOCK_LIST_FILE = os.path.join(DATA_DIR, "stock_list.parquet")


def get_db():
    """创建 DuckDB 连接"""
    if not os.path.exists(DAILY_FILE):
        print(f"数据文件不存在: {DAILY_FILE}")
        print("请先运行: python3 download_all_data.py --period daily")
        sys.exit(1)
    con = duckdb.connect()
    con.execute(f"CREATE VIEW data AS SELECT * FROM read_parquet('{DAILY_FILE}')")
    if os.path.exists(STOCK_LIST_FILE):
        con.execute(f"CREATE VIEW stock_list AS SELECT * FROM read_parquet('{STOCK_LIST_FILE}')")
    return con


def calc_ma20_signals(df):
    """计算 MA20 金叉死叉信号"""
    df = df.sort_values("日期").reset_index(drop=True)
    df["ma20"] = df["收盘"].rolling(20).mean()
    df["prev_close"] = df["收盘"].shift(1)
    df["prev_ma20"] = df["ma20"].shift(1)

    # 信号：收盘价上穿 MA20 = 买入，下穿 = 卖出
    df["signal"] = 0
    df.loc[(df["prev_close"] < df["prev_ma20"]) & (df["收盘"] >= df["ma20"]), "signal"] = 1   # 买入
    df.loc[(df["prev_close"] > df["prev_ma20"]) & (df["收盘"] <= df["ma20"]), "signal"] = -1  # 卖出

    return df


def run_backtest(df, initial_capital=100000):
    """模拟交易，计算收益和回撤"""
    df = calc_ma20_signals(df)
    signals = df[df["signal"] != 0].copy()

    if len(signals) == 0:
        return None

    trades = []
    position = None
    capital = initial_capital
    peak_capital = initial_capital
    max_drawdown = 0
    max_drawdown_pct = 0

    for _, row in signals.iterrows():
        if row["signal"] == 1 and position is None:
            # 买入
            shares = int(capital / row["收盘"] / 100) * 100  # 按手买
            if shares <= 0:
                continue
            cost = shares * row["收盘"]
            position = {
                "buy_date": row["日期"],
                "buy_price": row["收盘"],
                "shares": shares,
                "cost": cost
            }
            capital -= cost

        elif row["signal"] == -1 and position is not None:
            # 卖出
            revenue = position["shares"] * row["收盘"]
            profit = revenue - position["cost"]
            profit_pct = profit / position["cost"] * 100
            capital += revenue

            trades.append({
                "买入日期": position["buy_date"],
                "买入价": round(position["buy_price"], 2),
                "卖出日期": row["日期"],
                "卖出价": round(row["收盘"], 2),
                "股数": position["shares"],
                "盈亏": round(profit, 2),
                "收益率%": round(profit_pct, 2),
            })
            position = None

            # 更新最大回撤
            current_total = capital
            if current_total > peak_capital:
                peak_capital = current_total
            drawdown = peak_capital - current_total
            drawdown_pct = drawdown / peak_capital * 100 if peak_capital > 0 else 0
            if drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = drawdown_pct
                max_drawdown = drawdown

    # 如果还有持仓，按最后价格计算
    if position is not None:
        last_price = df.iloc[-1]["收盘"]
        unrealized = position["shares"] * last_price
        capital += unrealized

    total_return = capital - initial_capital
    total_return_pct = total_return / initial_capital * 100
    win_trades = [t for t in trades if t["盈亏"] > 0]
    lose_trades = [t for t in trades if t["盈亏"] <= 0]
    win_rate = len(win_trades) / len(trades) * 100 if trades else 0

    # 平均盈亏
    avg_win = np.mean([t["收益率%"] for t in win_trades]) if win_trades else 0
    avg_lose = np.mean([t["收益率%"] for t in lose_trades]) if lose_trades else 0

    return {
        "总交易次数": len(trades),
        "盈利次数": len(win_trades),
        "亏损次数": len(lose_trades),
        "胜率%": round(win_rate, 1),
        "总收益": round(total_return, 2),
        "总收益率%": round(total_return_pct, 2),
        "最大回撤": round(max_drawdown, 2),
        "最大回撤%": round(max_drawdown_pct, 2),
        "平均盈利%": round(avg_win, 2),
        "平均亏损%": round(avg_lose, 2),
        "期末资金": round(capital, 2),
        "trades": trades,
        "has_position": position is not None,
    }


def backtest_single(con, code, output=None):
    """单只股票回测"""
    df = con.execute(f"SELECT * FROM data WHERE code = '{code}' ORDER BY 日期").fetchdf()
    if len(df) < 30:
        print(f"{code} 数据不足 30 天，无法回测")
        return

    # 获取股票名称
    try:
        name = con.execute(f"SELECT name FROM stock_list WHERE code = '{code}'").fetchone()[0]
    except Exception:
        name = code

    result = run_backtest(df)
    if result is None:
        print(f"{code} {name} 没有产生交易信号")
        return

    report = generate_report(code, name, result)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"报告已保存: {output}")
    else:
        print(report)


def backtest_all(con, top=50):
    """全市场回测"""
    codes = con.execute("SELECT DISTINCT code FROM data").fetchdf()["code"].tolist()
    print(f"全市场回测 MA20 策略，共 {len(codes)} 只股票...\n")

    results = []
    for i, code in enumerate(codes):
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{len(codes)}")

        df = con.execute(f"SELECT * FROM data WHERE code = '{code}' ORDER BY 日期").fetchdf()
        if len(df) < 30:
            continue

        result = run_backtest(df)
        if result is None:
            continue

        try:
            name = con.execute(f"SELECT name FROM stock_list WHERE code = '{code}'").fetchone()[0]
        except Exception:
            name = code

        results.append({
            "代码": code,
            "名称": name,
            "交易次数": result["总交易次数"],
            "胜率%": result["胜率%"],
            "总收益率%": result["总收益率%"],
            "最大回撤%": result["最大回撤%"],
            "平均盈利%": result["平均盈利%"],
            "平均亏损%": result["平均亏损%"],
        })

    if not results:
        print("没有产生交易信号")
        return

    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values("总收益率%", ascending=False)

    print(f"\n{'='*80}")
    print(f"MA20 金叉策略全市场回测结果（TOP {top}）")
    print(f"{'='*80}")
    print(f"有效回测股票: {len(results_df)} 只")
    print(f"平均胜率: {results_df['胜率%'].mean():.1f}%")
    print(f"平均收益率: {results_df['总收益率%'].mean():.1f}%")
    print(f"盈利股票: {len(results_df[results_df['总收益率%'] > 0])} 只 "
          f"({len(results_df[results_df['总收益率%'] > 0]) / len(results_df) * 100:.1f}%)")
    print(f"\nTOP {top} 收益率最高:\n")
    print(results_df.head(top).to_markdown(index=False))

    print(f"\n\nBOTTOM 10 收益率最低:\n")
    print(results_df.tail(10).to_markdown(index=False))


def generate_report(code, name, result):
    """生成 Markdown 格式的回测报告"""
    report = f"""# {code} {name} MA20 金叉策略回测报告

生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 策略说明

- **策略**: 20 日均线金叉买入，死叉卖出
- **买入条件**: 收盘价从下方上穿 20 日均线
- **卖出条件**: 收盘价从上方下穿 20 日均线
- **初始资金**: 100,000 元
- **交易单位**: 100 股（1手）整数倍

## 回测结果

| 指标 | 值 |
|------|------|
| 总交易次数 | {result['总交易次数']} |
| 盈利次数 | {result['盈利次数']} |
| 亏损次数 | {result['亏损次数']} |
| **胜率** | **{result['胜率%']}%** |
| **总收益** | **{result['总收益']:+,.2f} 元** |
| **总收益率** | **{result['总收益率%']:+.2f}%** |
| **最大回撤** | **{result['最大回撤']:,.2f} 元 ({result['最大回撤%']:.2f}%)** |
| 平均盈利 | {result['平均盈利%']:+.2f}% |
| 平均亏损 | {result['平均亏损%']:+.2f}% |
| 期末资金 | {result['期末资金']:,.2f} 元 |
| 当前持仓 | {'是' if result['has_position'] else '否'} |

## 交易明细

| 买入日期 | 买入价 | 卖出日期 | 卖出价 | 股数 | 盈亏 | 收益率 |
|---------|--------|---------|--------|------|------|--------|
"""
    for t in result["trades"]:
        profit_mark = "+" if t["盈亏"] > 0 else ""
        report += f"| {t['买入日期']} | {t['买入价']} | {t['卖出日期']} | {t['卖出价']} | {t['股数']} | {profit_mark}{t['盈亏']} | {profit_mark}{t['收益率%']}% |\n"

    report += f"""
## 风险提示

本报告仅为历史数据回测，不构成任何投资建议。过去的业绩不代表未来表现。
"""
    return report


def main():
    parser = argparse.ArgumentParser(description="策略回测工具")
    parser.add_argument("strategy", choices=["ma20"], help="策略名称")
    parser.add_argument("code", nargs="?", help="股票代码（不指定则用 --all）")
    parser.add_argument("--all", action="store_true", help="全市场回测")
    parser.add_argument("--top", type=int, default=50, help="全市场模式显示前N名（默认50）")
    parser.add_argument("-o", "--output", help="输出文件路径（.md）")
    args = parser.parse_args()

    if not args.code and not args.all:
        parser.print_help()
        print("\n请指定股票代码或使用 --all 进行全市场回测")
        sys.exit(1)

    con = get_db()

    if args.all:
        backtest_all(con, args.top)
    else:
        backtest_single(con, args.code, args.output)


if __name__ == "__main__":
    main()
