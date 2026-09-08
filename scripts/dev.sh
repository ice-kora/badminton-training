#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/services/api"
cd "$API"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

mkdir -p data
export DATABASE_URL="${DATABASE_URL:-sqlite:///./data/app.db}"
export ALLOW_DEV_LOGIN=true

python -m app.seed
echo "Starting uvicorn on http://127.0.0.1:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
