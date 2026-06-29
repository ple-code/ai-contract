#!/bin/bash
set -e

echo "=== 明衡 · 本地开发启动 ==="

echo "[1/3] 启动 PostgreSQL (Docker)..."
docker compose up -d postgres
until docker compose exec postgres pg_isready -U mingheng 2>/dev/null; do sleep 1; done
echo "数据库就绪"

echo "[2/3] 启动后端..."
cd app/api
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install -e .
fi
.venv/bin/python -m app.seeds.run_all &
.venv/bin/uvicorn app.main:app --reload --port 8000 &
API_PID=$!
cd ../..

echo "[3/3] 启动前端..."
cd app/web
npm run dev &
WEB_PID=$!
cd ../..

echo ""
echo "=== 开发服务已启动 ==="
echo "前端: http://localhost:5173"
echo "API:  http://localhost:8000"
echo "默认管理员: admin / Admin@123"
echo ""
echo "Ctrl+C 停止所有服务"

trap "kill $API_PID $WEB_PID 2>/dev/null; exit" INT TERM
wait
