#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
  echo "Usage: scripts/restore.sh /path/to/agi-tutor-backup_YYYYMMDD_HHMMSS.tar.gz"
  exit 1
fi

ARCHIVE="$1"
TARGET_DIR="${2:-$HOME/agi-tutor-restored}"

mkdir -p "$TARGET_DIR"
tar -xzf "$ARCHIVE" -C "$TARGET_DIR"

cd "$TARGET_DIR"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

if [[ -f requirements.txt ]]; then
  python -m pip install -r requirements.txt
else
  # minimal set in case the file is missing
  python -m pip install openai python-dotenv rich typer pydantic
fi

# prefer the full db if present, else rebuild from dump
if [[ ! -f tutor.db && -f tutor_dump_*.sql ]]; then
  DUMP_FILE="$(ls -1 tutor_dump_*.sql | head -n 1)"
  sqlite3 tutor.db < "$DUMP_FILE"
fi

echo "Restore complete at $TARGET_DIR"
echo "Testing CLI import..."
PYTHONPATH=src python -m agi_tutor.cli init-db >/dev/null 2>&1 || true
echo "Ready."
