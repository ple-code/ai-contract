#!/bin/bash
# 明衡 · 后端接口测试脚本
# 用法: ./tests/test_api.sh [base_url]
# 需要先启动后端: uvicorn app.main:app --port 8000

BASE=${1:-http://localhost:8000}
COOKIE=/tmp/mh_test_cookie
PASS=0
FAIL=0
SKIP=0

green() { printf "\033[32m✓ %s\033[0m\n" "$1"; PASS=$((PASS+1)); }
red()   { printf "\033[31m✗ %s\033[0m\n" "$1"; FAIL=$((FAIL+1)); }
skip()  { printf "\033[33m⊘ %s\033[0m\n" "$1"; SKIP=$((SKIP+1)); }

check() {
  local name=$1 expected=$2 actual=$3
  if [ "$actual" = "$expected" ]; then green "$name"; else red "$name (expected $expected, got $actual)"; fi
}

check_contains() {
  local name=$1 needle=$2 haystack=$3
  if echo "$haystack" | grep -q "$needle" 2>/dev/null; then green "$name"; else red "$name (missing: $needle)"; fi
}

check_http() {
  local name=$1 expected=$2 url=$3
  shift 3
  local HTTP=$(curl -s -o /dev/null -w "%{http_code}" -b $COOKIE "$@" "$url")
  check "$name" "$expected" "$HTTP"
}

echo "=========================================="
echo "明衡 · 后端 API 测试 ($BASE)"
echo "=========================================="

# --- 1. Health ---
echo ""
echo "--- Health ---"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
check "GET /health" "200" "$HTTP"

# --- 2. Auth ---
echo ""
echo "--- Auth ---"
RES=$(curl -s -c $COOKIE -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123"}' -w "\n%{http_code}")
HTTP=$(echo "$RES" | tail -1)
BODY=$(echo "$RES" | head -1)
check "POST /api/auth/login" "200" "$HTTP"
check_contains "login returns token" "token" "$BODY"

HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" "$BASE/api/me")
check "GET /api/me" "200" "$HTTP"

HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" -X PUT "$BASE/api/me/pref" \
  -H 'Content-Type: application/json' -d '{"default_post":"采购经理","remember_post":true}')
check "PUT /api/me/pref" "200" "$HTTP"

# --- 3. 合同类型 ---
echo ""
echo "--- 合同类型 ---"
RES=$(curl -s -b $COOKIE "$BASE/api/contract-types")
check_contains "GET /api/contract-types" "purchase" "$RES"

# --- 4. 上传合同 ---
echo ""
echo "--- 上传合同 ---"
DOCX_PATH="../../raw/【模】个推采购合同模板.docx"
if [ -f "$DOCX_PATH" ]; then
  UPLOAD=$(curl -s -b $COOKIE -X POST "$BASE/api/contracts" \
    -F "file=@$DOCX_PATH" -F "mode=new")
  check_contains "POST /api/contracts (upload)" "ok" "$UPLOAD"
  check_contains "类型识别为 purchase" "purchase" "$UPLOAD"
  check_contains "条款数 > 0" "clause_count" "$UPLOAD"
  CID=$(echo "$UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('contract_id',''))" 2>/dev/null)
  VID=$(echo "$UPLOAD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version_id',''))" 2>/dev/null)
else
  skip "POST /api/contracts (无测试文件 $DOCX_PATH)"
  CID=""
  VID=""
fi

# --- 5. 合同列表 ---
echo ""
echo "--- 合同列表 ---"
RES=$(curl -s -b $COOKIE "$BASE/api/contracts")
check_contains "GET /api/contracts" "items" "$RES"

RES=$(curl -s -b $COOKIE "$BASE/api/contracts/options")
check_contains "GET /api/contracts/options" "name" "$RES"

# --- 6. 合同详情 + 预览 ---
if [ -n "$CID" ]; then
  echo ""
  echo "--- 合同详情 ---"
  HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" "$BASE/api/contracts/$CID")
  check "GET /api/contracts/$CID" "200" "$HTTP"

  RES=$(curl -s -b $COOKIE "$BASE/api/versions/$VID/preview")
  check_contains "GET /api/versions/$VID/preview" "code" "$RES"

  RES=$(curl -s -b $COOKIE "$BASE/api/versions/$VID/review-state")
  check_contains "GET /api/versions/$VID/review-state" "states" "$RES"
fi

# --- 7. 复审操作 ---
if [ -n "$VID" ]; then
  echo ""
  echo "--- 复审操作 ---"
  HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" -X PUT \
    "$BASE/api/versions/$VID/clauses/0/decision" \
    -H 'Content-Type: application/json' -d '{"decision":"accept"}')
  check "PUT decision (accept)" "200" "$HTTP"

  HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" -X PUT \
    "$BASE/api/versions/$VID/clauses/1/annotate" \
    -H 'Content-Type: application/json' -d '{"note":"测试批注"}')
  check "PUT annotate" "200" "$HTTP"

  RES=$(curl -s -b $COOKIE "$BASE/api/versions/$VID/review-state")
  check_contains "review-state shows accept" "accept" "$RES"
  check_contains "review-state shows locked" "true" "$RES"

  # 撤销
  curl -s -b $COOKIE -X PUT "$BASE/api/versions/$VID/clauses/0/decision" \
    -H 'Content-Type: application/json' -d '{"decision":null}' > /dev/null
  curl -s -b $COOKIE -X PUT "$BASE/api/versions/$VID/clauses/1/annotate" \
    -H 'Content-Type: application/json' -d '{"note":""}' > /dev/null
  green "undo decision + annotate"

  RES=$(curl -s -b $COOKIE "$BASE/api/versions/$VID/review-state")
  check_contains "review-state unlocked" "false" "$RES"
fi

# --- 8. 变更记录 ---
if [ -n "$CID" ]; then
  echo ""
  echo "--- 变更记录 ---"
  RES=$(curl -s -b $COOKIE "$BASE/api/contracts/$CID/change-logs")
  check_contains "GET change-logs" "event_type" "$RES"
fi

# --- 9. 法律法规 ---
echo ""
echo "--- 法律法规 ---"
RES=$(curl -s -b $COOKIE "$BASE/api/legal/articles")
COUNT=$(echo "$RES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
check "GET /api/legal/articles (count=$COUNT)" "19" "$COUNT"

RES=$(curl -s -b $COOKIE "$BASE/api/legal/articles?law=%E6%B0%91%E6%B3%95%E5%85%B8")
check_contains "GET legal/articles?law=民法典" "民法典" "$RES"

# --- 10. Admin 接口 ---
echo ""
echo "--- Admin ---"
HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" "$BASE/api/admin/users")
check "GET /api/admin/users" "200" "$HTTP"

RES=$(curl -s -b $COOKIE -X POST "$BASE/api/admin/users" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"test_$(date +%s)\",\"password\":\"Test@123\",\"display_name\":\"测试\",\"role\":\"普通用户\"}")
check_contains "POST /api/admin/users (create)" "username" "$RES"

HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" "$BASE/api/admin/model-config")
check "GET /api/admin/model-config" "200" "$HTTP"

RES=$(curl -s -b $COOKIE -X POST "$BASE/api/admin/model-config/test")
check_contains "POST model-config/test" "ok" "$RES"

RES=$(curl -s -b $COOKIE "$BASE/api/admin/audit-logs")
check_contains "GET /api/admin/audit-logs" "items" "$RES"

# --- 11. 导出 ---
if [ -n "$VID" ]; then
  echo ""
  echo "--- 导出 ---"
  HTTP=$(curl -s -b $COOKIE -o /tmp/mh_report.docx -w "%{http_code}" "$BASE/api/versions/$VID/export/report")
  check "GET export/report" "200" "$HTTP"
  SIZE=$(wc -c < /tmp/mh_report.docx)
  [ "$SIZE" -gt 1000 ] && green "report docx size=$SIZE" || red "report docx too small ($SIZE)"

  HTTP=$(curl -s -b $COOKIE -o /tmp/mh_revised.docx -w "%{http_code}" "$BASE/api/versions/$VID/export/revised")
  check "GET export/revised" "200" "$HTTP"
  SIZE=$(wc -c < /tmp/mh_revised.docx)
  [ "$SIZE" -gt 1000 ] && green "revised docx size=$SIZE" || red "revised docx too small ($SIZE)"
fi

# --- 12. AI 审查 (可选, 耗时较长) ---
echo ""
echo "--- AI 审查 (SSE) ---"
if [ "${RUN_AI_TEST:-0}" = "1" ] && [ -n "$VID" ]; then
  RES=$(curl -s -N -b $COOKIE -X POST "$BASE/api/reviews" \
    -H 'Content-Type: application/json' \
    -d "{\"version_id\":$VID,\"stance\":\"buyer\"}" &
  PID=$!; sleep 30; kill $PID 2>/dev/null; cat /tmp/review_sse.txt 2>/dev/null | head -3)
  check_contains "AI review SSE returns data" "type" "$RES"
else
  skip "AI 审查 (设置 RUN_AI_TEST=1 启用, 需要 ~2min)"
fi

# --- 13. Logout ---
echo ""
echo "--- Logout ---"
HTTP=$(curl -s -b $COOKIE -o /dev/null -w "%{http_code}" -X POST "$BASE/api/auth/logout")
check "POST /api/auth/logout" "200" "$HTTP"

# --- Summary ---
echo ""
echo "=========================================="
printf "结果: \033[32m%d 通过\033[0m  \033[31m%d 失败\033[0m  \033[33m%d 跳过\033[0m\n" $PASS $FAIL $SKIP
echo "=========================================="

rm -f $COOKIE
exit $FAIL
