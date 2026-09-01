import json
import os
import re
import sqlite3

from datetime import datetime

from config import BOT_USERNAME, BASE_DIR
from core.logger import logger


# ========================================================
# Database Configuration
# ========================================================

DB_NAME = os.path.join(
    BASE_DIR,
    "database",
    "users.db",
)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


# ========================================================
# PostgreSQL Compatibility Wrapper
# ========================================================

class PGCursor:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        converted_sql = sql.replace("?", "%s")
        if params is None:
            return self._cur.execute(converted_sql)
        return self._cur.execute(converted_sql, params)

    def executemany(self, sql, seq_of_params):
        return self._cur.executemany(
            sql.replace("?", "%s"),
            seq_of_params,
        )

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __getattr__(self, item):
        return getattr(self._cur, item)


class PGConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return PGCursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        try:
            return self._conn.close()
        except Exception:
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
        finally:
            self.close()


# ========================================================
# Connection
# ========================================================

def _connect_postgresql():
    import psycopg2

    return PGConnection(
        psycopg2.connect(DATABASE_URL)
    )


def get_connection():
    os.makedirs(
        os.path.join(BASE_DIR, "database"),
        exist_ok=True,
    )

    if DATABASE_URL:
        try:
            return _connect_postgresql()
        except Exception as exc:
            logger.error(
                f"POSTGRES CONNECTION FAILED: {exc}"
                )

            logger.warning(
                "FALLBACK: SQLite"
            )

    conn = sqlite3.connect(
        DB_NAME,
        timeout=30,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _is_sqlite_connection(conn):
    return isinstance(conn, sqlite3.Connection)


# ========================================================
# Schema
# ========================================================

SQLITE_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT NOT NULL DEFAULT '',
        first_name TEXT NOT NULL DEFAULT '',
        nickname TEXT NOT NULL DEFAULT '',
        bio TEXT NOT NULL DEFAULT '',
        interests TEXT NOT NULL DEFAULT '',
        plan TEXT NOT NULL DEFAULT 'free',
        CHECK(length(plan) > 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        due_date TEXT NOT NULL DEFAULT '',
        completed INTEGER NOT NULL DEFAULT 0
            CHECK(completed IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        memory_key TEXT NOT NULL,
        memory_value TEXT NOT NULL DEFAULT '',
        UNIQUE(user_id, memory_key),
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qa_cache(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        normalized_question TEXT NOT NULL,
        answer TEXT NOT NULL,
        prompt_version TEXT NOT NULL DEFAULT '1',
        provider TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL DEFAULT '',
        UNIQUE(
            user_id,
            normalized_question,
            prompt_version,
            provider,
            model
        ),
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_state(
        user_id INTEGER PRIMARY KEY,
        active_project TEXT NOT NULL DEFAULT '',
        current_goal TEXT NOT NULL DEFAULT '',
        preferences TEXT NOT NULL DEFAULT '{}',
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        daily_messages INTEGER NOT NULL DEFAULT 30
            CHECK(daily_messages >= 0),
        daily_images INTEGER NOT NULL DEFAULT 2
            CHECK(daily_images >= 0),
        daily_technical_questions INTEGER NOT NULL DEFAULT 3
            CHECK(daily_technical_questions >= 0),
        cooldown_seconds INTEGER NOT NULL DEFAULT 5
            CHECK(cooldown_seconds >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_prices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_name TEXT NOT NULL UNIQUE,
        duration_days INTEGER NOT NULL DEFAULT 30
            CHECK(duration_days > 0),
        price INTEGER NOT NULL DEFAULT 0
            CHECK(price >= 0),
        currency TEXT NOT NULL DEFAULT 'IRR',
        is_active INTEGER NOT NULL DEFAULT 1
            CHECK(is_active IN (0, 1)),
        FOREIGN KEY(plan_name)
            REFERENCES plans(name)
            ON DELETE RESTRICT
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        plan TEXT NOT NULL DEFAULT 'free',
        start_date TEXT,
        duration_days INTEGER NOT NULL DEFAULT 0
            CHECK(duration_days >= 0),
        status TEXT NOT NULL DEFAULT 'inactive',
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
        FOREIGN KEY(plan)
            REFERENCES plans(name)
            ON DELETE RESTRICT
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        messages INTEGER NOT NULL DEFAULT 0
            CHECK(messages >= 0),
        images INTEGER NOT NULL DEFAULT 0
            CHECK(images >= 0),
        code_requests INTEGER NOT NULL DEFAULT 0
            CHECK(code_requests >= 0),
        searches INTEGER NOT NULL DEFAULT 0
            CHECK(searches >= 0),
        UNIQUE(user_id, date),
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rate_limit(
        user_id INTEGER PRIMARY KEY,
        last_request REAL NOT NULL DEFAULT 0,
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payment_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plan_name TEXT NOT NULL,
        duration_days INTEGER NOT NULL DEFAULT 30
            CHECK(duration_days > 0),
        amount INTEGER NOT NULL DEFAULT 0
            CHECK(amount >= 0),
        currency TEXT NOT NULL DEFAULT 'IRR',
        gateway TEXT NOT NULL DEFAULT 'placeholder',
        gateway_reference TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
        FOREIGN KEY(plan_name)
            REFERENCES plans(name)
            ON DELETE RESTRICT
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referral_settings(
        id INTEGER PRIMARY KEY CHECK(id = 1),
        required_invites INTEGER NOT NULL DEFAULT 3
            CHECK(required_invites > 0),
        reward_days INTEGER NOT NULL DEFAULT 3
            CHECK(reward_days > 0),
        reward_plan TEXT NOT NULL DEFAULT 'pro',
        FOREIGN KEY(reward_plan)
            REFERENCES plans(name)
            ON DELETE RESTRICT
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referrals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inviter_id INTEGER NOT NULL,
        invited_id INTEGER NOT NULL,
        reward_given INTEGER NOT NULL DEFAULT 0
            CHECK(reward_given IN (0, 1)),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(inviter_id, invited_id),
        CHECK(inviter_id <> invited_id),
        FOREIGN KEY(inviter_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
        FOREIGN KEY(invited_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS banned_users(
        user_id INTEGER PRIMARY KEY,
        reason TEXT NOT NULL DEFAULT '',
        banned_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
    )
    """,
)


POSTGRES_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users(
        id BIGINT PRIMARY KEY,
        username TEXT NOT NULL DEFAULT '',
        first_name TEXT NOT NULL DEFAULT '',
        nickname TEXT NOT NULL DEFAULT '',
        bio TEXT NOT NULL DEFAULT '',
        interests TEXT NOT NULL DEFAULT '',
        plan TEXT NOT NULL DEFAULT 'free'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        role TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        due_date TEXT NOT NULL DEFAULT '',
        completed INTEGER NOT NULL DEFAULT 0
            CHECK(completed IN (0,1)),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        memory_key TEXT NOT NULL,
        memory_value TEXT NOT NULL DEFAULT '',
        UNIQUE(user_id, memory_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qa_cache(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        question TEXT NOT NULL,
        normalized_question TEXT NOT NULL,
        answer TEXT NOT NULL,
        prompt_version TEXT NOT NULL DEFAULT '1',
        provider TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL DEFAULT '',
        UNIQUE(
            user_id,
            normalized_question,
            prompt_version,
            provider,
            model
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_state(
        user_id BIGINT PRIMARY KEY REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        active_project TEXT NOT NULL DEFAULT '',
        current_goal TEXT NOT NULL DEFAULT '',
        preferences TEXT NOT NULL DEFAULT '{}'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plans(
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        daily_messages INTEGER NOT NULL DEFAULT 30 CHECK(daily_messages >= 0),
        daily_images INTEGER NOT NULL DEFAULT 2 CHECK(daily_images >= 0),
        daily_technical_questions INTEGER NOT NULL DEFAULT 3
            CHECK(daily_technical_questions >= 0),
        cooldown_seconds INTEGER NOT NULL DEFAULT 5
            CHECK(cooldown_seconds >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plan_prices(
        id BIGSERIAL PRIMARY KEY,
        plan_name TEXT NOT NULL UNIQUE REFERENCES plans(name)
            ON DELETE RESTRICT ON UPDATE CASCADE,
        duration_days INTEGER NOT NULL DEFAULT 30 CHECK(duration_days > 0),
        price INTEGER NOT NULL DEFAULT 0 CHECK(price >= 0),
        currency TEXT NOT NULL DEFAULT 'IRR',
        is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL UNIQUE REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        plan TEXT NOT NULL DEFAULT 'free' REFERENCES plans(name)
            ON DELETE RESTRICT ON UPDATE CASCADE,
        start_date TEXT,
        duration_days INTEGER NOT NULL DEFAULT 0 CHECK(duration_days >= 0),
        status TEXT NOT NULL DEFAULT 'inactive'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS usage(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        date TEXT NOT NULL,
        messages INTEGER NOT NULL DEFAULT 0 CHECK(messages >= 0),
        images INTEGER NOT NULL DEFAULT 0 CHECK(images >= 0),
        code_requests INTEGER NOT NULL DEFAULT 0 CHECK(code_requests >= 0),
        searches INTEGER NOT NULL DEFAULT 0 CHECK(searches >= 0),
        UNIQUE(user_id, date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rate_limit(
        user_id BIGINT PRIMARY KEY REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        last_request DOUBLE PRECISION NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS payment_requests(
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        plan_name TEXT NOT NULL REFERENCES plans(name)
            ON DELETE RESTRICT ON UPDATE CASCADE,
        duration_days INTEGER NOT NULL DEFAULT 30 CHECK(duration_days > 0),
        amount INTEGER NOT NULL DEFAULT 0 CHECK(amount >= 0),
        currency TEXT NOT NULL DEFAULT 'IRR',
        gateway TEXT NOT NULL DEFAULT 'placeholder',
        gateway_reference TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referral_settings(
        id INTEGER PRIMARY KEY CHECK(id = 1),
        required_invites INTEGER NOT NULL DEFAULT 3 CHECK(required_invites > 0),
        reward_days INTEGER NOT NULL DEFAULT 3 CHECK(reward_days > 0),
        reward_plan TEXT NOT NULL DEFAULT 'pro'
            REFERENCES plans(name) ON DELETE RESTRICT ON UPDATE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS referrals(
        id BIGSERIAL PRIMARY KEY,
        inviter_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        invited_id BIGINT NOT NULL REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        reward_given INTEGER NOT NULL DEFAULT 0 CHECK(reward_given IN (0,1)),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(inviter_id, invited_id),
        CHECK(inviter_id <> invited_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS banned_users(
        user_id BIGINT PRIMARY KEY REFERENCES users(id)
            ON DELETE CASCADE ON UPDATE CASCADE,
        reason TEXT NOT NULL DEFAULT '',
        banned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_user_id ON memory(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_qa_cache_lookup "
    "ON qa_cache(user_id, normalized_question, prompt_version)",
    "CREATE INDEX IF NOT EXISTS idx_qa_cache_expires_at "
    "ON qa_cache(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_payment_requests_user_id "
    "ON payment_requests(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_payment_requests_status "
    "ON payment_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_referrals_inviter_id "
    "ON referrals(inviter_id)",
    "CREATE INDEX IF NOT EXISTS idx_referrals_invited_id "
    "ON referrals(invited_id)",
    "CREATE INDEX IF NOT EXISTS idx_usage_user_date "
    "ON usage(user_id, date)",
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_status "
    "ON subscriptions(status)",
    "CREATE INDEX IF NOT EXISTS idx_banned_users_user_id "
    "ON banned_users(user_id)",
)


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    schema = (
        POSTGRES_SCHEMA
        if DATABASE_URL and not _is_sqlite_connection(conn)
        else SQLITE_SCHEMA
    )

    for statement in schema:
        cursor.execute(statement)

    if DATABASE_URL and not _is_sqlite_connection(conn):
        for index_sql in INDEXES:
            cursor.execute(index_sql)
    else:
        for index_sql in INDEXES:
            cursor.execute(index_sql)

    _seed_defaults(cursor)
    conn.commit()
    conn.close()


def _seed_defaults(cursor):
    cursor.execute(
    """
    INSERT INTO plans
    (
        name,
        daily_messages,
        daily_images,
        daily_technical_questions,
        cooldown_seconds
    )
    VALUES
    (?, ?, ?, ?, ?),
    (?, ?, ?, ?, ?),
    (?, ?, ?, ?, ?)
    ON CONFLICT DO NOTHING
    """,
    (
        "free", 30, 1, 3, 5,
        "pro", 1000, 2, 10, 1,
        "ultra", 999999, 4, 99999, 0,
    ),
)

    cursor.execute(
        """
        INSERT INTO plan_prices
        (
            plan_name,
            duration_days,
            price,
            currency,
            is_active
        )
        VALUES
        (?, ?, ?, ?, ?),
        (?, ?, ?, ?, ?),
        (?, ?, ?, ?, ?)
        ON CONFLICT(plan_name) DO NOTHING
        """,
        (
            "free", 30, 0, "IRR", 1,
            "pro", 30, 300000, "IRR", 1,
            "ultra", 30, 700000, "IRR", 1,
        ),
    )

    cursor.execute(
        """
        INSERT INTO referral_settings(
            id,
            required_invites,
            reward_days,
            reward_plan
        )
        VALUES(1, 3, 3, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        ("pro",),
    )


# ========================================================
# Text Helpers
# ========================================================

def normalize_text(text):
    return " ".join(
        str(text or "")
        .strip()
        .lower()
        .split()
    )


def _parse_price_value(value):
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    text = str(value).strip()
    if not text:
        return None

    text = text.translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    )
    text = (
        text
        .replace("٫", ".")
        .replace("٬", "")
        .replace("،", "")
    )
    text = re.sub(r"(\d)/(\d)", r"\1\2", text)
    text = re.sub(r"[^\w\s.-]", " ", text)

    tokens = [token for token in re.split(r"\s+", text) if token]
    if not tokens:
        return None

    number = None

    units = {
        "هزار": 1000,
        "k": 1000,
        "thousand": 1000,
        "میلیون": 1_000_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "میلیارد": 1_000_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
    }

    currencies = {
        "تومان",
        "toman",
        "t",
        "rial",
        "irr",
        "ریال",
    }

    for token in tokens:
        lower = token.lower()

        if lower in currencies:
            continue

        if lower in units:
            if number is not None:
                number *= units[lower]
            continue

        match = re.fullmatch(r"([0-9]+)([^0-9]+)?", token)
        if match:
            parsed = int(match.group(1))
            suffix = (match.group(2) or "").lower()
            if suffix in units:
                parsed *= units[suffix]

            if number is None:
                number = parsed
            else:
                number = int(f"{number}{parsed}")
            continue

        try:
            parsed = int(float(token))
        except ValueError:
            continue

        if number is None:
            number = parsed
        else:
            number = int(f"{number}{parsed}")

    return number


# ========================================================
# Cache
# ========================================================

def get_cached_answer(
    user_id,
    question,
    prompt_version="1",
    provider=None,
    model=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    normalized_question = normalize_text(question)
    now = datetime.now().isoformat()

    cursor.execute(
        """
        DELETE FROM qa_cache
        WHERE expires_at != ''
        AND expires_at < ?
        """,
        (now,),
    )

    query = """
        SELECT answer
        FROM qa_cache
        WHERE user_id=?
        AND normalized_question=?
        AND prompt_version=?
    """
    params = [
        user_id,
        normalized_question,
        prompt_version or "1",
    ]

    if provider is not None:
        query += " AND provider=?"
        params.append(provider)

    if model is not None:
        query += " AND model=?"
        params.append(model)

    query += " ORDER BY id DESC LIMIT 1"

    cursor.execute(query, tuple(params))
    row = cursor.fetchone()

    conn.commit()
    conn.close()

    return row[0] if row else None


def save_cached_answer(
    user_id,
    question,
    answer,
    prompt_version="1",
    provider="",
    model="",
    expires_at="",
):
    conn = get_connection()
    cursor = conn.cursor()

    normalized_question = normalize_text(question)
    now = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO qa_cache
        (
            user_id,
            question,
            normalized_question,
            answer,
            prompt_version,
            provider,
            model,
            created_at,
            expires_at
        )
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(
            user_id,
            normalized_question,
            prompt_version,
            provider,
            model
        )
        DO UPDATE SET
            question=excluded.question,
            answer=excluded.answer,
            created_at=excluded.created_at,
            expires_at=excluded.expires_at
        """,
        (
            user_id,
            question,
            normalized_question,
            answer,
            prompt_version or "1",
            provider or "",
            model or "",
            now,
            expires_at or "",
        ),
    )

    conn.commit()
    conn.close()


def delete_expired_cached_answers():
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute(
        """
        DELETE FROM qa_cache
        WHERE expires_at != ''
        AND expires_at < ?
        """,
        (now,),
    )

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted


def clear_user_cache(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM qa_cache WHERE user_id=?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def clear_all_cache():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM qa_cache")
    conn.commit()
    conn.close()


# ========================================================
# Users
# ========================================================

def add_user(user_id, username="", first_name=""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO users(id, username, first_name)
        VALUES(?, ?, ?)
        ON CONFLICT(id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (user_id, username or "", first_name or ""),
    )

    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users ORDER BY id")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def get_all_users_info(limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            username,
            first_name,
            plan
        FROM users
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_user_info(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            username,
            first_name,
            nickname,
            bio,
            interests,
            plan
        FROM users
        WHERE id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()
    return row


def get_user_plan(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT plan FROM users WHERE id=?",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return row[0] if row and row[0] else "free"


def update_user_plan(user_id, plan):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET plan=? WHERE id=?",
        ((plan or "free").lower(), user_id),
    )
    conn.commit()
    conn.close()


def get_plan_counts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT plan, COUNT(*)
        FROM users
        GROUP BY plan
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


# ========================================================
# Profile
# ========================================================

def get_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            username,
            first_name,
            nickname,
            bio,
            interests
        FROM users
        WHERE id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if not row:
        return {}

    return {
        "username": row[0],
        "first_name": row[1],
        "nickname": row[2],
        "bio": row[3],
        "interests": row[4],
    }


def update_profile(
    user_id,
    nickname=None,
    bio=None,
    interests=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET
            nickname=COALESCE(?, nickname),
            bio=COALESCE(?, bio),
            interests=COALESCE(?, interests)
        WHERE id=?
        """,
        (
            nickname,
            bio,
            interests,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


# ========================================================
# Messages
# ========================================================

def save_message(user_id, role, message):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO messages(user_id, role, message)
        VALUES(?, ?, ?)
        """,
        (user_id, role, message),
    )

    conn.commit()
    conn.close()


def get_history(user_id, limit=10):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT role, message
        FROM messages
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT ?
        """,
        (user_id, limit),
    )

    rows = cursor.fetchall()
    conn.close()
    return rows[::-1]


def get_user_message_count(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE user_id=?",
        (user_id,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_message_history(user_id, limit=5):
    return get_history(user_id, limit)


def clear_history(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM messages WHERE user_id=?",
        (user_id,),
    )
    conn.commit()
    conn.close()


# ========================================================
# Memory
# ========================================================

def save_memory(user_id, key, value):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO memory(user_id, memory_key, memory_value)
        VALUES(?, ?, ?)
        ON CONFLICT(user_id, memory_key)
        DO UPDATE SET
            memory_value=excluded.memory_value
        """,
        (user_id, key, str(value)),
    )

    conn.commit()
    conn.close()


def get_memories(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT memory_key, memory_value
        FROM memory
        WHERE user_id=?
        ORDER BY id
        """,
        (user_id,),
    )
    data = cursor.fetchall()
    conn.close()
    return data


def clear_memory(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM memory WHERE user_id=?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def clear_user_memory(user_id):
    clear_memory(user_id)


# ========================================================
# User State
# ========================================================

def get_state(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            active_project,
            current_goal,
            preferences
        FROM user_state
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "active_project": "",
            "current_goal": "",
            "preferences": {},
        }

    try:
        preferences = json.loads(row[2]) if row[2] else {}
    except (TypeError, ValueError):
        preferences = {}

    return {
        "active_project": row[0] or "",
        "current_goal": row[1] or "",
        "preferences": preferences,
    }


def save_state(
    user_id,
    active_project=None,
    current_goal=None,
    preferences=None,
):
    current = get_state(user_id)

    active_project = (
        active_project
        if active_project is not None
        else current["active_project"]
    )
    current_goal = (
        current_goal
        if current_goal is not None
        else current["current_goal"]
    )
    preferences = (
        preferences
        if preferences is not None
        else current["preferences"]
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO user_state(
            user_id,
            active_project,
            current_goal,
            preferences
        )
        VALUES(?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            active_project=excluded.active_project,
            current_goal=excluded.current_goal,
            preferences=excluded.preferences
        """,
        (
            user_id,
            active_project or "",
            current_goal or "",
            json.dumps(
                preferences or {},
                ensure_ascii=False,
            ),
        ),
    )

    conn.commit()
    conn.close()


# ========================================================
# Tasks Compatibility Helpers
# ========================================================

def create_task(
    user_id,
    title,
    description="",
    due_date="",
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO tasks(
            user_id,
            title,
            description,
            due_date,
            completed
        )
        VALUES(?, ?, ?, ?, 0)
        """,
        (
            user_id,
            title,
            description or "",
            due_date or "",
        ),
    )

    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(user_id, include_completed=False):
    conn = get_connection()
    cursor = conn.cursor()

    if include_completed:
        cursor.execute(
            """
            SELECT id, title, description, due_date, completed, created_at
            FROM tasks
            WHERE user_id=?
            ORDER BY id DESC
            """,
            (user_id,),
        )
    else:
        cursor.execute(
            """
            SELECT id, title, description, due_date, completed, created_at
            FROM tasks
            WHERE user_id=?
            AND completed=0
            ORDER BY id DESC
            """,
            (user_id,),
        )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "due_date": row[3],
            "completed": bool(row[4]),
            "created_at": row[5],
        }
        for row in rows
    ]


# ========================================================
# Price / Plan
# ========================================================

def set_plan_price(
    plan_name,
    price,
    duration_days=30,
    currency="IRR",
):
    normalized_price = _parse_price_value(price)

    if normalized_price is None:
        raise ValueError("price could not be parsed")

    plan_name = (plan_name or "").lower().strip()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO plan_prices(
            plan_name,
            duration_days,
            price,
            currency,
            is_active
        )
        VALUES(?, ?, ?, ?, 1)
        ON CONFLICT(plan_name)
        DO UPDATE SET
            duration_days=excluded.duration_days,
            price=excluded.price,
            currency=excluded.currency,
            is_active=1
        """,
        (
            plan_name,
            duration_days,
            normalized_price,
            currency,
        ),
    )

    conn.commit()
    conn.close()

    return normalized_price


def get_plan_price(plan_name, duration_days=30):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT price, currency, is_active
        FROM plan_prices
        WHERE plan_name=?
        AND duration_days=?
        """,
        (
            (plan_name or "").lower(),
            duration_days,
        ),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "price": 0,
            "currency": "IRR",
            "is_active": True,
        }

    return {
        "price": row[0],
        "currency": row[1] or "IRR",
        "is_active": bool(row[2]),
    }


def get_plan_prices():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            plan_name,
            duration_days,
            price,
            currency,
            is_active
        FROM plan_prices
        ORDER BY plan_name
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return {
        row[0]: {
            "duration_days": row[1],
            "price": row[2],
            "currency": row[3] or "IRR",
            "is_active": bool(row[4]),
        }
        for row in rows
    }


# ========================================================
# Payments
# ========================================================

def create_payment_request(
    user_id,
    plan_name,
    amount,
    currency="IRR",
    duration_days=30,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO payment_requests(
            user_id,
            plan_name,
            duration_days,
            amount,
            currency,
            gateway,
            gateway_reference,
            status,
            created_at
        )
        VALUES(?, ?, ?, ?, ?, 'placeholder', '', 'pending', ?)
        """,
        (
            user_id,
            (plan_name or "").lower(),
            duration_days,
            amount,
            currency,
            datetime.now().isoformat(),
        ),
    )

    request_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return request_id


def get_payment_request(request_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_id,
            plan_name,
            duration_days,
            amount,
            currency,
            gateway,
            gateway_reference,
            status,
            created_at
        FROM payment_requests
        WHERE id=?
        """,
        (request_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "plan_name": row[2],
        "duration_days": row[3],
        "amount": row[4],
        "currency": row[5],
        "gateway": row[6],
        "gateway_reference": row[7],
        "status": row[8],
        "created_at": row[9],
    }


def update_payment_request_status(
    request_id,
    status,
    gateway_reference="",
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE payment_requests
        SET
            status=?,
            gateway_reference=?
        WHERE id=?
        """,
        (
            status,
            gateway_reference,
            request_id,
        ),
    )

    conn.commit()
    conn.close()


# ========================================================
# Referrals
# ========================================================

def get_referral_settings():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            required_invites,
            reward_days,
            reward_plan
        FROM referral_settings
        WHERE id=1
        """
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "required_invites": 3,
            "reward_days": 3,
            "reward_plan": "pro",
        }

    return {
        "required_invites": row[0] or 3,
        "reward_days": row[1] or 3,
        "reward_plan": row[2] or "pro",
    }


def set_referral_settings(
    required_invites=None,
    reward_days=None,
    reward_plan=None,
):
    current = get_referral_settings()

    values = {
        "required_invites": (
            required_invites
            if required_invites is not None
            else current["required_invites"]
        ),
        "reward_days": (
            reward_days
            if reward_days is not None
            else current["reward_days"]
        ),
        "reward_plan": (
            (reward_plan or current["reward_plan"]).lower()
        ),
    }

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO referral_settings(
            id,
            required_invites,
            reward_days,
            reward_plan
        )
        VALUES(1, ?, ?, ?)
        ON CONFLICT(id)
        DO UPDATE SET
            required_invites=excluded.required_invites,
            reward_days=excluded.reward_days,
            reward_plan=excluded.reward_plan
        """,
        (
            values["required_invites"],
            values["reward_days"],
            values["reward_plan"],
        ),
    )

    conn.commit()
    conn.close()


def get_referral_link(user_id):
    username = (BOT_USERNAME or "").strip()

    if username:
        return f"https://t.me/{username}?start=ref_{user_id}"

    return (
        "https://t.me/"
        "your_bot_username"
        f"?start=ref_{user_id}"
    )


def create_referral(inviter_id, invited_id):
    if inviter_id == invited_id:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM referrals
        WHERE inviter_id=?
        AND invited_id=?
        """,
        (
            inviter_id,
            invited_id,
        ),
    )

    if cursor.fetchone():
        conn.close()
        return None

    cursor.execute(
        """
        INSERT INTO referrals(
            inviter_id,
            invited_id,
            reward_given,
            created_at
        )
        VALUES(?, ?, 0, ?)
        """,
        (
            inviter_id,
            invited_id,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    maybe_grant_referral_reward(inviter_id)
    return True


def maybe_grant_referral_reward(inviter_id):
    settings = get_referral_settings()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(
                SUM(
                    CASE
                        WHEN reward_given=1 THEN 1
                        ELSE 0
                    END
                ),
                0
            )
        FROM referrals
        WHERE inviter_id=?
        """,
        (inviter_id,),
    )

    total, rewarded = cursor.fetchone()
    conn.close()

    if (
        total < settings["required_invites"]
        or rewarded > 0
    ):
        return False

    create_subscription(
        inviter_id,
        settings["reward_plan"],
        settings["reward_days"],
    )
    update_user_plan(
        inviter_id,
        settings["reward_plan"],
    )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE referrals
        SET reward_given=1
        WHERE inviter_id=?
        AND reward_given=0
        """,
        (inviter_id,),
    )

    conn.commit()
    conn.close()

    return True


def get_user_referral_stats(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(
                SUM(
                    CASE
                        WHEN reward_given=1 THEN 1
                        ELSE 0
                    END
                ),
                0
            )
        FROM referrals
        WHERE inviter_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "invites": 0,
            "rewarded": 0,
        }

    return {
        "invites": row[0] or 0,
        "rewarded": row[1] or 0,
    }


# ========================================================
# Ban System
# ========================================================

def ban_user(user_id, reason=""):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO banned_users(
            user_id,
            reason,
            banned_at
        )
        VALUES(?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            reason=excluded.reason,
            banned_at=excluded.banned_at
        """,
        (
            user_id,
            reason or "",
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM banned_users WHERE user_id=?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def is_user_banned(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM banned_users WHERE user_id=?",
        (user_id,),
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def get_ban_reason(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT reason, banned_at
        FROM banned_users
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "reason": row[0] or "",
            "banned_at": row[1] or "",
        }

    return {
        "reason": "",
        "banned_at": "",
    }


# ========================================================
# Statistics
# ========================================================

def get_total_messages():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_total_memories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM memory")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_total_cached_questions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM qa_cache")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_active_subscription_count():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM subscriptions
        WHERE status='active'
        """
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ========================================================
# Subscriptions
# ========================================================

def create_subscription(user_id, plan, days):
    today = datetime.now().date().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO subscriptions(
            user_id,
            plan,
            start_date,
            duration_days,
            status
        )
        VALUES(?, ?, ?, ?, 'active')
        ON CONFLICT(user_id)
        DO UPDATE SET
            plan=excluded.plan,
            start_date=excluded.start_date,
            duration_days=excluded.duration_days,
            status=excluded.status
        """,
        (
            user_id,
            (plan or "free").lower(),
            today,
            days,
        ),
    )

    conn.commit()
    conn.close()


def get_subscription(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            plan,
            start_date,
            duration_days,
            status
        FROM subscriptions
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "plan": "free",
            "start_date": "",
            "duration_days": 0,
            "status": "inactive",
        }

    return {
        "plan": row[0],
        "start_date": row[1],
        "duration_days": row[2],
        "status": row[3],
    }


# ========================================================
# Rate Limit
# ========================================================

def get_last_request(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT last_request
        FROM rate_limit
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else 0


def update_last_request(user_id, timestamp):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO rate_limit(user_id, last_request)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            last_request=excluded.last_request
        """,
        (
            user_id,
            timestamp,
        ),
    )

    conn.commit()
    conn.close()


# ========================================================
# Runtime State
# ========================================================

broadcast_messages = {}
admin_actions = {}


def set_broadcast_message(user_id, value=True):
    broadcast_messages[user_id] = value


def get_broadcast_message(user_id):
    return broadcast_messages.get(user_id)


def clear_broadcast_message(user_id):
    broadcast_messages.pop(user_id, None)


def set_admin_action(user_id, action):
    admin_actions[user_id] = action


def get_admin_action(user_id):
    return admin_actions.get(user_id)


def clear_admin_action(user_id):
    admin_actions.pop(user_id, None)


# ========================================================
# Database Rebuild / Migration
# ========================================================

def _safe_copy_rows(
    source_conn,
    target_conn,
    table,
    columns,
    transform=None,
):
    source_cursor = source_conn.cursor()
    target_cursor = target_conn.cursor()

    source_cursor.execute(
        f"SELECT {', '.join(columns)} FROM {table}"
    )

    rows = source_cursor.fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["?"] * len(columns))

    copied = 0

    for row in rows:
        values = transform(row) if transform else row

        try:
            target_cursor.execute(
                f"""
                INSERT OR IGNORE INTO {table}
                ({', '.join(columns)})
                VALUES ({placeholders})
                """,
                values,
            )
            copied += 1
        except sqlite3.IntegrityError:
            continue

    return copied


def rebuild_database():
    if DATABASE_URL:
        raise RuntimeError(
            "rebuild_database() is only for the local SQLite database."
        )

    if not os.path.exists(DB_NAME):
        raise FileNotFoundError(DB_NAME)

    init_target = DB_NAME + ".rebuild"

    if os.path.exists(init_target):
        os.remove(init_target)

    original_db = sqlite3.connect(DB_NAME)
    original_db.execute("PRAGMA foreign_keys = OFF")

    new_db = sqlite3.connect(init_target)
    new_db.execute("PRAGMA foreign_keys = ON")

    for statement in SQLITE_SCHEMA:
        new_db.execute(statement)

    for statement in INDEXES:
        new_db.execute(statement)

    # Seed defaults first so FK-dependent copies are valid.
    _seed_defaults(new_db.cursor())
    new_db.commit()

    users = _safe_copy_rows(
        original_db,
        new_db,
        "users",
        [
            "id",
            "username",
            "first_name",
            "nickname",
            "bio",
            "interests",
            "plan",
        ],
        transform=lambda row: (
            row[0],
            row[1] or "",
            row[2] or "",
            row[3] or "",
            row[4] or "",
            row[5] or "",
            row[6] or "free",
        ),
    )

    valid_user_ids = {
        row[0]
        for row in new_db.execute("SELECT id FROM users").fetchall()
    }

    def valid_user(row):
        return row[1] in valid_user_ids

    # Messages
    for row in original_db.execute(
        """
        SELECT id, user_id, role, message
        FROM messages
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO messages(
                id,
                user_id,
                role,
                message
            )
            VALUES(?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2] or "",
                row[3] or "",
            ),
        )

    # Tasks
    for row in original_db.execute(
        """
        SELECT id, user_id, title, description, due_date, completed, created_at
        FROM tasks
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO tasks(
                id,
                user_id,
                title,
                description,
                due_date,
                completed,
                created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2] or "",
                row[3] or "",
                row[4] or "",
                1 if row[5] else 0,
                row[6] or datetime.now().isoformat(),
            ),
        )

    # Memory
    for row in original_db.execute(
        """
        SELECT id, user_id, memory_key, memory_value
        FROM memory
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO memory(
                id,
                user_id,
                memory_key,
                memory_value
            )
            VALUES(?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3] or "",
            ),
        )

    # Cache
    old_cache_columns = {
        row[1]
        for row in original_db.execute(
            "PRAGMA table_info(qa_cache)"
        ).fetchall()
    }

    cache_select = [
        "id",
        "user_id",
        "question",
        "normalized_question",
        "answer",
    ]

    for column, default in (
        ("prompt_version", "1"),
        ("provider", ""),
        ("model", ""),
        ("created_at", ""),
        ("expires_at", ""),
    ):
        cache_select.append(
            column if column in old_cache_columns else f"'{default}' AS {column}"
        )

    for row in original_db.execute(
        f"SELECT {', '.join(cache_select)} FROM qa_cache"
    ):
        if row[1] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO qa_cache(
                id,
                user_id,
                question,
                normalized_question,
                answer,
                prompt_version,
                provider,
                model,
                created_at,
                expires_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2] or "",
                row[3] or normalize_text(row[2]),
                row[4] or "",
                row[5] or "1",
                row[6] or "",
                row[7] or "",
                row[8] or datetime.now().isoformat(),
                row[9] or "",
            ),
        )

    # User state
    for row in original_db.execute(
        """
        SELECT user_id, active_project, current_goal, preferences
        FROM user_state
        """
    ):
        if row[0] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO user_state(
                user_id,
                active_project,
                current_goal,
                preferences
            )
            VALUES(?, ?, ?, ?)
            """,
            (
                row[0],
                row[1] or "",
                row[2] or "",
                row[3] or "{}",
            ),
        )

    # Plans
    for row in original_db.execute(
        """
        SELECT
            name,
            daily_messages,
            daily_images,
            daily_technical_questions,
            cooldown_seconds
        FROM plans
        """
    ):
        new_db.execute(
            """
            INSERT INTO plans(
                name,
                daily_messages,
                daily_images,
                daily_technical_questions,
                cooldown_seconds
            )
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(name)
            DO UPDATE SET
                daily_messages=excluded.daily_messages,
                daily_images=excluded.daily_images,
                daily_technical_questions=excluded.daily_technical_questions,
                cooldown_seconds=excluded.cooldown_seconds
            """,
            (
                row[0],
                max(0, row[1] or 0),
                max(0, row[2] or 0),
                max(0, row[3] or 0),
                max(0, row[4] or 0),
            ),
        )

    # Plan prices
    for row in original_db.execute(
        """
        SELECT
            plan_name,
            duration_days,
            price,
            currency,
            is_active
        FROM plan_prices
        """
    ):
        try:
            new_db.execute(
                """
                INSERT INTO plan_prices(
                    plan_name,
                    duration_days,
                    price,
                    currency,
                    is_active
                )
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(plan_name)
                DO UPDATE SET
                    duration_days=excluded.duration_days,
                    price=excluded.price,
                    currency=excluded.currency,
                    is_active=excluded.is_active
                """,
                (
                    row[0],
                    row[1] or 30,
                    max(0, row[2] or 0),
                    row[3] or "IRR",
                    1 if row[4] else 0,
                ),
            )
        except sqlite3.IntegrityError:
            continue

    # Subscriptions
    for row in original_db.execute(
        """
        SELECT
            id,
            user_id,
            plan,
            start_date,
            duration_days,
            status
        FROM subscriptions
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        plan_exists = new_db.execute(
            "SELECT 1 FROM plans WHERE name=?",
            (row[2],),
        ).fetchone()

        if not plan_exists:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO subscriptions(
                id,
                user_id,
                plan,
                start_date,
                duration_days,
                status
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2] or "free",
                row[3],
                max(0, row[4] or 0),
                row[5] or "inactive",
            ),
        )

    # Usage
    for row in original_db.execute(
        """
        SELECT
            id,
            user_id,
            date,
            messages,
            images,
            code_requests,
            searches
        FROM usage
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO usage(
                id,
                user_id,
                date,
                messages,
                images,
                code_requests,
                searches
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                max(0, row[3] or 0),
                max(0, row[4] or 0),
                max(0, row[5] or 0),
                max(0, row[6] or 0),
            ),
        )

    # Rate limit
    if original_db.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table'
        AND name='rate_limit'
        """
    ).fetchone()[0]:
        for row in original_db.execute(
            "SELECT user_id, last_request FROM rate_limit"
        ):
            if row[0] not in valid_user_ids:
                continue

            new_db.execute(
                """
                INSERT OR IGNORE INTO rate_limit(
                    user_id,
                    last_request
                )
                VALUES(?, ?)
                """,
                (
                    row[0],
                    row[1] or 0,
                ),
            )

    # Payments
    for row in original_db.execute(
        """
        SELECT
            id,
            user_id,
            plan_name,
            duration_days,
            amount,
            currency,
            gateway,
            gateway_reference,
            status,
            created_at
        FROM payment_requests
        """
    ):
        if row[1] not in valid_user_ids:
            continue

        if not new_db.execute(
            "SELECT 1 FROM plans WHERE name=?",
            (row[2],),
        ).fetchone():
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO payment_requests(
                id,
                user_id,
                plan_name,
                duration_days,
                amount,
                currency,
                gateway,
                gateway_reference,
                status,
                created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                row[3] or 30,
                max(0, row[4] or 0),
                row[5] or "IRR",
                row[6] or "placeholder",
                row[7] or "",
                row[8] or "pending",
                row[9] or datetime.now().isoformat(),
            ),
        )

    # Referral settings
    referral_settings_table = original_db.execute(
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table'
        AND name='referral_settings'
        """
    ).fetchone()[0]

    if referral_settings_table:
        row = original_db.execute(
            """
            SELECT
                required_invites,
                reward_days,
                reward_plan
            FROM referral_settings
            WHERE id=1
            """
        ).fetchone()

        if row and new_db.execute(
            "SELECT 1 FROM plans WHERE name=?",
            (row[2],),
        ).fetchone():
            new_db.execute(
                """
                INSERT INTO referral_settings(
                    id,
                    required_invites,
                    reward_days,
                    reward_plan
                )
                VALUES(1, ?, ?, ?)
                ON CONFLICT(id)
                DO UPDATE SET
                    required_invites=excluded.required_invites,
                    reward_days=excluded.reward_days,
                    reward_plan=excluded.reward_plan
                """,
                (
                    max(1, row[0] or 3),
                    max(1, row[1] or 3),
                    row[2],
                ),
            )

    # Referrals
    for row in original_db.execute(
        """
        SELECT
            id,
            inviter_id,
            invited_id,
            reward_given,
            created_at
        FROM referrals
        """
    ):
        if (
            row[1] not in valid_user_ids
            or row[2] not in valid_user_ids
            or row[1] == row[2]
        ):
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO referrals(
                id,
                inviter_id,
                invited_id,
                reward_given,
                created_at
            )
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                row[0],
                row[1],
                row[2],
                1 if row[3] else 0,
                row[4] or datetime.now().isoformat(),
            ),
        )

    # Bans
    for row in original_db.execute(
        """
        SELECT user_id, reason, banned_at
        FROM banned_users
        """
    ):
        if row[0] not in valid_user_ids:
            continue

        new_db.execute(
            """
            INSERT OR IGNORE INTO banned_users(
                user_id,
                reason,
                banned_at
            )
            VALUES(?, ?, ?)
            """,
            (
                row[0],
                row[1] or "",
                row[2] or datetime.now().isoformat(),
            ),
        )

    new_db.commit()
    fk_errors = new_db.execute("PRAGMA foreign_key_check").fetchall()

    if fk_errors:
        new_db.close()
        original_db.close()
        os.remove(init_target)
        raise RuntimeError(
            f"Foreign key validation failed: {fk_errors}"
        )

    new_db.execute("PRAGMA optimize")
    new_db.commit()

    original_db.close()
    new_db.close()

    backup_path = DB_NAME + ".pre_rebuild_runtime"

    if os.path.exists(backup_path):
        os.remove(backup_path)

    os.replace(DB_NAME, backup_path)
    os.replace(init_target, DB_NAME)

    return {
        "backup": backup_path,
        "users": users,
        "database": DB_NAME,
    }


# ========================================================
# Auto Init
# ========================================================

if __name__ == "__main__":
    init_db()
