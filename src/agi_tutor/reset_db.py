from __future__ import annotations
import sqlite3, os
DB = "tutor.db"

schema = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  region TEXT,
  stage TEXT,
  sessions_per_week INTEGER,
  hours_per_session REAL,
  school_year_end TEXT
);
CREATE TABLE IF NOT EXISTS plans(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  subject_code TEXT,
  start_date TEXT,
  end_date TEXT,
  hours_per_week REAL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS modules(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER,
  title TEXT,
  summary TEXT,
  est_minutes INTEGER,
  order_index INTEGER
);
CREATE TABLE IF NOT EXISTS module_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id INTEGER,
  objective TEXT,
  success_criteria TEXT,
  order_index INTEGER
);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id INTEGER,
  started_at TEXT,
  completed_at TEXT
);
CREATE TABLE IF NOT EXISTS subjects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT,
  title TEXT
);
CREATE TABLE IF NOT EXISTS progress(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  module_id INTEGER,
  progress REAL
);
CREATE TABLE IF NOT EXISTS badges(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  name TEXT
);
CREATE TABLE IF NOT EXISTS curriculums(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  region TEXT,
  stage TEXT,
  subject TEXT,
  spec TEXT
);
"""

def reset():
  if os.path.exists(DB):
    os.remove(DB)
  con = sqlite3.connect(DB)
  con.executescript(schema)
  con.commit()
  con.close()

if __name__ == "__main__":
  reset()
  print("OK, tutor.db reset with correct schema")
