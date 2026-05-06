# -*- coding: utf-8 -*-
"""
AKShare 个股综合分析脚本

使用方法:
    python stock_analyzer.py <股票代码> [--output <输出文件>]

示例:
    python stock_analyzer.py 002475
    python stock_analyzer.py 600519 --output 茅台分析.txt
"""
import argparse
import os
import sys
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("请先安装依赖: pip install akshare pandas")
    sys.exit(1)

# 本地数据路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data")
DAILY_FILE = os.path.join(DATA_DIR, "all_daily.parquet")

# 配置 pandas 显示选项
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_rows', 50)


def get_stock_code_with_prefix(code: str) -> str:
    """
    将纯数字股票代码转换为带交易所前缀的格式

    Args:
        code: 6位股票代码，如 "002475"

    Returns:
        带前缀的代码，如 "SZ002475"
    """
    code = code.strip()
    if code.startswith('6'):
        return f"SH{code}"
    elif code.startswith(('0', '3')):
        return f"SZ{code}"
    elif code.startswith(('4', '8')):
        return f"BJ{code}"  # 北交所
    else:
        return f"SZ{code}"


def get_market(code: str) -> str:
    """
    根据代码获取市场标识

    Args:
        code: 股票代码

    Returns:
        市场标识 "sh" 或 "sz"
    """
    if code.startswith('6'):
        return 'sh'
    else:
        return 'sz'


def analyze_stock(code: str, output_file: str = None):
    """
    综合分析单只股票

    Args:
        code: 股票代码（6位数字）
        output_file: 可选，输出文件路径
    """
    results = []

    def log(msg: str):
        """记录输出"""
        print(msg)
        results.append(msg)

    code = code.strip()
    code_with_prefix = get_stock_code_with_prefix(code)
    market = get_market(code)

    log("=" * 70)
    log("股票综合分析报告")
    log(f"股票代码: {code}")
    log(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    # 1-2. 基本信息 + 实时行情（合并用雪球接口）
    log("\n【1. 基本信息 & 实时行情】")
    log("-" * 50)
    try:
        xq = ak.stock_individual_spot_xq(symbol=code_with_prefix)
        if xq is not None and not xq.empty:
            data = dict(zip(xq['item'], xq['value']))
            log(f"股票名称: {data.get('名称', '')}")
            log(f"现价: {data.get('现价', '')}")
            log(f"涨跌幅: {data.get('涨幅', '')}%")
            log(f"最高: {data.get('最高', '')}")
            log(f"最低: {data.get('最低', '')}")
            log(f"今开: {data.get('今开', '')}")
            log(f"昨收: {data.get('昨收', '')}")
            log(f"成交量: {data.get('成交量', '')}")
            log(f"成交额: {data.get('成交额', '')}")
            log(f"换手率: {data.get('换手率', '')}")
            log(f"市盈率(动态): {data.get('市盈率(动)', '')}")
            log(f"市盈率(TTM): {data.get('市盈率(TTM)', '')}")
            log(f"市净率: {data.get('市净率', '')}")
            log(f"股息率(TTM): {data.get('股息率(TTM)', '')}%")
            log(f"52周最高: {data.get('52周最高', '')}")
            log(f"52周最低: {data.get('52周最低', '')}")
            log(f"今年以来涨幅: {data.get('今年以来涨幅', '')}%")
        else:
            log("无法获取数据")
    except Exception as e:
        log(f"获取失败: {e}")

    # 3. 近期K线走势
    log("\n【3. 近期K线走势（最近30个交易日）】")
    log("-" * 50)
    try:
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=60)).strftime('%Y%m%d')
        hist = None

        # 优先本地数据
        if os.path.exists(DAILY_FILE):
            try:
                import duckdb
                con = duckdb.connect()
                s = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
                e = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
                hist = con.execute(f"""
                    SELECT 日期, 开盘, 最高, 最低, 收盘, 成交量, 成交额
                    FROM read_parquet('{DAILY_FILE}')
                    WHERE code = '{code}' AND 日期 >= '{s}' AND 日期 <= '{e}'
                    ORDER BY 日期
                """).fetchdf()
                con.close()
                if len(hist) == 0:
                    hist = None
                else:
                    log(f"（数据来源: 本地 BaoStock）")
            except:
                hist = None

        # 回退在线
        if hist is None:
            hist = ak.stock_zh_a_hist(symbol=code, period="daily",
                                       start_date=start_date, end_date=end_date, adjust="qfq")

        if hist is not None and len(hist) > 0:
            log(hist.tail(30).to_string(index=False))

            # 统计摘要
            recent = hist.tail(30)
            log("\n--- 近30日统计 ---")
            log(f"最新收盘价: {recent['收盘'].iloc[-1]:.2f}")
            log(f"期间最高价: {recent['最高'].max():.2f}")
            log(f"期间最低价: {recent['最低'].min():.2f}")
            if len(recent) > 1:
                change = ((recent['收盘'].iloc[-1] / recent['收盘'].iloc[0]) - 1) * 100
                log(f"期间涨跌幅: {change:.2f}%")
            log(f"日均成交量: {recent['成交量'].mean() / 10000:.2f}万手")
            log(f"日均成交额: {recent['成交额'].mean() / 1e8:.2f}亿元")
            log(f"日均换手率: {recent['换手率'].mean():.2f}%")
        else:
            log("无历史数据")
    except Exception as e:
        log(f"获取K线数据失败: {e}")

    # 4. 估值指标 (使用雪球数据)
    log("\n【4. 估值指标】")
    log("-" * 50)
    try:
        # 使用雪球接口获取详细估值数据
        xq_data = ak.stock_individual_spot_xq(symbol=code_with_prefix)
        if xq_data is not None and len(xq_data) > 0:
            # 转换为字典便于查询
            xq_dict = dict(zip(xq_data['item'], xq_data['value']))
            log(f"市盈率(动态): {xq_dict.get('市盈率(动)', 'N/A')}")
            log(f"市盈率(静态): {xq_dict.get('市盈率(静)', 'N/A')}")
            log(f"市盈率(TTM): {xq_dict.get('市盈率(TTM)', 'N/A')}")
            log(f"市净率(PB): {xq_dict.get('市净率', 'N/A')}")
            log(f"每股收益: {xq_dict.get('每股收益', 'N/A')}")
            log(f"每股净资产: {xq_dict.get('每股净资产', 'N/A')}")
            log(f"股息率(TTM): {xq_dict.get('股息率(TTM)', 'N/A')}%")
            log(f"52周最高: {xq_dict.get('52周最高', 'N/A')}")
            log(f"52周最低: {xq_dict.get('52周最低', 'N/A')}")
            log(f"今年以来涨幅: {xq_dict.get('今年以来涨幅', 'N/A')}%")
        else:
            log("无估值数据")
    except Exception as e:
        log(f"获取估值指标失败: {e}")

    # 5. 资金流向
    log("\n【5. 资金流向（最近10日）】")
    log("-" * 50)
    try:
        fund_flow = ak.stock_individual_fund_flow(stock=code, market=market)
        if fund_flow is not None and len(fund_flow) > 0:
            log(fund_flow.tail(10).to_string(index=False))

            # 统计摘要
            recent_flow = fund_flow.tail(10)
            log("\n--- 近10日资金流统计 ---")
            if '主力净流入-净额' in recent_flow.columns:
                total_main = recent_flow['主力净流入-净额'].sum()
                log(f"主力净流入合计: {total_main / 1e8:.2f}亿")
        else:
            log("无资金流向数据")
    except Exception as e:
        log(f"获取资金流向失败: {e}")

    # 6. 十大股东 (使用 stock_main_stock_holder)
    log("\n【6. 主要股东】")
    log("-" * 50)
    try:
        holders = ak.stock_main_stock_holder(stock=code)
        if holders is not None and len(holders) > 0:
            # 获取最新一期的股东数据
            latest_date = holders['截至日期'].max()
            latest_holders = holders[holders['截至日期'] == latest_date]
            log(f"截至日期: {latest_date}")
            log(f"股东总数: {latest_holders['股东总数'].iloc[0]}")
            log(f"平均持股数: {latest_holders['平均持股数'].iloc[0]}")
            log("")
            # 显示前10大股东
            display_cols = ['编号', '股东名称', '持股数量', '持股比例', '股本性质']
            available_cols = [c for c in display_cols if c in latest_holders.columns]
            log(latest_holders[available_cols].head(10).to_string(index=False))
        else:
            log("无股东数据")
    except Exception as e:
        log(f"获取股东数据失败: {e}")

    # 7. 历史分红
    log("\n【7. 历史分红记录】")
    log("-" * 50)
    try:
        dividend = ak.stock_history_dividend_detail(symbol=code, indicator="分红")
        if dividend is not None and len(dividend) > 0:
            log(dividend.head(10).to_string(index=False))
        else:
            log("无分红记录")
    except Exception as e:
        log(f"获取分红数据失败: {e}")

    # 8. 财务指标 (使用同花顺接口)
    log("\n【8. 财务指标】")
    log("-" * 50)
    try:
        # 使用同花顺财务摘要接口
        fina = ak.stock_financial_abstract_ths(symbol=code, indicator="按报告期")
        if fina is not None and len(fina) > 0:
            if '报告期' in fina.columns:
                fina = fina.sort_values('报告期', ascending=False).reset_index(drop=True)
            latest = fina.iloc[0]
            log(f"报告期: {latest.get('报告期', 'N/A')}")
            log(f"净利润: {latest.get('净利润', 'N/A')}")
            log(f"净利润同比增长率: {latest.get('净利润同比增长率', 'N/A')}")
            log(f"扣非净利润: {latest.get('扣非净利润', 'N/A')}")
            log(f"营业总收入: {latest.get('营业总收入', 'N/A')}")
            log(f"营业总收入同比增长率: {latest.get('营业总收入同比增长率', 'N/A')}")
            log(f"基本每股收益: {latest.get('基本每股收益', 'N/A')}")
            log(f"每股净资产: {latest.get('每股净资产', 'N/A')}")
            log(f"每股经营现金流: {latest.get('每股经营现金流', 'N/A')}")
            log(f"销售净利率: {latest.get('销售净利率', 'N/A')}")
            log(f"销售毛利率: {latest.get('销售毛利率', 'N/A')}")
            log(f"净资产收益率: {latest.get('净资产收益率', 'N/A')}")
            log(f"资产负债率: {latest.get('资产负债率', 'N/A')}")
        else:
            log("无财务指标数据")
    except Exception as e:
        log(f"获取财务指标失败: {e}")

    log("\n" + "=" * 70)
    log("分析完成")
    log("=" * 70)

    # 保存到文件
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
        print(f"\n分析报告已保存至: {output_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='AKShare 个股综合分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
    python stock_analyzer.py 002475
    python stock_analyzer.py 600519 --output 茅台分析.txt
    python stock_analyzer.py 000001 -o 平安银行分析.txt
        '''
    )
    parser.add_argument('code', help='股票代码（6位数字），如 002475')
    parser.add_argument('-o', '--output', help='输出文件路径（可选）')

    args = parser.parse_args()

    analyze_stock(args.code, args.output)


if __name__ == '__main__':
    main()
