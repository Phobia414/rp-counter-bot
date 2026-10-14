import aiosqlite
from datetime import datetime, timezone, timedelta
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rp_stats (
                user_id INTEGER,
                chat_id INTEGER,
                thread_id INTEGER DEFAULT 0,
                date_key TEXT,
                rp_chars INTEGER DEFAULT 0,
                offtop_chars INTEGER DEFAULT 0,
                rp_posts INTEGER DEFAULT 0,
                offtop_posts INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, chat_id, thread_id, date_key)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_rp_chat_thread_date
            ON rp_stats (chat_id, thread_id, date_key)
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS rp_user_names (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT ''
            )
        """)

        # ЧЁРНЫЙ СПИСОК: чаты, где счётчик ВЫКЛЮЧЕН.
        # По умолчанию — все чаты ВКЛЮЧЕНЫ.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rp_disabled_chats (
                chat_id INTEGER PRIMARY KEY,
                disabled_at TEXT DEFAULT ''
            )
        """)

        await db.commit()


# ============ RP STATS ============
async def add_rp_chars(user_id, chat_id, thread_id, date_key, rp_chars, offtop_chars):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO rp_stats
                (user_id, chat_id, thread_id, date_key, rp_chars, offtop_chars, rp_posts, offtop_posts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, chat_id, thread_id, date_key) DO UPDATE SET
                rp_chars = rp_chars + excluded.rp_chars,
                offtop_chars = offtop_chars + excluded.offtop_chars,
                rp_posts = rp_posts + excluded.rp_posts,
                offtop_posts = offtop_posts + excluded.offtop_posts
        """, (
            user_id, chat_id, thread_id, date_key,
            rp_chars, offtop_chars,
            1 if rp_chars > 0 else 0,
            1 if offtop_chars > 0 else 0,
        ))
        await db.commit()


async def get_rp_top(chat_id, thread_id, date_keys):
    if not date_keys:
        return []
    placeholders = ",".join("?" * len(date_keys))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(f"""
            SELECT
                rp_stats.user_id,
                IFNULL(u.first_name, '') AS first_name,
                IFNULL(u.username, '') AS username,
                SUM(rp_stats.rp_chars) AS total_rp,
                SUM(rp_stats.offtop_chars) AS total_off,
                SUM(rp_stats.rp_posts) AS rp_posts,
                SUM(rp_stats.offtop_posts) AS offtop_posts
            FROM rp_stats
            LEFT JOIN rp_user_names u ON u.user_id = rp_stats.user_id
            WHERE rp_stats.chat_id = ?
              AND rp_stats.thread_id = ?
              AND rp_stats.date_key IN ({placeholders})
            GROUP BY rp_stats.user_id
            ORDER BY total_rp DESC
        """, (chat_id, thread_id, *date_keys)) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def clear_old_rp_stats(days_keep=8):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_keep)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM rp_stats WHERE date_key < ?", (cutoff,))
        await db.commit()


async def remember_user_name(user_id, first_name, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO rp_user_names (user_id, first_name, username)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                first_name = excluded.first_name,
                username = excluded.username
        """, (user_id, first_name or "", username or ""))
        await db.commit()


# ============ ЧЁРНЫЙ СПИСОК ЧАТОВ ============
async def enable_rp_chat(chat_id):
    """Убирает чат из чёрного списка (включает счётчик)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM rp_disabled_chats WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def disable_rp_chat(chat_id):
    """Добавляет чат в чёрный список (выключает счётчик)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO rp_disabled_chats (chat_id, disabled_at) VALUES (?, ?)",
            (chat_id, datetime.now(timezone.utc).isoformat())
        )
        await db.commit()


async def is_rp_chat_enabled(chat_id):
    """True, если чат НЕ в чёрном списке. По умолчанию — включён."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM rp_disabled_chats WHERE chat_id = ?", (chat_id,)
        ) as cur:
            return await cur.fetchone() is None


async def cleanup_old_data():
    await clear_old_rp_stats(days_keep=8)
