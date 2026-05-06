# -*- coding: utf-8 -*-
"""
技术指标计算模块

支持指标:
- MA: 均线 (5/10/20/60日)
- MACD: 指数平滑异同移动平均线
- RSI: 相对强弱指标
- KDJ: 随机指标
- BOLL: 布林带

用法:
    python calc_technical.py 002475
    python calc_technical.py 002475 --indicators MA MACD RSI
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("请先安装依赖: pip install pandas numpy")
    sys.exit(1)

# 本地数据路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
DAILY_FILE = os.path.join(DATA_DIR, "all_daily.parquet")


def calc_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
    """
    计算均线
    
    Args:
        df: K线数据，需包含 '收盘' 列
        periods: 均线周期列表
    
    Returns:
        添加均线列的 DataFrame
    """
    for period in periods:
        df[f'MA{period}'] = df['收盘'].rolling(window=period).mean()
    return df


def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    计算 MACD
    
    Args:
        df: K线数据
        fast: 快线周期
        slow: 慢线周期
        signal: 信号线周期
    
    Returns:
        添加 MACD 指标的 DataFrame
    """
    exp1 = df['收盘'].ewm(span=fast, adjust=False).mean()
    exp2 = df['收盘'].ewm(span=slow, adjust=False).mean()
    
    df['DIF'] = exp1 - exp2
    df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])
    
    return df


def calc_rsi(df: pd.DataFrame, periods: list = [6, 12, 24]) -> pd.DataFrame:
    """
    计算 RSI
    
    Args:
        df: K线数据
        periods: RSI 周期列表
    
    Returns:
        添加 RSI 指标的 DataFrame
    """
    delta = df['收盘'].diff()
    
    for period in periods:
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        df[f'RSI{period}'] = 100 - (100 / (1 + rs))
    
    return df


def calc_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """
    计算 KDJ
    
    Args:
        df: K线数据
        n: RSV 周期
        m1: K 平滑周期
        m2: D 平滑周期
    
    Returns:
        添加 KDJ 指标的 DataFrame
    """
    low_min = df['最低'].rolling(window=n).min()
    high_max = df['最高'].rolling(window=n).max()
    
    rsv = (df['收盘'] - low_min) / (high_max - low_min) * 100
    
    df['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/m2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    return df


def calc_boll(df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    """
    计算布林带
    
    Args:
        df: K线数据
        period: 中轨周期
        std_dev: 标准差倍数
    
    Returns:
        添加布林带的 DataFrame
    """
    df['BOLL_MID'] = df['收盘'].rolling(window=period).mean()
    std = df['收盘'].rolling(window=period).std()
    
    df['BOLL_UP'] = df['BOLL_MID'] + std_dev * std
    df['BOLL_DOWN'] = df['BOLL_MID'] - std_dev * std
    
    return df


def calc_volume_ratio(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
    """计算量比"""
    df['量比'] = df['成交量'] / df['成交量'].rolling(window=period).mean()
    return df


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标"""
    df = calc_ma(df)
    df = calc_macd(df)
    df = calc_rsi(df)
    df = calc_kdj(df)
    df = calc_boll(df)
    df = calc_volume_ratio(df)
    return df


def analyze_signals(df: pd.DataFrame) -> dict:
    """
    分析技术信号
    
    Returns:
        技术信号字典
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    signals = {}
    
    # 均线分析
    if 'MA5' in df.columns and 'MA20' in df.columns:
        if latest['MA5'] > latest['MA20'] and prev['MA5'] <= prev['MA20']:
            signals['均线'] = '🟢 金叉（MA5上穿MA20）'
        elif latest['MA5'] < latest['MA20'] and prev['MA5'] >= prev['MA20']:
            signals['均线'] = '🔴 死叉（MA5下穿MA20）'
        elif latest['收盘'] > latest['MA5'] > latest['MA20']:
            signals['均线'] = '🟢 多头排列'
        elif latest['收盘'] < latest['MA5'] < latest['MA20']:
            signals['均线'] = '🔴 空头排列'
        else:
            signals['均线'] = '⚪ 震荡'
    
    # MACD分析
    if 'DIF' in df.columns and 'DEA' in df.columns:
        if latest['DIF'] > latest['DEA'] and prev['DIF'] <= prev['DEA']:
            signals['MACD'] = '🟢 金叉'
        elif latest['DIF'] < latest['DEA'] and prev['DIF'] >= prev['DEA']:
            signals['MACD'] = '🔴 死叉'
        elif latest['MACD'] > 0:
            signals['MACD'] = '🟢 多头'
        else:
            signals['MACD'] = '🔴 空头'
    
    # RSI分析
    if 'RSI6' in df.columns:
        rsi = latest['RSI6']
        if rsi > 80:
            signals['RSI'] = f'🔴 超买 ({rsi:.1f})'
        elif rsi < 20:
            signals['RSI'] = f'🟢 超卖 ({rsi:.1f})'
        elif rsi > 50:
            signals['RSI'] = f'🟢 偏强 ({rsi:.1f})'
        else:
            signals['RSI'] = f'🔴 偏弱 ({rsi:.1f})'
    
    # KDJ分析
    if 'K' in df.columns and 'D' in df.columns:
        if latest['K'] > latest['D'] and prev['K'] <= prev['D'] and latest['K'] < 20:
            signals['KDJ'] = '🟢 低位金叉'
        elif latest['K'] < latest['D'] and prev['K'] >= prev['D'] and latest['K'] > 80:
            signals['KDJ'] = '🔴 高位死叉'
        elif latest['J'] > 100:
            signals['KDJ'] = f'🔴 超买 (J={latest["J"]:.1f})'
        elif latest['J'] < 0:
            signals['KDJ'] = f'🟢 超卖 (J={latest["J"]:.1f})'
        else:
            signals['KDJ'] = '⚪ 中性'
    
    # 布林带分析
    if 'BOLL_UP' in df.columns:
        if latest['收盘'] > latest['BOLL_UP']:
            signals['BOLL'] = '🔴 突破上轨（注意回调）'
        elif latest['收盘'] < latest['BOLL_DOWN']:
            signals['BOLL'] = '🟢 突破下轨（注意反弹）'
        else:
            width = (latest['BOLL_UP'] - latest['BOLL_DOWN']) / latest['BOLL_MID'] * 100
            signals['BOLL'] = f'⚪ 通道内 (带宽{width:.1f}%)'
    
    return signals


def format_output(df: pd.DataFrame, code: str, signals: dict) -> str:
    """格式化输出为 Markdown"""
    lines = [f"# {code} 技术分析\n"]
    
    latest = df.iloc[-1]
    
    # 信号汇总
    lines.append("## 技术信号\n")
    lines.append("| 指标 | 信号 |")
    lines.append("|------|------|")
    for name, signal in signals.items():
        lines.append(f"| {name} | {signal} |")
    lines.append("")
    
    # 指标数值
    lines.append("## 指标数值\n")
    lines.append("### 均线")
    lines.append("| MA5 | MA10 | MA20 | MA60 |")
    lines.append("|-----|------|------|------|")
    ma_vals = [f"{latest.get(f'MA{p}', 'N/A'):.2f}" if pd.notna(latest.get(f'MA{p}')) else 'N/A' for p in [5,10,20,60]]
    lines.append(f"| {' | '.join(ma_vals)} |")
    lines.append("")
    
    lines.append("### MACD")
    lines.append("| DIF | DEA | MACD |")
    lines.append("|-----|-----|------|")
    dif = f"{latest.get('DIF', 0):.3f}" if pd.notna(latest.get('DIF')) else 'N/A'
    dea = f"{latest.get('DEA', 0):.3f}" if pd.notna(latest.get('DEA')) else 'N/A'
    macd = f"{latest.get('MACD', 0):.3f}" if pd.notna(latest.get('MACD')) else 'N/A'
    lines.append(f"| {dif} | {dea} | {macd} |")
    lines.append("")
    
    lines.append("### RSI")
    lines.append("| RSI6 | RSI12 | RSI24 |")
    lines.append("|------|-------|-------|")
    rsi_vals = [f"{latest.get(f'RSI{p}', 'N/A'):.2f}" if pd.notna(latest.get(f'RSI{p}')) else 'N/A' for p in [6,12,24]]
    lines.append(f"| {' | '.join(rsi_vals)} |")
    lines.append("")
    
    lines.append("### KDJ")
    lines.append("| K | D | J |")
    lines.append("|---|---|---|")
    kdj_vals = [f"{latest.get(k, 'N/A'):.2f}" if pd.notna(latest.get(k)) else 'N/A' for k in ['K','D','J']]
    lines.append(f"| {' | '.join(kdj_vals)} |")
    lines.append("")
    
    lines.append("### 布林带")
    lines.append("| 上轨 | 中轨 | 下轨 |")
    lines.append("|------|------|------|")
    boll_vals = [f"{latest.get(k, 'N/A'):.2f}" if pd.notna(latest.get(k)) else 'N/A' for k in ['BOLL_UP','BOLL_MID','BOLL_DOWN']]
    lines.append(f"| {' | '.join(boll_vals)} |")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='计算技术指标')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--days', type=int, default=120, help='计算周期（天）')
    parser.add_argument('-o', '--output', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 获取K线数据：优先本地，回退在线
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y%m%d')
    df = None

    # 1. 尝试本地数据
    if os.path.exists(DAILY_FILE):
        try:
            import duckdb
            con = duckdb.connect()
            start_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
            end_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
            df = con.execute(f"""
                SELECT 日期, 开盘, 最高, 最低, 收盘, 成交量
                FROM read_parquet('{DAILY_FILE}')
                WHERE code = '{args.code}'
                  AND 日期 >= '{start_fmt}' AND 日期 <= '{end_fmt}'
                ORDER BY 日期
            """).fetchdf()
            con.close()
            if len(df) > 0:
                print(f"从本地数据加载: {len(df)} 条记录")
            else:
                df = None
        except Exception:
            df = None

    # 2. 回退在线（东方财富 → 网易163）
    if df is None:
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=args.code, period='daily',
                start_date=start_date, end_date=end_date, adjust='qfq'
            )
            if df is not None and not df.empty:
                print(f"从东方财富在线获取: {len(df)} 条记录")
        except Exception:
            pass

    if df is None:
        try:
            import akshare as ak
            sym = f"sz{args.code}" if args.code.startswith(('0', '3')) else f"sh{args.code}"
            df = ak.stock_zh_a_daily(symbol=sym, start_date=start_date, end_date=end_date, adjust='qfq')
            if df is not None and not df.empty:
                # 网易163 列名映射
                col_map = {'open': '开盘', 'high': '最高', 'low': '最低', 'close': '收盘', 'volume': '成交量'}
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                print(f"从网易163在线获取: {len(df)} 条记录")
        except Exception:
            pass

    if df is None or (hasattr(df, 'empty') and df.empty):
        print("所有数据源均获取失败")
        sys.exit(1)
    
    # 计算所有指标
    df = calc_all_indicators(df)
    
    # 分析信号
    signals = analyze_signals(df)
    
    # 格式化输出
    output = format_output(df, args.code, signals)
    print(output)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
