# -*- coding: utf-8 -*-
"""
实时行情共享数据源（雪球 → 腾讯 → 东财 → 新浪 四级回退）

所有需要实时行情/估值的脚本统一调用本模块，避免回退逻辑散落各处、
改了一个忘了其他（历史教训：雪球失效后多个脚本同时报错）。

数据源顺序（按字段丰富度 + 稳定性排）：
  1. 雪球（自写预热）—— 字段最全（动/静/TTM PE、股息率、每股收益/净资产、52 周高低）
  2. 腾讯财经 qt.gtimg.cn —— 国内直连最稳，行情字段 + PE(TTM)/PB
  3. 东方财富 push2/stock/get —— 行情字段 + 换手/量比，无估值
  4. 新浪 hq.sinajs.cn —— 仅基础行情，最后兜底

> **雪球为什么自写预热**：AKShare 的 `stock_individual_spot_xq` 内置了一个写死的
> `xq_a_token`（`akshare/stock/cons.py`），该 token 会过期，过期后返回
> `error_code 400016`。本模块不依赖 akshare 那个常量，而是先访问 `xueqiu.com`
> 让服务器**现发一个新 cookie**，再带新 cookie 请求行情，避免被旧 token 连累。

统一返回「雪球键风格」的 dict，例如 {'名称':..., '现价':..., '市盈率(TTM)':..., '市净率':...}，
这样各调用方原有的 data.get('雪球字段') 逻辑无需改动——某源缺的字段自动取默认值。

用法：
    from realtime_source import get_spot_dict
    data, source = get_spot_dict('600519', 'SH600519')
    # data 是雪球键风格 dict；source 是 '雪球'/'腾讯'/'东财'/'新浪'/None（全失败）
"""
import warnings
warnings.filterwarnings('ignore')

try:
    import requests
except ImportError:
    requests = None

_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1")

# 雪球键风格的完整字段集（其他源没有的字段统一留空，保证下游 .get 不报错）
_XQ_KEYS = [
    '名称', '现价', '涨幅', '最高', '最低', '今开', '昨收',
    '成交量', '成交额', '换手率',
    '市盈率(动)', '市盈率(静)', '市盈率(TTM)', '市净率',
    '每股收益', '每股净资产', '股息率(TTM)',
    '52周最高', '52周最低', '今年以来涨幅',
]


def _to_float(s):
    """安全转 float，失败返回原值。"""
    try:
        return round(float(s), 4)
    except (ValueError, TypeError):
        return s


def _blank_dict():
    return {k: '' for k in _XQ_KEYS}


def get_tencent_prefix(code: str) -> str:
    """腾讯/新浪格式前缀（sh/sz 小写）。"""
    return f"sh{code}" if code.startswith('6') else f"sz{code}"


# ---------- 1. 雪球（自写预热，不用 akshare 写死的旧 token） ----------
def fetch_from_xueqiu(code_with_prefix: str):
    """
    雪球行情，返回雪球键风格 dict（字段最全）。
    先访问 xueqiu.com 拿服务器现发的新 cookie，再请求行情，规避旧 token 过期。
    """
    if requests is None:
        return None
    s = requests.Session()
    s.headers['User-Agent'] = _UA
    s.get('https://xueqiu.com', timeout=8)  # 预热：让服务器种新 xq_a_token cookie
    url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={code_with_prefix}&extend=detail"
    j = s.get(url, timeout=8).json()
    if not j.get('data') or not j['data'].get('quote'):
        return None
    q = j['data']['quote']
    data = _blank_dict()
    data.update({
        '名称': q.get('name', ''),
        '现价': _to_float(q.get('current')),
        '涨幅': _to_float(q.get('percent')),
        '最高': _to_float(q.get('high')),
        '最低': _to_float(q.get('low')),
        '今开': _to_float(q.get('open')),
        '昨收': _to_float(q.get('last_close')),
        '成交量': _to_float(q.get('volume')),       # 单位:股
        '成交额': _to_float(q.get('amount')),       # 单位:元
        '换手率': _to_float(q.get('turnover_rate')),
        '市盈率(动)': _to_float(q.get('pe_forecast')),
        '市盈率(静)': _to_float(q.get('pe_lyr')),
        '市盈率(TTM)': _to_float(q.get('pe_ttm')),
        '市净率': _to_float(q.get('pb')),
        '每股收益': _to_float(q.get('eps')),
        '每股净资产': _to_float(q.get('navps')),
        '股息率(TTM)': _to_float(q.get('dividend_yield')),
        '52周最高': _to_float(q.get('high52w')),
        '52周最低': _to_float(q.get('low52w')),
        '今年以来涨幅': _to_float(q.get('current_year_percent')),
    })
    return data


# ---------- 2. 腾讯财经 qt.gtimg.cn（自写 HTTP） ----------
def fetch_from_tencent(code: str):
    """
    腾讯财经行情（qt.gtimg.cn），GBK、~ 分隔。返回雪球键风格 dict。
    字段位置实测核对：
      1=名称 3=现价 4=昨收 5=今开 6=成交量(手) 31=涨跌额 32=涨幅%
      33=最高 34=最低 37=成交额(万) 38=换手率% 39=市盈率TTM 46=市净率
    """
    if requests is None:
        return None
    url = f"https://qt.gtimg.cn/q={get_tencent_prefix(code)}"
    resp = requests.get(url, timeout=8, headers={'User-Agent': _UA})
    resp.encoding = 'gbk'
    text = resp.text
    if '="' not in text:
        return None
    body = text.split('="', 1)[1].rsplit('"', 1)[0]
    f = body.split('~')
    if len(f) < 46 or not f[1]:
        return None
    data = _blank_dict()
    data.update({
        '名称': f[1],
        '现价': _to_float(f[3]),
        '涨幅': _to_float(f[32]),
        '最高': _to_float(f[33]),
        '最低': _to_float(f[34]),
        '今开': _to_float(f[5]),
        '昨收': _to_float(f[4]),
        '成交量': _to_float(f[6]),       # 单位:手
        '成交额': _to_float(f[37]),      # 单位:万元
        '换手率': _to_float(f[38]),
        '市盈率(TTM)': _to_float(f[39]),
        '市净率': _to_float(f[46]) if len(f) > 46 else '',
    })
    return data


# ---------- 3. 东方财富 push2/stock/get（单只，行情+换手/量比，无估值） ----------
def fetch_from_eastmoney(code: str):
    """
    东方财富行情报价（push2.eastmoney.com/api/qt/stock/get），单只。
    注意：东财反爬激进，此接口可能限流/断连，故排在腾讯之后。
    f43=现价 f44=最高 f45=最低 f46=今开 f60=昨收 f47=成交量(手)
    f48=成交额 f168=换手率 f170=涨幅 f169=涨跌额
    """
    if requests is None:
        return None
    market_code = 1 if code.startswith('6') else 0
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "fltt": "2", "invt": "2",
        "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f168,f169,f170",
        "secid": f"{market_code}.{code}",
    }
    j = requests.get(url, params=params, timeout=8, headers={'User-Agent': _UA}).json()
    d = j.get('data')
    if not d or d.get('f43') in (None, '-'):
        return None
    data = _blank_dict()
    data.update({
        '名称': d.get('f58', ''),
        '现价': _to_float(d.get('f43')),
        '涨幅': _to_float(d.get('f170')),
        '最高': _to_float(d.get('f44')),
        '最低': _to_float(d.get('f45')),
        '今开': _to_float(d.get('f46')),
        '昨收': _to_float(d.get('f60')),
        '成交量': _to_float(d.get('f47')),   # 单位:手
        '成交额': _to_float(d.get('f48')),   # 单位:元
        '换手率': _to_float(d.get('f168')),
    })
    return data


# ---------- 4. 新浪 hq.sinajs.cn（单只，仅基础行情，最后兜底） ----------
def fetch_from_sina(code: str):
    """
    新浪行情（hq.sinajs.cn/list=），GBK、逗号分隔。返回雪球键风格 dict。
    需要带 Referer，否则被拒。字段位置实测核对：
      0=名称 1=今开 2=昨收 3=现价 4=最高 5=最低 8=成交量(股) 9=成交额(元)
    新浪此接口无估值字段（PE/PB/股息），仅基础行情。
    """
    if requests is None:
        return None
    url = f"https://hq.sinajs.cn/list={get_tencent_prefix(code)}"
    resp = requests.get(url, timeout=8,
                        headers={'User-Agent': _UA, 'Referer': 'https://finance.sina.com.cn'})
    resp.encoding = 'gbk'
    text = resp.text
    if '"' not in text:
        return None
    body = text.split('"')[1]
    f = body.split(',')
    if len(f) < 10 or not f[0]:
        return None
    last_close = _to_float(f[2])
    current = _to_float(f[3])
    # 新浪不直接给涨幅，用 (现价-昨收)/昨收 算
    pct = ''
    try:
        if last_close:
            pct = round((current - last_close) / last_close * 100, 4)
    except (TypeError, ZeroDivisionError):
        pct = ''
    data = _blank_dict()
    data.update({
        '名称': f[0],
        '现价': current,
        '涨幅': pct,
        '最高': _to_float(f[4]),
        '最低': _to_float(f[5]),
        '今开': _to_float(f[1]),
        '昨收': last_close,
        '成交量': _to_float(f[8]),   # 单位:股
        '成交额': _to_float(f[9]),   # 单位:元
    })
    return data


# 回退链（顺序即优先级）
_SOURCES = [
    ('雪球', lambda code, cwp: fetch_from_xueqiu(cwp)),
    ('腾讯', lambda code, cwp: fetch_from_tencent(code)),
    ('东财', lambda code, cwp: fetch_from_eastmoney(code)),
    ('新浪', lambda code, cwp: fetch_from_sina(code)),
]


def get_spot_dict(code: str, code_with_prefix: str = None):
    """
    获取实时行情/估值，四级回退：雪球 → 腾讯 → 东财 → 新浪。

    Args:
        code: 6 位代码，如 '600519'
        code_with_prefix: 雪球格式（SH/SZ 大写），不传则自动推断

    Returns:
        (data, source)
        data: 雪球键风格 dict；全部数据源失败时为 {}
        source: '雪球'/'腾讯'/'东财'/'新浪'/None
    """
    if code_with_prefix is None:
        code_with_prefix = f"SH{code}" if code.startswith('6') else f"SZ{code}"

    for name, fetch in _SOURCES:
        try:
            data = fetch(code, code_with_prefix)
            if data:
                return data, name
        except Exception:
            continue

    return {}, None


if __name__ == '__main__':
    import sys
    codes = sys.argv[1:] or ['600519', '000001']
    for c in codes:
        d, src = get_spot_dict(c)
        print(f"\n=== {c}  (来源: {src}) ===")
        if d:
            for k in ['名称', '现价', '涨幅', '市盈率(TTM)', '市净率', '股息率(TTM)', '52周最高']:
                print(f"  {k}: {d.get(k, '')}")
        else:
            print("  所有数据源均获取失败")
