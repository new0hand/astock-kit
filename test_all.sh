#!/bin/bash
# ============================================================
# astock-kit 全功能测试脚本
# 按客户需求逐条测试，从简单到复杂
# ============================================================

set -e

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
SKIP=0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL="$SCRIPT_DIR/astock-kit-skills/local"
SKILL="$SCRIPT_DIR/astock-kit-skills/scripts"

# 测试用股票
STOCK="000001"        # 平安银行（便宜，方便回测）
STOCK2="600519"       # 贵州茅台（贵，测高价股）
STOCK3="002475"       # 立讯精密（config.yaml 里的监控股）

run_test() {
    local num="$1"
    local name="$2"
    local cmd="$3"
    local timeout="${4:-60}"
    local fail_pattern="${5:-}"  # 可选：输出包含该关键词则判定为失败

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}测试 #${num}: ${name}${NC}"
    echo -e "${YELLOW}命令: ${cmd}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # macOS 没有 timeout，用 gtimeout（brew install coreutils）或直接跑
    local TIMEOUT_CMD=""
    if command -v gtimeout &>/dev/null; then
        TIMEOUT_CMD="gtimeout $timeout"
    elif command -v timeout &>/dev/null; then
        TIMEOUT_CMD="timeout $timeout"
    fi

    local output
    output=$($TIMEOUT_CMD bash -c "$cmd" 2>&1)
    local exit_code=$?

    echo "$output"

    if [ $exit_code -eq 124 ]; then
        echo -e "\n${RED}⏰ #${num} 超时（${timeout}s）${NC}"
        FAIL=$((FAIL + 1))
    elif [ $exit_code -ne 0 ]; then
        echo -e "\n${RED}❌ #${num} 失败 (exit=$exit_code)${NC}"
        FAIL=$((FAIL + 1))
    elif [ -n "$fail_pattern" ] && echo "$output" | grep -qiE "$fail_pattern"; then
        echo -e "\n${RED}❌ #${num} 数据获取失败（脚本没崩但数据为空或异常）${NC}"
        FAIL=$((FAIL + 1))
    else
        echo -e "\n${GREEN}✅ #${num} 通过${NC}"
        PASS=$((PASS + 1))
    fi
}

# 清除缓存，避免拿到旧数据
CACHE_FILE="$SCRIPT_DIR/astock-kit-skills/.cache/akshare_cache.db"
if [ -f "$CACHE_FILE" ]; then
    echo "删除旧缓存: $CACHE_FILE"
    rm "$CACHE_FILE"
fi

AKSHARE_VER=$(python3 -c "import akshare; print(akshare.__version__)" 2>/dev/null || echo "未安装")
AKSHARE_LATEST=$(pip3 index versions akshare 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "")

echo "============================================================"
echo "  astock-kit 全功能测试"
echo "  测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  测试股票: $STOCK (平安银行) / $STOCK2 (贵州茅台)"
echo "  AKShare 版本: $AKSHARE_VER"
if [ -n "$AKSHARE_LATEST" ] && [ "$AKSHARE_LATEST" != "$AKSHARE_VER" ]; then
    echo -e "  ${YELLOW}⚠️  最新版: $AKSHARE_LATEST — pip install akshare --upgrade${NC}"
fi
echo "============================================================"

# ============================================================
# 第一部分：本地数据查询（基于 DuckDB + Parquet）
# 需求来源："本地数据库拉完之后，在屏幕上演示查股票代码"
# ============================================================
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  第一部分：本地数据查询（DuckDB）${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"

# 需求："帮我查看股票代码谁谁谁"
run_test 1 "个股最新行情（查平安银行）" \
    "cd $LOCAL && python3 query_data.py quote $STOCK"

run_test 2 "个股最新行情（查茅台）" \
    "cd $LOCAL && python3 query_data.py quote $STOCK2"

# 需求："在哪一天的最高点是多少"
run_test 3 "近60天最高价" \
    "cd $LOCAL && python3 query_data.py high $STOCK --days 60"

run_test 4 "近120天最高价（茅台）" \
    "cd $LOCAL && python3 query_data.py high $STOCK2 --days 120"

# 需求："20日均线买入，20日均线卖出"
run_test 5 "MA20 均线买卖信号" \
    "cd $LOCAL && python3 query_data.py ma20 $STOCK"

run_test 6 "MA20 均线信号（茅台）" \
    "cd $LOCAL && python3 query_data.py ma20 $STOCK2"

# 需求：全市场扫描
run_test 7 "全市场 MA20 金叉扫描" \
    "cd $LOCAL && python3 query_data.py scan-ma20" 120

# 需求：涨幅榜
run_test 8 "近5天涨幅 TOP20" \
    "cd $LOCAL && python3 query_data.py top-gainers --days 5"

run_test 9 "近20天涨幅 TOP20" \
    "cd $LOCAL && python3 query_data.py top-gainers --days 20"

# 自定义 SQL
run_test 10 "自定义SQL查询" \
    "cd $LOCAL && python3 query_data.py sql \"SELECT code, 日期, 收盘, 成交量 FROM data WHERE code='$STOCK' AND 收盘 > 11 ORDER BY 日期 DESC LIMIT 5\""

# ============================================================
# 第二部分：策略回测
# 需求来源："MA20金叉测试"、"输出的报告得调的详细一点，最大回撤什么的"
# ============================================================
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  第二部分：策略回测${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"

# 单只回测
run_test 11 "单只回测 - 平安银行（终端输出）" \
    "cd $LOCAL && python3 backtest.py ma20 $STOCK"

run_test 12 "单只回测 - 茅台（100万资金）" \
    "cd $LOCAL && python3 backtest.py ma20 $STOCK2"

# 需求："输出专业格式的回测报告"
run_test 13 "生成 Markdown 回测报告" \
    "cd $LOCAL && python3 backtest.py ma20 $STOCK -o /tmp/backtest_test_report.md && echo '--- 报告内容 ---' && head -30 /tmp/backtest_test_report.md"

# 需求："本地跑全部股票回测"
run_test 14 "全市场回测 TOP10（耗时较长）" \
    "cd $LOCAL && python3 backtest.py ma20 --all --top 10" 300

# ============================================================
# 第三部分：实时数据（AKShare）
# 需求来源："akshare可以拉A股数据"、"实时行情"
# ============================================================
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  第三部分：实时数据查询（AKShare 在线）${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"

# 实时行情
run_test 15 "实时行情 - 平安银行" \
    "cd $SKILL && python3 get_realtime_quote.py $STOCK" 30 \
    "获取失败|ProxyError|ConnectionError"

run_test 16 "实时行情 - 茅台" \
    "cd $SKILL && python3 get_realtime_quote.py $STOCK2" 30 \
    "获取失败|ProxyError|ConnectionError"

# 历史K线
run_test 17 "历史K线 - 近60天" \
    "cd $SKILL && python3 get_history_kline.py $STOCK --days 60" 30 \
    "获取失败|ProxyError|ConnectionError"

# 技术指标（MA/MACD/RSI/KDJ/BOLL）
run_test 18 "技术指标计算（MA/MACD/RSI/KDJ/BOLL）" \
    "cd $SKILL && python3 calc_technical.py $STOCK" 30 \
    "获取.*失败|ProxyError|ConnectionError"

# 资金流向
run_test 19 "资金流向 - 近10天" \
    "cd $SKILL && python3 get_fund_flow.py $STOCK --days 10" 30 \
    "获取失败|ProxyError|ConnectionError"

# 财务数据
run_test 20 "财务数据" \
    "cd $SKILL && python3 get_financial.py $STOCK" 30 \
    "获取失败|报告期: 1989"

# 估值指标（PE/PB）
run_test 21 "估值指标（PE/PB/股息率）" \
    "cd $SKILL && python3 get_valuation.py $STOCK" 30

# 股东信息
run_test 22 "股东信息" \
    "cd $SKILL && python3 get_shareholders.py $STOCK" 30

# 分红数据
run_test 23 "分红数据" \
    "cd $SKILL && python3 get_dividend.py $STOCK" 30

# ============================================================
# 第四部分：智能分析（AKShare 综合）
# 需求来源："AI 有专业格式的回测报告"、投资分析
# ============================================================
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  第四部分：智能分析${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"

# 需求：智能投资分析（评分模型）— 全是50分说明数据没拿到
run_test 24 "智能投资分析（多维度评分）- 平安银行" \
    "cd $SKILL && python3 analyze_investment.py $STOCK" 60 \
    "得分: 50.*得分: 50.*得分: 50"

run_test 25 "智能投资分析 - 茅台" \
    "cd $SKILL && python3 analyze_investment.py $STOCK2" 60 \
    "得分: 50.*得分: 50.*得分: 50"

# 综合分析报告 — 有"获取.*失败"说明东方财富数据缺失
run_test 26 "综合分析报告（全量数据合并）" \
    "cd $SKILL && python3 stock_analyzer.py $STOCK" 90 \
    "获取.*失败"

run_test 27 "综合分析报告导出" \
    "cd $SKILL && python3 stock_analyzer.py $STOCK -o /tmp/stock_report_test.md && echo '--- 报告前30行 ---' && head -30 /tmp/stock_report_test.md" 90 \
    "获取.*失败"

# ============================================================
# 第五部分：数据下载与更新
# 需求来源："每天agent做一个定时任务自动更新"
# ============================================================
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  第五部分：数据下载与更新${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"

# 数据摘要
run_test 28 "数据摘要（已下载数据统计）" \
    "cd $LOCAL && python3 download_fast.py --summary"

# 增量更新（只拉最近7天，很快）
run_test 29 "增量更新日线（--update 模式）" \
    "cd $LOCAL && python3 download_fast.py --period daily --update --test 3" 60

# 断点续传
run_test 30 "断点续传测试（--resume 跳过已有）" \
    "cd $LOCAL && python3 download_fast.py --period daily --resume --test 3" 60

# ============================================================
# 汇总
# ============================================================
echo ""
echo "============================================================"
echo "  测试完成！"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo -e "  ${GREEN}通过: $PASS${NC}"
echo -e "  ${RED}失败: $FAIL${NC}"
echo "  总计: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 全部通过！可以给客户部署了${NC}"
else
    echo -e "${RED}⚠️  有 $FAIL 项失败，请检查后再部署${NC}"
fi
echo ""

# 需求对照清单
echo "============================================================"
echo "  客户需求对照"
echo "============================================================"
echo "  [测试 1-2]   查个股行情              → quote"
echo "  [测试 3-4]   查某天最高点            → high"
echo "  [测试 5-6]   20日均线买卖信号        → ma20"
echo "  [测试 7]     全市场MA20金叉扫描      → scan-ma20"
echo "  [测试 8-9]   涨幅榜                  → top-gainers"
echo "  [测试 10]    自定义SQL               → sql"
echo "  [测试 11-12] 单只MA20回测            → backtest ma20"
echo "  [测试 13]    专业回测报告（Markdown） → backtest -o"
echo "  [测试 14]    全市场回测              → backtest --all"
echo "  [测试 15-16] 实时行情（AKShare）     → get_realtime_quote"
echo "  [测试 17]    历史K线                 → get_history_kline"
echo "  [测试 18]    技术指标MA/MACD/RSI/KDJ → calc_technical"
echo "  [测试 19]    资金流向                → get_fund_flow"
echo "  [测试 20]    财务数据                → get_financial"
echo "  [测试 21]    估值PE/PB               → get_valuation"
echo "  [测试 22]    股东信息                → get_shareholders"
echo "  [测试 23]    分红数据                → get_dividend"
echo "  [测试 24-25] 智能投资分析（评分）    → analyze_investment"
echo "  [测试 26-27] 综合分析报告            → stock_analyzer"
echo "  [测试 28]    数据摘要                → --summary"
echo "  [测试 29]    每日增量更新            → --update"
echo "  [测试 30]    断点续传                → --resume"
echo "============================================================"
echo ""
echo "  未覆盖（需手动测试）："
echo "  - Hermes Agent 安装与后台运行"
echo "  - 微信网关接入"
echo "  - 关闭Mac省电模式"
echo "  - 定时任务 crontab 配置"
echo "  - 一键备份/还原"
echo "============================================================"
