# -*- coding: utf-8 -*-
"""
智能投资分析

综合估值、成长性、资金面、技术面进行多维度分析

用法:
    python analyze_investment.py 002475
    python analyze_investment.py 002475 -o analysis.md
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
    import numpy as np
except ImportError:
    print("请先安装依赖: pip install akshare pandas numpy")
    sys.exit(1)

from calc_technical import calc_all_indicators, analyze_signals

# 本地数据路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "..", "data")
DAILY_FILE = os.path.join(DATA_DIR, "all_daily.parquet")


def get_code_with_prefix(code: str) -> str:
    if code.startswith('6'):
        return f"SH{code}"
    elif code.startswith(('0', '3')):
        return f"SZ{code}"
    return f"SZ{code}"


def get_market(code: str) -> str:
    return 'sh' if code.startswith('6') else 'sz'


class InvestmentAnalyzer:
    """投资分析器"""
    
    def __init__(self, code: str):
        self.code = code
        self.code_with_prefix = get_code_with_prefix(code)
        self.market = get_market(code)
        self.scores = {}
        self.analysis = {}
        self.data = {}
    
    def fetch_data(self):
        """获取所有需要的数据"""
        # 基本信息
        try:
            self.data['info'] = ak.stock_individual_info_em(symbol=self.code)
        except:
            pass
        
        # 实时行情（雪球，东方财富经常被封）
        try:
            xq_spot = ak.stock_individual_spot_xq(symbol=self.code_with_prefix)
            if xq_spot is not None:
                spot_data = dict(zip(xq_spot['item'], xq_spot['value']))
                self.data['spot'] = pd.Series({
                    '代码': self.code,
                    '名称': spot_data.get('名称', ''),
                    '最新价': spot_data.get('现价', 0),
                    '涨跌幅': spot_data.get('涨幅', 0),
                    '最高': spot_data.get('最高', 0),
                    '最低': spot_data.get('最低', 0),
                    '成交量': spot_data.get('成交量', 0),
                    '成交额': spot_data.get('成交额', 0),
                    '换手率': spot_data.get('换手率', 0),
                })
        except:
            pass

        # 历史K线（优先本地数据）
        try:
            end = datetime.now().strftime('%Y%m%d')
            start = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            kline = None

            # 本地数据
            if os.path.exists(DAILY_FILE):
                try:
                    import duckdb
                    con = duckdb.connect()
                    start_fmt = f"{start[:4]}-{start[4:6]}-{start[6:]}"
                    end_fmt = f"{end[:4]}-{end[4:6]}-{end[6:]}"
                    kline = con.execute(f"""
                        SELECT 日期, 开盘, 最高, 最低, 收盘, 成交量
                        FROM read_parquet('{DAILY_FILE}')
                        WHERE code = '{self.code}'
                          AND 日期 >= '{start_fmt}' AND 日期 <= '{end_fmt}'
                        ORDER BY 日期
                    """).fetchdf()
                    con.close()
                    if len(kline) == 0:
                        kline = None
                except:
                    kline = None

            # 回退在线
            if kline is None:
                kline = ak.stock_zh_a_hist(symbol=self.code, period='daily', start_date=start, end_date=end, adjust='qfq')

            self.data['kline'] = kline
        except:
            pass
        
        # 雪球估值
        try:
            xq = ak.stock_individual_spot_xq(symbol=self.code_with_prefix)
            self.data['valuation'] = dict(zip(xq['item'], xq['value'])) if xq is not None else {}
        except:
            pass
        
        # 资金流向
        try:
            self.data['fund_flow'] = ak.stock_individual_fund_flow(stock=self.code, market=self.market)
        except:
            pass
        
        # 财务数据（排序取最新）
        try:
            fin = ak.stock_financial_abstract_ths(symbol=self.code, indicator="按报告期")
            if fin is not None and not fin.empty and '报告期' in fin.columns:
                fin = fin.sort_values('报告期', ascending=False).reset_index(drop=True)
            self.data['financial'] = fin
        except:
            pass
    
    def analyze_valuation(self) -> dict:
        """估值分析"""
        result = {'score': 50, 'signals': []}
        
        val = self.data.get('valuation', {})
        spot = self.data.get('spot')
        
        if spot is not None:
            pe = spot.get('市盈率-动态', 0)
            pb = spot.get('市净率', 0)
            
            if pe and pe > 0:
                if pe < 15:
                    result['score'] += 20
                    result['signals'].append('🟢 PE<15，估值较低')
                elif pe < 25:
                    result['score'] += 10
                    result['signals'].append('🟡 PE适中 (15-25)')
                elif pe < 40:
                    result['signals'].append('🟡 PE偏高 (25-40)')
                else:
                    result['score'] -= 10
                    result['signals'].append('🔴 PE>40，估值较高')
            
            if pb and pb > 0:
                if pb < 2:
                    result['score'] += 10
                    result['signals'].append('🟢 PB<2，价值凸显')
                elif pb > 5:
                    result['score'] -= 5
                    result['signals'].append('🔴 PB>5，溢价较高')
        
        # 股息率
        dv = val.get('股息率(TTM)')
        if dv and isinstance(dv, (int, float)) and dv > 2:
            result['score'] += 10
            result['signals'].append(f'🟢 股息率{dv:.2f}%，有分红价值')
        
        self.analysis['valuation'] = result
        return result
    
    def analyze_growth(self) -> dict:
        """成长性分析"""
        result = {'score': 50, 'signals': []}
        
        fina = self.data.get('financial')
        if fina is not None and len(fina) > 0:
            latest = fina.iloc[0]
            
            # 营收增速
            rev_growth = latest.get('营业总收入同比增长率')
            if rev_growth and str(rev_growth) not in ['False', 'nan']:
                try:
                    growth = float(str(rev_growth).replace('%', ''))
                    if growth > 30:
                        result['score'] += 25
                        result['signals'].append(f'🟢 营收增速{growth:.1f}%，高增长')
                    elif growth > 15:
                        result['score'] += 15
                        result['signals'].append(f'🟢 营收增速{growth:.1f}%，稳健增长')
                    elif growth > 0:
                        result['score'] += 5
                        result['signals'].append(f'🟡 营收增速{growth:.1f}%')
                    else:
                        result['score'] -= 10
                        result['signals'].append(f'🔴 营收负增长{growth:.1f}%')
                except:
                    pass
            
            # 净利润增速
            profit_growth = latest.get('净利润同比增长率')
            if profit_growth and str(profit_growth) not in ['False', 'nan']:
                try:
                    growth = float(str(profit_growth).replace('%', ''))
                    if growth > 30:
                        result['score'] += 25
                        result['signals'].append(f'🟢 净利润增速{growth:.1f}%，高增长')
                    elif growth > 15:
                        result['score'] += 15
                        result['signals'].append(f'🟢 净利润增速{growth:.1f}%，稳健')
                    elif growth < 0:
                        result['score'] -= 15
                        result['signals'].append(f'🔴 净利润负增长{growth:.1f}%')
                except:
                    pass
        
        self.analysis['growth'] = result
        return result
    
    def analyze_fund_flow(self) -> dict:
        """资金面分析"""
        result = {'score': 50, 'signals': []}
        
        flow = self.data.get('fund_flow')
        if flow is not None and len(flow) > 0 and '主力净流入-净额' in flow.columns:
            recent = flow.tail(10)
            total = recent['主力净流入-净额'].sum()
            latest = recent['主力净流入-净额'].iloc[-1]
            recent_3 = recent['主力净流入-净额'].tail(3).sum()
            
            # 整体趋势
            if total > 0:
                result['score'] += 15
                result['signals'].append(f'🟢 近10日主力净流入{total/1e8:.2f}亿')
            else:
                result['score'] -= 10
                result['signals'].append(f'🔴 近10日主力净流出{abs(total)/1e8:.2f}亿')
            
            # 近期趋势
            if recent_3 > 0 and latest > 0:
                result['score'] += 10
                result['signals'].append('🟢 资金持续流入')
            elif recent_3 < 0 and latest < 0:
                result['score'] -= 10
                result['signals'].append('🔴 资金持续流出')
        
        self.analysis['fund_flow'] = result
        return result
    
    def analyze_technical(self) -> dict:
        """技术面分析"""
        result = {'score': 50, 'signals': []}
        
        kline = self.data.get('kline')
        if kline is not None and len(kline) > 60:
            kline = calc_all_indicators(kline)
            signals = analyze_signals(kline)
            
            for name, signal in signals.items():
                result['signals'].append(f"{name}: {signal}")
                if '🟢' in signal:
                    result['score'] += 5
                elif '🔴' in signal:
                    result['score'] -= 5
        
        self.analysis['technical'] = result
        return result
    
    def get_total_score(self) -> int:
        """计算综合评分"""
        scores = []
        weights = {'valuation': 0.3, 'growth': 0.3, 'fund_flow': 0.2, 'technical': 0.2}
        
        for key, weight in weights.items():
            if key in self.analysis:
                scores.append(self.analysis[key]['score'] * weight)
        
        return int(sum(scores)) if scores else 50
    
    def get_recommendation(self, score: int) -> str:
        """根据评分给出建议"""
        if score >= 80:
            return "🟢 **强烈推荐买入** - 多项指标优秀，具备较好的投资价值"
        elif score >= 65:
            return "🟢 **推荐买入** - 整体表现良好，可择机介入"
        elif score >= 50:
            return "🟡 **谨慎持有** - 表现一般，建议观望或小仓位"
        elif score >= 35:
            return "🔴 **不建议买入** - 多项指标偏弱，需要等待更好时机"
        else:
            return "🔴 **建议回避** - 风险较大，不宜介入"
    
    def generate_report(self) -> str:
        """生成分析报告"""
        self.fetch_data()
        self.analyze_valuation()
        self.analyze_growth()
        self.analyze_fund_flow()
        self.analyze_technical()
        
        total_score = self.get_total_score()
        recommendation = self.get_recommendation(total_score)
        
        # 生成Markdown报告
        spot = self.data.get('spot')
        name = spot['名称'] if spot is not None else self.code
        
        lines = [
            f"# {name} ({self.code}) 投资分析报告\n",
            f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
            "---\n",
            f"## 📊 综合评分: {total_score}/100\n",
            f"{recommendation}\n",
            "---\n"
        ]
        
        # 各维度分析
        dimension_names = {
            'valuation': '💰 估值分析',
            'growth': '📈 成长性分析',
            'fund_flow': '💵 资金面分析',
            'technical': '📉 技术面分析'
        }
        
        for key, name in dimension_names.items():
            if key in self.analysis:
                data = self.analysis[key]
                lines.append(f"### {name} (得分: {data['score']})\n")
                for signal in data['signals']:
                    lines.append(f"- {signal}")
                lines.append("")
        
        # 基本信息（兼容雪球和东方财富两种字段名）
        if spot is not None:
            lines.append("---\n")
            lines.append("## 📋 基本信息\n")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            price = spot.get('最新价', spot.get('现价', ''))
            change = spot.get('涨跌幅', spot.get('涨幅%', ''))
            pe = spot.get('市盈率-动态', spot.get('市盈率(TTM)', ''))
            pb = spot.get('市净率', '')
            lines.append(f"| 最新价 | {price} 元 |")
            lines.append(f"| 涨跌幅 | {change}% |")
            if '总市值' in spot and spot['总市值']:
                lines.append(f"| 总市值 | {float(spot['总市值'])/1e8:.2f} 亿 |")
            lines.append(f"| 市盈率 | {pe} |")
            lines.append(f"| 市净率 | {pb} |")
        
        lines.append("\n---\n")
        lines.append("> ⚠️ 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='智能投资分析')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('-o', '--output', help='输出文件路径')
    
    args = parser.parse_args()
    
    analyzer = InvestmentAnalyzer(args.code)
    report = analyzer.generate_report()
    
    print(report)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n已保存至: {args.output}")


if __name__ == '__main__':
    main()
