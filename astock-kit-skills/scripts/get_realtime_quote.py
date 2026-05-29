# -*- coding: utf-8 -*-
"""
获取股票实时行情

用法:
    python get_realtime_quote.py 002475
    python get_realtime_quote.py 002475 600519

数据源统一走 realtime_source（雪球 → 腾讯 → 东财 → 新浪 四级回退）。
"""
import argparse
import sys
import warnings
warnings.filterwarnings('ignore')

try:
    import pandas as pd
except ImportError:
    print("请先安装依赖: pip install pandas requests")
    sys.exit(1)

from cache_manager import cache_get, cache_set
from realtime_source import get_spot_dict


def get_code_with_prefix(code: str) -> str:
    """股票代码加前缀（雪球格式）"""
    if code.startswith('6'):
        return f"SH{code}"
    elif code.startswith(('0', '3')):
        return f"SZ{code}"
    return f"SZ{code}"


def get_realtime_quote(codes: list, use_cache: bool = True):
    """获取实时行情（雪球 → 腾讯 → 东财 → 新浪 四级回退，统一走共享模块）"""
    print("正在获取实时行情...")

    results = []
    for code in codes:
        symbol = get_code_with_prefix(code)
        cache_key = f"realtime_{symbol}"

        # 尝试缓存
        if use_cache:
            cached_data = cache_get('realtime', cache_key)
            if cached_data:
                results.append(cached_data)
                continue

        data, source = get_spot_dict(code, symbol)
        if data:
            row = {
                '代码': code,
                '名称': data.get('名称', ''),
                '现价': data.get('现价', ''),
                '涨幅%': data.get('涨幅', ''),
                '最高': data.get('最高', ''),
                '最低': data.get('最低', ''),
                '今开': data.get('今开', ''),
                '昨收': data.get('昨收', ''),
                '成交量': data.get('成交量', ''),
                '成交额': data.get('成交额', ''),
                '换手率': data.get('换手率', ''),
                '市盈率(TTM)': data.get('市盈率(TTM)', ''),
                '市净率': data.get('市净率', ''),
                '52周最高': data.get('52周最高', ''),
                '52周最低': data.get('52周最低', ''),
                '来源': source,
            }
            results.append(row)
            if use_cache:
                cache_set('realtime', row, cache_key)
        else:
            print(f"  {code}: 所有数据源均获取失败（雪球、腾讯、东财、新浪）")

    if results:
        result_df = pd.DataFrame(results)
        print(result_df.to_markdown(index=False))
    else:
        print("未获取到任何数据")


def main():
    parser = argparse.ArgumentParser(description='获取实时行情')
    parser.add_argument('codes', nargs='+', help='股票代码列表')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')

    args = parser.parse_args()

    get_realtime_quote(args.codes, use_cache=not args.no_cache)


if __name__ == '__main__':
    main()
