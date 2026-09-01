from datetime import datetime

from database.db import get_connection, _is_sqlite_connection


VALID_KINDS = {"own", "ads"}
MEMBER_STATUSES = {"member", "administrator", "creator", "restricted"}
DEFAULT_MESSAGE = "🔒 برای استفاده از PFAST_AI ابتدا باید در کانال‌های زیر عضو شوید."


def _ensure_tables():
    conn = get_connection()
    cursor = conn.cursor()
    if _is_sqlite_connection(conn):
        channels_sql = """
        CREATE TABLE IF NOT EXISTS mandatory_channels(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL CHECK(kind IN ('own','ads')),
            title TEXT NOT NULL DEFAULT '',
            chat_id TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL DEFAULT '',
            invite_link TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        settings_id_sql = "id INTEGER PRIMARY KEY"
    else:
        channels_sql = """
        CREATE TABLE IF NOT EXISTS mandatory_channels(
            id BIGSERIAL PRIMARY KEY,
            kind TEXT NOT NULL CHECK(kind IN ('own','ads')),
            title TEXT NOT NULL DEFAULT '',
            chat_id TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL DEFAULT '',
            invite_link TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
        settings_id_sql = "id INTEGER PRIMARY KEY"
    cursor.execute(channels_sql)
    cursor.execute(
        f"""CREATE TABLE IF NOT EXISTS mandatory_join_settings(
            {settings_id_sql},
            message TEXT NOT NULL DEFAULT ''
        )"""
    )
    cursor.execute(
        """
        INSERT INTO mandatory_join_settings(id, message) VALUES(1, ?)
        ON CONFLICT(id) DO NOTHING
        """,
        (DEFAULT_MESSAGE,),
    )
    conn.commit()
    conn.close()


def add_channel(kind, chat_id, title="", username="", invite_link=""):
    _ensure_tables()
    kind = (kind or "").strip().lower()
    chat_id = str(chat_id or "").strip()
    if kind not in VALID_KINDS:
        raise ValueError("kind must be own or ads")
    if not chat_id:
        raise ValueError("chat_id is required")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO mandatory_channels(kind,title,chat_id,username,invite_link,active,created_at)
        VALUES(?,?,?,?,?,1,?)
        ON CONFLICT(chat_id) DO UPDATE SET
            kind=excluded.kind,
            title=excluded.title,
            username=excluded.username,
            invite_link=excluded.invite_link,
            active=1
        """,
        (kind, str(title or "").strip(), chat_id,
         str(username or "").strip().lstrip("@"),
         str(invite_link or "").strip(), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def remove_channel(channel_id):
    _ensure_tables()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mandatory_channels WHERE id=?", (int(channel_id),))
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def set_channel_active(channel_id, active):
    _ensure_tables()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE mandatory_channels SET active=? WHERE id=?",
        (1 if active else 0, int(channel_id)),
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_channels(kind=None, active_only=False):
    _ensure_tables()
    sql = (
        "SELECT id,kind,title,chat_id,username,invite_link,active,created_at "
        "FROM mandatory_channels"
    )
    params = []
    clauses = []
    if kind:
        clauses.append("kind=?")
        params.append(kind)
    if active_only:
        clauses.append("active=1")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "kind": r[1], "title": r[2], "chat_id": r[3],
            "username": r[4], "invite_link": r[5], "active": bool(r[6]), "created_at": r[7],
        }
        for r in rows
    ]


def get_channel(channel_id):
    try:
        channel_id = int(channel_id)
    except (TypeError, ValueError):
        return None
    return next((c for c in get_channels() if c["id"] == channel_id), None)


def get_display_name(channel):
    return channel.get("title") or channel.get("username") or channel.get("chat_id") or "کانال"


def get_mandatory_join_message():
    _ensure_tables()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT message FROM mandatory_join_settings WHERE id=1")
    row = cursor.fetchone()
    conn.close()
    return (row[0] if row and row[0] else DEFAULT_MESSAGE)


def set_mandatory_join_message(message):
    message = str(message or "").strip()
    if not message:
        raise ValueError("message is empty")
    _ensure_tables()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO mandatory_join_settings(id,message) VALUES(1,?)
        ON CONFLICT(id) DO UPDATE SET message=excluded.message
        """,
        (message,),
    )
    conn.commit()
    conn.close()


async def get_missing_channels(bot, user_id):
    missing = []
    for channel in get_channels(active_only=True):
        try:
            member = await bot.get_chat_member(channel["chat_id"], user_id)
            if member.status not in MEMBER_STATUSES:
                missing.append(channel)
        except Exception:
            missing.append(channel)
    return missing
