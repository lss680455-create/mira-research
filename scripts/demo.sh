#!/usr/bin/env bash
# Mira 离线 demo：契约校验 → 刷新报告 → 研究包读出
# 用法：bash scripts/demo.sh [PYTHON]   默认 PYTHON=python
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${1:-python}"
AS_OF="${MIRA_AS_OF:-2026-09-10}"
CASE="examples/aapl-2026-04"

echo "== 1/3 契约校验（examples 全部 + schemas 自检） =="
"$PY" -m mira validate --all

echo
echo "== 2/3 刷新报告（as_of=${AS_OF}） =="
"$PY" -m mira refresh "$CASE" --as-of "$AS_OF" --write

echo
echo "== 3/3 研究包读出 =="
"$PY" -m mira report "$CASE" --as-of "$AS_OF" -o "$CASE/report.md"

echo
echo "完成：$CASE/refresh-report.md · $CASE/refresh-report.json · $CASE/report.md"
