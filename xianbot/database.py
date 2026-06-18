from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import urlparse


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
  user_id TEXT PRIMARY KEY,
  nickname TEXT NOT NULL,
  root_type TEXT NOT NULL,
  root_affinity TEXT NOT NULL DEFAULT '木',
  root_purity INTEGER NOT NULL DEFAULT 60,
  root_temperament TEXT NOT NULL DEFAULT '中正',
  root_trait TEXT NOT NULL DEFAULT '聚灵',
  realm TEXT NOT NULL,
  cultivation INTEGER NOT NULL DEFAULT 0,
  age INTEGER NOT NULL DEFAULT 16,
  age_progress INTEGER NOT NULL DEFAULT 0,
  lifespan INTEGER NOT NULL DEFAULT 120,
  spirit_stones INTEGER NOT NULL DEFAULT 0,
  fortune INTEGER NOT NULL DEFAULT 0,
  stamina INTEGER NOT NULL DEFAULT 100,
  comprehension INTEGER NOT NULL DEFAULT 10,
  insight INTEGER NOT NULL DEFAULT 0,
  breakthrough_ready INTEGER NOT NULL DEFAULT 0,
  rebirth_count INTEGER NOT NULL DEFAULT 0,
  soul_marks INTEGER NOT NULL DEFAULT 0,
  legacy_points INTEGER NOT NULL DEFAULT 0,
  destiny_type TEXT,
  destiny_level INTEGER NOT NULL DEFAULT 0,
  sect_id TEXT,
  primary_method_id TEXT,
  equipped_artifact_id TEXT,
  meditation_started_at TEXT,
  meditation_until TEXT,
  meditation_minutes INTEGER NOT NULL DEFAULT 0,
  meditation_reward INTEGER NOT NULL DEFAULT 0,
  meditation_method_id TEXT,
  meditation_mode TEXT,
  meditation_insight_reward INTEGER NOT NULL DEFAULT 0,
  meditation_breakthrough_reward INTEGER NOT NULL DEFAULT 0,
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
  grade TEXT NOT NULL DEFAULT '凡品',
  method_type TEXT NOT NULL DEFAULT '心法',
  affinity TEXT NOT NULL DEFAULT '土',
  style TEXT NOT NULL DEFAULT '绵长',
  practice_bonus REAL NOT NULL DEFAULT 0,
  breakthrough_bonus REAL NOT NULL DEFAULT 0,
  insight_bonus REAL NOT NULL DEFAULT 0,
  source_sect_id TEXT,
  required_rebirth_count INTEGER NOT NULL DEFAULT 0,
  description TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (source_sect_id) REFERENCES sects(id)
);

CREATE TABLE IF NOT EXISTS player_methods (
  user_id TEXT NOT NULL,
  method_id TEXT NOT NULL,
  mastery INTEGER NOT NULL DEFAULT 0,
  equipped INTEGER NOT NULL DEFAULT 0,
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
  description TEXT NOT NULL,
  base_price INTEGER NOT NULL DEFAULT 0,
  consumable INTEGER NOT NULL DEFAULT 0,
  tradable INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS player_artifacts (
  user_id TEXT NOT NULL,
  item_id TEXT NOT NULL,
  mastery INTEGER NOT NULL DEFAULT 0,
  equipped INTEGER NOT NULL DEFAULT 0,
  acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, item_id),
  FOREIGN KEY (user_id) REFERENCES players(user_id),
  FOREIGN KEY (item_id) REFERENCES items(id)
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
  buyer_user_id TEXT,
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

CREATE TABLE IF NOT EXISTS world_states (
  state_date TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  adventure_bonus INTEGER NOT NULL DEFAULT 0,
  meditation_bonus REAL NOT NULL DEFAULT 0,
  encounter_bonus INTEGER NOT NULL DEFAULT 0,
  fortune_bonus INTEGER NOT NULL DEFAULT 0,
  lifespan_bonus INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS world_events (
  event_date TEXT PRIMARY KEY,
  event_key TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  objective TEXT NOT NULL,
  target_progress INTEGER NOT NULL,
  current_progress INTEGER NOT NULL DEFAULT 0,
  reward_spirit_stones INTEGER NOT NULL DEFAULT 0,
  reward_cultivation INTEGER NOT NULL DEFAULT 0,
  reward_insight INTEGER NOT NULL DEFAULT 0,
  reward_item_id TEXT,
  reward_item_quantity INTEGER NOT NULL DEFAULT 0,
  bonus_text TEXT NOT NULL DEFAULT '',
  participation_hint TEXT NOT NULL DEFAULT '',
  completed_at TEXT,
  FOREIGN KEY (reward_item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS world_event_contributions (
  event_date TEXT NOT NULL,
  user_id TEXT NOT NULL,
  contribution INTEGER NOT NULL DEFAULT 0,
  claimed INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (event_date, user_id),
  FOREIGN KEY (event_date) REFERENCES world_events(event_date),
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
    (
        "breath-basic",
        "吐纳诀",
        "炼气前期",
        "凡品",
        "吐纳法",
        "木",
        "绵长",
        0.10,
        0.00,
        0.03,
        "qinglan",
        0,
        "青岚宗入门吐纳法，胜在平稳，利于新手固本培元。",
    ),
    (
        "mist-heart",
        "青岚养心篇",
        "筑基前期",
        "黄阶",
        "心法",
        "水",
        "明悟",
        0.15,
        0.05,
        0.08,
        "qinglan",
        0,
        "以养神静心见长，可让修士在闭关时更易凝成道感。",
    ),
    (
        "river-mirror",
        "镜水归元录",
        "金丹前期",
        "玄阶",
        "心法",
        "水",
        "明悟",
        0.19,
        0.06,
        0.12,
        "qinglan",
        0,
        "青岚宗内门传承，修至深处可令气海如镜，最适合参玄与稳固根基。",
    ),
    (
        "scarlet-soul",
        "赤霄战诀",
        "炼气后期",
        "黄阶",
        "战诀",
        "火",
        "霸烈",
        0.08,
        0.10,
        0.02,
        "chixiao",
        0,
        "赤霄门杀伐传承，冲关与历练收益凶猛，但也更看根骨。",
    ),
    (
        "flame-body",
        "离火锻骨篇",
        "筑基中期",
        "玄阶",
        "锻体法",
        "火",
        "霸烈",
        0.14,
        0.11,
        0.03,
        "chixiao",
        0,
        "以火炼躯，斗法与冲关均有奇效，但闭关时更耗心神。",
    ),
    (
        "void-scripture",
        "太虚轮回经",
        "筑基圆满",
        "地阶",
        "轮回经",
        "虚",
        "轮回",
        0.18,
        0.08,
        0.10,
        "taixu",
        1,
        "轮回者才可驾驭的古经，擅长积蓄前尘感悟与冲关底蕴。",
    ),
    (
        "return-light",
        "返照观心诀",
        "金丹后期",
        "地阶",
        "心法",
        "虚",
        "轮回",
        0.20,
        0.10,
        0.15,
        "taixu",
        1,
        "返照前尘，化执为悟，轮回次数越高时越显神异。",
    ),
    (
        "ancient-vault",
        "太虚古藏篇",
        "元婴中期",
        "古传",
        "轮回经",
        "雷",
        "轮回",
        0.24,
        0.14,
        0.16,
        "taixu",
        2,
        "藏有古修封印的残篇，需要多次转世者才能真正承受其反震。",
    ),
)

DEFAULT_ITEMS = (
    ("qigather", "聚气丹", "丹药", "凡品", "服用后可迅速积累一段修为。", 80, 1, 1),
    ("spirit-herb", "灵草", "材料", "凡品", "炼丹与交易常用的基础灵材。", 25, 0, 1),
    ("clear-dew", "灵泉水", "材料", "凡品", "调和丹性所需的清灵泉水。", 30, 0, 1),
    ("iron-ore", "玄铁矿", "材料", "凡品", "常见的锻材，也可在坊市流通。", 35, 0, 1),
    ("flame-sand", "赤焰砂", "材料", "黄阶", "火性灵砂，适合炼制冲关类丹药。", 90, 0, 1),
    ("moon-dust", "月华粉", "材料", "黄阶", "月华凝成的细粉，适合炼制悟道类丹药。", 120, 0, 1),
    ("marrow-jade", "洗髓玉", "材料", "玄阶", "蕴有重塑根骨之力的稀有灵材。", 520, 0, 1),
    ("pill-dregs", "丹渣", "材料", "凡品", "炼丹失败后残留的药渣，可交易或留待后续玩法。", 8, 0, 1),
    ("restore-powder", "回灵散", "丹药", "凡品", "能快速补充体力。", 60, 1, 1),
    ("essence-pill", "凝元丹", "丹药", "黄阶", "服用后可凝练气海，积蓄冲关底蕴。", 180, 1, 1),
    ("insight-pill", "悟道丹", "丹药", "黄阶", "服用后可增长道悟，并帮助参玄明法。", 240, 1, 1),
    ("marrow-pill", "洗髓丹", "丹药", "玄阶", "转世者方能承受的洗髓丹，可洗练灵根画像。", 760, 1, 1),
    ("longevity-fruit", "延寿果", "灵果", "稀有", "服下后可滋养气血，少量延缓寿元流逝。", 380, 1, 1),
    ("rebirth-mark", "轮回印记", "秘物", "稀有", "转世重修所需的关键凭证。", 5000, 1, 1),
    ("method-fragment", "吐纳残篇", "功法残篇", "稀有", "可用于参悟基础吐纳类功法。", 250, 0, 1),
    ("artifact-iron-sword", "玄铁飞剑", "法宝", "凡品", "最常见的攻伐法宝，斗法时略增伤势。", 360, 0, 1),
    ("artifact-cloud-bell", "青云铃", "法宝", "黄阶", "铃音可稳住心神，闭关与斗法皆有助益。", 680, 0, 1),
    ("artifact-flame-seal", "赤焰印", "法宝", "黄阶", "火性攻伐法宝，适合霸烈战诀与火灵根。", 760, 0, 1),
    ("artifact-wind-boots", "追风履", "法宝", "玄阶", "身法类法宝，斗法时更易抢得先机。", 980, 0, 1),
    ("artifact-thunder-banner", "引雷幡", "法宝", "玄阶", "雷性法宝，擅长迟滞敌手气机。", 1180, 0, 1),
    ("artifact-mirror-jade", "照心玉", "法宝", "玄阶", "辅助参玄悟道，也能在斗法中稳住神识。", 1280, 0, 1),
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
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.executescript(SCHEMA_SQL)
        _ensure_schema_compatibility(connection)
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
              id, name, realm_requirement, grade, method_type, affinity, style,
              practice_bonus, breakthrough_bonus, insight_bonus,
              source_sect_id, required_rebirth_count, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEFAULT_METHODS,
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO items (
              id, name, item_type, rarity, description, base_price, consumable, tradable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            DEFAULT_ITEMS,
        )
        connection.commit()
    return db_path


def _ensure_schema_compatibility(connection: sqlite3.Connection) -> None:
    player_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(players)").fetchall()
    }
    if "age_progress" not in player_columns:
        connection.execute(
            "ALTER TABLE players ADD COLUMN age_progress INTEGER NOT NULL DEFAULT 0"
        )

    player_method_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(player_methods)").fetchall()
    }
    if "mastery" not in player_method_columns:
        connection.execute(
            "ALTER TABLE player_methods ADD COLUMN mastery INTEGER NOT NULL DEFAULT 0"
        )
    if "equipped" not in player_method_columns:
        connection.execute(
            "ALTER TABLE player_methods ADD COLUMN equipped INTEGER NOT NULL DEFAULT 0"
        )

    player_column_defaults = {
        "root_affinity": "木",
        "root_purity": 60,
        "root_temperament": "中正",
        "root_trait": "聚灵",
        "insight": 0,
        "breakthrough_ready": 0,
        "destiny_type": None,
        "destiny_level": 0,
        "primary_method_id": None,
        "equipped_artifact_id": None,
        "meditation_mode": None,
        "meditation_insight_reward": 0,
        "meditation_breakthrough_reward": 0,
    }
    for column, default_value in player_column_defaults.items():
        if column in player_columns:
            continue
        if default_value is None:
            connection.execute(f"ALTER TABLE players ADD COLUMN {column} TEXT")
        elif isinstance(default_value, str):
            connection.execute(
                f"ALTER TABLE players ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default_value}'"
            )
        else:
            connection.execute(
                f"ALTER TABLE players ADD COLUMN {column} INTEGER NOT NULL DEFAULT {default_value}"
            )

    method_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(cultivation_methods)").fetchall()
    }
    method_column_defaults = {
        "grade": ("TEXT", "'凡品'"),
        "method_type": ("TEXT", "'心法'"),
        "affinity": ("TEXT", "'土'"),
        "style": ("TEXT", "'绵长'"),
        "insight_bonus": ("REAL", "0"),
        "description": ("TEXT", "''"),
    }
    for column, (column_type, default_sql) in method_column_defaults.items():
        if column in method_columns:
            continue
        connection.execute(
            f"ALTER TABLE cultivation_methods ADD COLUMN {column} {column_type} NOT NULL DEFAULT {default_sql}"
        )

    artifact_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(player_artifacts)").fetchall()
    }
    if not artifact_columns:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS player_artifacts (
              user_id TEXT NOT NULL,
              item_id TEXT NOT NULL,
              mastery INTEGER NOT NULL DEFAULT 0,
              equipped INTEGER NOT NULL DEFAULT 0,
              acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (user_id, item_id),
              FOREIGN KEY (user_id) REFERENCES players(user_id),
              FOREIGN KEY (item_id) REFERENCES items(id)
            )
            """
        )
