#!/bin/bash
set -e
cd "$(dirname "$0")/.."
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
curl -sf http://127.0.0.1:8000/health && echo
curl -sf -o /dev/null -w "web:%{http_code}\n" http://127.0.0.1:8088/
