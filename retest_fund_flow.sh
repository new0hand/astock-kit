#!/bin/bash
# ============================================================
# 单独测试资金流向（东方财富 push2his 接口）
# 本机代理拦截，需要在服务器上跑
# ============================================================

GREEN='\033[0;32m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL="$SCRIPT_DIR/skill/scripts"

AKSHARE_VER=$(python3 -c "import akshare; print(akshare.__version__)" 2>/dev/null || echo "未安装")
AKSHARE_LATEST=$(pip3 index versions akshare 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "")

echo "============================================================"
echo "  资金流向接口测试"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  接口: push2his.eastmoney.com (东方财富)"
echo "  函数: ak.stock_individual_fund_flow()"
echo "  AKShare 版本: $AKSHARE_VER"
if [ -n "$AKSHARE_LATEST" ] && [ "$AKSHARE_LATEST" != "$AKSHARE_VER" ]; then
    echo -e "  ${YELLOW}⚠️  最新版: $AKSHARE_LATEST — pip install akshare --upgrade${NC}"
fi
echo "============================================================"

PASS=0
FAIL=0

run_test() {
    local num="$1" name="$2" cmd="$3" check="$4"
    echo ""
    echo -e "${CYAN}测试 #${num}: ${name}${NC}"
    local output
    output=$(bash -c "$cmd" 2>&1)
    local code=$?
    echo "$output"
    if [ $code -ne 0 ]; then
        echo -e "${RED}❌ #${num} 失败 (exit=$code)${NC}"
        FAIL=$((FAIL+1))
    elif [ -n "$check" ] && echo "$output" | grep -qiE "$check"; then
        echo -e "${RED}❌ #${num} 数据获取失败${NC}"
        FAIL=$((FAIL+1))
    else
        echo -e "${GREEN}✅ #${num} 通过${NC}"
        PASS=$((PASS+1))
    fi
}

# 资金流向 - 3只不同股票
run_test 1 "资金流向 - 000001 平安银行" \
    "cd $SKILL && python3 get_fund_flow.py 000001 --days 5" \
    "获取失败|ConnectionError|Connection aborted"

run_test 2 "资金流向 - 600519 贵州茅台" \
    "cd $SKILL && python3 get_fund_flow.py 600519 --days 5" \
    "获取失败|ConnectionError|Connection aborted"

run_test 3 "资金流向 - 002475 立讯精密" \
    "cd $SKILL && python3 get_fund_flow.py 002475 --days 5" \
    "获取失败|ConnectionError|Connection aborted"

# 顺便测下清缓存后的财务数据
echo ""
echo -e "${CYAN}--- 附加：财务数据（清缓存后）---${NC}"
if [ -f "$SCRIPT_DIR/skill/.cache/akshare_cache.db" ]; then
    echo "删除旧缓存..."
    rm "$SCRIPT_DIR/skill/.cache/akshare_cache.db"
fi

run_test 4 "财务数据 - 000001（应显示2025/2026年报告期）" \
    "cd $SKILL && python3 get_financial.py 000001" \
    "报告期: 1989"

run_test 5 "财务数据 - 600519" \
    "cd $SKILL && python3 get_financial.py 600519" \
    "报告期: 1989"

echo ""
echo "============================================================"
echo "  通过: $PASS / 失败: $FAIL / 总计: $((PASS+FAIL))"
echo "============================================================"
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}全部通过${NC}"
else
    echo -e "${RED}有 $FAIL 项失败${NC}"
fi
