#!/usr/bin/env bash
# Import + publish literature_cited packages (peer-reviewed extracted ranges).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LIT=docs/benchmark/literature
FLAG=--allow-literature-cited
for f in forehand_smash.literature_v1.json net_tumble.literature_v1.json forehand_clear.literature_v1.json; do
  python scripts/benchmark_validate.py "$LIT/$f" $FLAG
  python scripts/benchmark_import.py "$LIT/$f" $FLAG --change-log "literature_cited import"
done
python scripts/benchmark_publish.py forehand_smash --version 1.0.0-lit $FLAG
python scripts/benchmark_publish.py net_tumble --version 1.0.0-lit $FLAG
python scripts/benchmark_publish.py forehand_clear --version 1.0.0-lit $FLAG
echo "OK: literature packages published"
