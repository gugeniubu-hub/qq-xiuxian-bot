from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import urlparse


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
  user_id TEXT PRIMARY KEY,
  nickname TEXT NOT NULL,
  root_type TEXT NOT NULL,
  realm TEXT NOT NULL,
  cultivation INTEGER NOT NULL DEFAULT 0,
  age INTEGER NOT NULL DEFAULT 16,
  lifespan INTEGER NOT NULL DEFAULT 120,
  spirit_stones INTEGER NOT NULL DEFAULT 0,
  fortune INTEGER NOT NULL DEFAULT 0,
  stamina INTEGER NOT NULL DEFAULT 100,
  comprehension INTEGER NOT NULL DEFAULT 10,
  rebirth_count INTEGER NOT NULL DEFAULT 0,
  soul_marks INTEGER NOT NULL DEFAULT 0,
  legacy_points INTEGER NOT NULL DEFAULT 0,
  sect_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  theme TEXT NOT NULL,
  description TEXT NOT NULL,
  required_rebirth_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS cultivation_methods (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  realm_requirement TEXT NOT NULL,
  practice_bonus REAL NOT NULL DEFAULT 0,
  breakthrough_bonus REAL NOT NULL DEFAULT 0,
  source_sect_id TEXT,
  required_rebirth_count INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (source_sect_id) REFERENCES sects(id)
);

CREATE TABLE IF NOT EXISTS player_methods (
  user_id TEXT NOT NULL,
  method_id TEXT NOT NULL,
  acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, method_id),
  FOREIGN KEY (user_id) REFERENCES players(user_id),
  FOREIGN KEY (method_id) REFERENCES cultivation_methods(id)
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  item_type TEXT NOT NULL,
  rarity TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventories (
  user_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, item_id),
  FOREIGN KEY (user_id) REFERENCES players(user_id),
  FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS market_listings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seller_user_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  sold_at TEXT,
  FOREIGN KEY (seller_user_id) REFERENCES players(user_id),
  FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS fortune_pool (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  amount INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO fortune_pool (id, amount) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS daily_signins (
  user_id TEXT NOT NULL,
  sign_date TEXT NOT NULL,
  base_reward INTEGER NOT NULL,
  pool_reward INTEGER NOT NULL,
  fortune_roll INTEGER NOT NULL,
  PRIMARY KEY (user_id, sign_date),
  FOREIGN KEY (user_id) REFERENCES players(user_id)
);

CREATE TABLE IF NOT EXISTS adventure_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  roll_value INTEGER,
  outcome TEXT NOT NULL,
  reward_spirit_stones INTEGER NOT NULL DEFAULT 0,
  reward_cultivation INTEGER NOT NULL DEFAULT 0,
  reward_item_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES players(user_id),
  FOREIGN KEY (reward_item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS rebirth_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  rebirth_count INTEGER NOT NULL,
  previous_realm TEXT NOT NULL,
  legacy_points_gained INTEGER NOT NULL,
  soul_marks_consumed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES players(user_id)
);

CREATE TABLE IF NOT EXISTS legacy_unlocks (
  user_id TEXT NOT NULL,
  unlock_key TEXT NOT NULL,
  unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, unlock_key),
  FOREIGN KEY (user_id) REFERENCES players(user_id)
);
"""

DEFAULT_SECTS = (
    (
        "qinglan",
        "青岚宗",
        "稳扎稳打的吐纳正宗，适合新手入门。",
        "以平稳修行为主，突破略稳，奇遇爆发较少。",
        0,
    ),
    (
        "chixiao",
        "赤霄门",
        "偏重杀伐与历练，收益高，波动也大。",
        "历练收益更激进，但更容易遭遇凶险事件。",
        0,
    ),
    (
        "taixu",
        "太虚观",
        "轮回者才能踏入的古老传承。",
        "擅长福缘、命格与前尘感悟。",
        1,
    ),
)

DEFAULT_METHODS = (
    ("breath-basic", "吐纳诀", "炼气前期", 0.10, 0.00, "qinglan", 0),
    ("mist-heart", "青岚养心篇", "筑基前期", 0.15, 0.05, "qinglan", 0),
    ("scarlet-soul", "赤霄战诀", "炼气后期", 0.08, 0.10, "chixiao", 0),
    ("void-scripture", "太虚轮回经", "筑基圆满", 0.18, 0.08, "taixu", 1),
)


def resolve_sqlite_path(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

    if parsed.path.startswith("/"):
        path = parsed.path[1:]
    else:
        path = parsed.path

    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def initialize_database(database_url: str) -> Path:
    db_path = resolve_sqlite_path(database_url)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.executemany(
            """
            INSERT OR IGNORE INTO sects (
              id, name, theme, description, required_rebirth_count
            ) VALUES (?, ?, ?, ?, ?)
            """,
            DEFAULT_SECTS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO cultivation_methods (
              id, name, realm_requirement, practice_bonus, breakthrough_bonus,
              source_sect_id, required_rebirth_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            DEFAULT_METHODS,
        )
        connection.commit()
    return db_path
