#!/bin/bash
# ============================================================
# 重测脚本：只测东方财富数据源相关的在线查询
# 换网络后跑这个验证 AKShare 实时数据是否正常
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL="$SCRIPT_DIR/astock-kit-skills/scripts"

STOCK="000001"
STOCK2="600519"

run_test() {
    local num="$1"
    local name="$2"
    local cmd="$3"
    local check_pattern="$4"  # 如果输出包含这个关键词，说明实际失败了

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}测试 #${num}: ${name}${NC}"
    echo -e "${YELLOW}命令: ${cmd}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    local output
    output=$(bash -c "$cmd" 2>&1)
    local exit_code=$?

    echo "$output"

    # 检查退出码
    if [ $exit_code -ne 0 ]; then
        echo -e "\n${RED}❌ #${num} 失败（exit=$exit_code）${NC}"
        FAIL=$((FAIL + 1))
        return
    fi

    # 检查输出里有没有失败关键词（抓"假通过"）
    if [ -n "$check_pattern" ]; then
        if echo "$output" | grep -qi "$check_pattern"; then
            echo -e "\n${RED}❌ #${num} 假通过 — 脚本没崩但数据获取失败${NC}"
            FAIL=$((FAIL + 1))
            return
        fi
    fi

    echo -e "\n${GREEN}✅ #${num} 通过${NC}"
    PASS=$((PASS + 1))
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
echo "  AKShare 在线数据重测（东方财富数据源）"
echo "  测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  测试股票: $STOCK (平安银行) / $STOCK2 (贵州茅台)"
echo "  AKShare 版本: $AKSHARE_VER"
if [ -n "$AKSHARE_LATEST" ] && [ "$AKSHARE_LATEST" != "$AKSHARE_VER" ]; then
    echo -e "  ${YELLOW}⚠️  最新版: $AKSHARE_LATEST — pip install akshare --upgrade${NC}"
fi
echo ""
echo "  这些测试依赖东方财富 API，需要直连网络"
echo "  如果全部失败 → 代理/网络问题"
echo "  如果部分失败 → 脚本 bug 或 API 变更"
echo "============================================================"

# --- 实时行情 ---
run_test 1 "实时行情 - 平安银行" \
    "cd $SKILL && python3 get_realtime_quote.py $STOCK" \
    "获取失败"

run_test 2 "实时行情 - 茅台" \
    "cd $SKILL && python3 get_realtime_quote.py $STOCK2" \
    "获取失败"

# --- 历史K线 ---
run_test 3 "历史K线 - 近60天" \
    "cd $SKILL && python3 get_history_kline.py $STOCK --days 60" \
    "所有数据源均获取失败"

# --- 技术指标 ---
run_test 4 "技术指标（MA/MACD/RSI/KDJ/BOLL）" \
    "cd $SKILL && python3 calc_technical.py $STOCK" \
    "所有数据源均获取失败"

# --- 资金流向 ---
run_test 5 "资金流向 - 近10天" \
    "cd $SKILL && python3 get_fund_flow.py $STOCK --days 10" \
    "获取失败"

# --- 财务数据（上次拿到1989年数据，检查是否正常） ---
run_test 6 "财务数据（检查报告期是否最新）" \
    "cd $SKILL && python3 get_financial.py $STOCK" \
    "1989"

# --- 智能投资分析（上次全是50分默认值） ---
run_test 7 "智能投资分析 - 平安银行" \
    "cd $SKILL && python3 analyze_investment.py $STOCK" \
    "所有数据源均获取失败"

run_test 8 "智能投资分析 - 茅台" \
    "cd $SKILL && python3 analyze_investment.py $STOCK2" \
    "所有数据源均获取失败"

# --- 综合报告（上次大量模块获取失败） ---
run_test 9 "综合分析报告" \
    "cd $SKILL && python3 stock_analyzer.py $STOCK" \
    "所有数据源均获取失败|Connection aborted"

# ============================================================
# 汇总
# ============================================================
echo ""
echo "============================================================"
echo "  重测完成！"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo -e "  ${GREEN}通过: $PASS${NC}"
echo -e "  ${RED}失败: $FAIL${NC}"
echo "  总计: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 全部通过！东方财富 API 连接正常${NC}"
elif [ $FAIL -eq $((PASS + FAIL)) ]; then
    echo -e "${RED}💀 全部失败 — 大概率还是代理/网络问题，检查：${NC}"
    echo "  1. v2rayN 是否关闭 TUN 模式"
    echo "  2. 或者把 eastmoney.com 加到直连规则"
    echo "  3. 或者 unset http_proxy https_proxy all_proxy"
else
    echo -e "${YELLOW}⚠️  部分失败 — 可能是个别 API 变更或脚本问题${NC}"
fi
echo ""
