#!/usr/bin/env bash
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$HOME/Desktop/agi-tutor-backup_$STAMP.tar.gz"

# freeze requirements from the venv if present
if [[ -d .venv ]]; then
  source .venv/bin/activate
  python3 -m pip freeze > requirements.txt
fi

# make SQLite backup and dump if DB exists
DB_FILE="tutor.db"
if [[ -f "$DB_FILE" ]]; then
  sqlite3 "$DB_FILE" ".backup tutor_backup_$STAMP.sqlite3"
  sqlite3 "$DB_FILE" ".dump" > tutor_dump_$STAMP.sql
fi

# archive everything needed to restore
tar -czf "$OUT" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".DS_Store" \
  src ui data .env requirements.txt \
  tutor.db tutor_backup_$STAMP.sqlite3 tutor_dump_$STAMP.sql 2>/dev/null || true

# tidy temp files
rm -f tutor_backup_$STAMP.sqlite3 tutor_dump_$STAMP.sql 2>/dev/null || true

echo "✅ Backup written to: $OUT"
tar -tzf "$OUT" | sed -n '1,40p'
