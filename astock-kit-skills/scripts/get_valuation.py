# -*- coding: utf-8 -*-
"""
获取股票估值指标

用法:
    python get_valuation.py 002475
"""
import argparse
import sys
import warnings
warnings.filterwarnings('ignore')

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print("请先安装依赖: pip install akshare pandas")
    sys.exit(1)

from cache_manager import cache_get, cache_set
from realtime_source import get_spot_dict


def get_code_with_prefix(code: str) -> str:
    if code.startswith('6'):
        return f"SH{code}"
    elif code.startswith(('0', '3')):
        return f"SZ{code}"
    return f"SZ{code}"


def get_valuation(code: str, use_cache: bool = True):
    """获取估值数据 (雪球接口)"""
    symbol = get_code_with_prefix(code)
    print(f"获取估值数据: {symbol}")
    
    # 缓存
    if use_cache:
        cached_data = cache_get('valuation', symbol)
        if cached_data:
            print("从缓存加载数据...")
            display_valuation(cached_data)
            return

    # 雪球 → 腾讯 回退（统一走共享模块）
    data, source = get_spot_dict(code, symbol)
    if data:
        print(f"（数据来源: {source}）")
        if source == '腾讯':
            print("注意: 腾讯源无动/静市盈率、股息率、每股指标，相关字段留空")
        display_valuation(data)
        if use_cache:
            cache_set('valuation', data, symbol)
    else:
        print("所有数据源均获取失败（雪球、腾讯）")


def display_valuation(data: dict):
    """显示估值信息"""
    print("-" * 30)
    print(f"股票名称: {data.get('名称', '')}")
    print(f"当前价格: {data.get('现价', '')}")
    print(f"涨跌幅:   {data.get('涨幅', '')}%")
    print("-" * 30)
    print(f"市盈率(动):  {data.get('市盈率(动)', '')}")
    print(f"市盈率(静):  {data.get('市盈率(静)', '')}")
    print(f"市盈率(TTM): {data.get('市盈率(TTM)', '')}")
    print(f"市净率:      {data.get('市净率', '')}")
    print("-" * 30)
    print(f"股息率(TTM): {data.get('股息率(TTM)', '')}%")
    print(f"每股收益:    {data.get('每股收益', '')}")
    print(f"每股净资产:  {data.get('每股净资产', '')}")
    print("-" * 30)


def main():
    parser = argparse.ArgumentParser(description='获取估值指标')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')
    
    args = parser.parse_args()
    
    get_valuation(args.code, use_cache=not args.no_cache)


if __name__ == '__main__':
    main()
