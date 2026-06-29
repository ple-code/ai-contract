#!/bin/bash
set -e

echo "=== 明衡 · AI 合同审阅系统 启动脚本 ==="

echo "[1/4] 启动 PostgreSQL..."
docker compose up -d postgres
echo "等待数据库就绪..."
until docker compose exec postgres pg_isready -U mingheng 2>/dev/null; do sleep 1; done
echo "数据库就绪"

echo "[2/4] 启动后端 API..."
docker compose up -d api
sleep 3

echo "[3/4] 运行数据库种子..."
docker compose exec api python -m app.seeds.run_all

echo "[4/4] 启动前端..."
docker compose up -d web

echo ""
echo "=== 启动完成 ==="
echo "前端: http://localhost"
echo "API:  http://localhost:8000"
echo "默认管理员: admin / Admin@123"
echo ""
