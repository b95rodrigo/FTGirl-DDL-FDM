#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$ROOT/plugin/manifest.json")"
OUT="$ROOT/FTGirl-DDL-FDM-v${VERSION}.fda"
rm -f "$OUT"
(
  cd "$ROOT/plugin"
  zip -r -9 "$OUT" . -x '*.pyc' '__pycache__/*' '.DS_Store'
)
echo "Built: $OUT"
