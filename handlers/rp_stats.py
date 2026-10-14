import re
from datetime import datetime, timezone

from aiogram import types, F
from aiogram.filters import Command

from bot_instance import dp
from config import RP_OWNER_ID
from db import (
    add_rp_chars, get_rp_top, remember_user_name,
    enable_rp_chat, disable_rp_chat, is_rp_chat_enabled,
)
from logger import get_logger

log = get_logger(__name__)


# ==================== ПАРСЕР ====================
def parse_message(text: str):
    """Возвращает (отыгрыш, оффтоп). Всё после // — оффтоп."""
    if not text:
        return "", ""
    idx = text.find("//")
    if idx != -1:
        return text[:idx], text[idx + 2:]
    return text, ""


def count_chars(text: str) -> int:
    """Считает ТОЛЬКО буквы. Пробелы, знаки, цифры, эмодзи — игнорируются."""
    if not text:
        return 0
    return len(re.sub(r"[\W\d_]", "", text, flags=re.UNICODE))


def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_thread_id(message: types.Message) -> int:
    return getattr(message, "message_thread_id", None) or 0


# ==================== ДОСТУП ====================
def is_bot_owner(message: types.Message) -> bool:
    if not message.from_user:
        return False
    return message.from_user.id == RP_OWNER_ID


# ==================== КОМАНДЫ (регистрируются ПЕРВЫМИ) ====================
@dp.message(Command("rp_on"))
async def cmd_rp_on(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    await enable_rp_chat(message.chat.id)

    await message.answer(
        "✅ <b>Счётчик РП включён в этом чате</b>\n\n"
        "<b>Команды:</b>\n"
        "• <code>/top_rp</code> — топ по отыгрышу\n"
        "• <code>/top_off</code> — топ по оффтопу\n"
        "• <code>/rp_list</code> — полный список\n"
        "• <code>/rp_me</code> — статистика игрока\n"
        "• <code>/rp_off</code> — выключить",
        parse_mode="HTML"
    )


@dp.message(Command("rp_off"))
async def cmd_rp_off(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    await disable_rp_chat(message.chat.id)
    await message.answer("🔕 Счётчик РП выключен.")


@dp.message(Command("top_rp", "топрп"))
async def cmd_top_rp(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    thread_id = get_thread_id(message)
    rows = await get_rp_top(message.chat.id, thread_id, [today_key()])
    rows = [r for r in rows if r["total_rp"] > 0]

    if not rows:
        await message.answer("📭 В этой ветке сегодня никто не играл.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>ТОП ПО ОТЫГРЫШУ (сегодня)</b>", "━━━━━━━━━━━━━", ""]
    for i, r in enumerate(rows[:15], 1):
        medal = medals.get(i, f"{i}.")
        lines.append(f"{medal} <b>{_name(r)}</b> — {r['total_rp']} симв.")

    try:
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        log.warning(f"top_rp send error: {e}")


@dp.message(Command("top_off", "топофф"))
async def cmd_top_off(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    thread_id = get_thread_id(message)
    rows = await get_rp_top(message.chat.id, thread_id, [today_key()])
    rows = [r for r in rows if r["total_off"] > 0]
    rows.sort(key=lambda r: r["total_off"], reverse=True)

    if not rows:
        await message.answer("📭 В этой ветке сегодня оффтопа не было.")
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["💬 <b>ТОП ПО ОФФТОПУ (сегодня)</b>", "━━━━━━━━━━━━━", ""]
    for i, r in enumerate(rows[:15], 1):
        medal = medals.get(i, f"{i}.")
        lines.append(f"{medal} <b>{_name(r)}</b> — {r['total_off']} симв.")

    try:
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        log.warning(f"top_off send error: {e}")


@dp.message(Command("rp_list"))
async def cmd_rp_list(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    thread_id = get_thread_id(message)
    rows = await get_rp_top(message.chat.id, thread_id, [today_key()])
    if not rows:
        await message.answer("📭 Сегодня в этой ветке ещё не было активности.")
        return

    lines = ["📋 <b>СПИСОК УЧАСТНИКОВ (эта ветка, сегодня)</b>", "━━━━━━━━━━━━━", ""]
    for i, r in enumerate(rows, 1):
        name = _name(r)
        total = r["total_rp"] + r["total_off"]
        rp = r["total_rp"]
        off = r["total_off"]
        flag = " ⚠️ <i>(только оффтоп)</i>" if rp == 0 and off > 0 else ""
        lines.append(
            f"{i}. <b>{name}</b>{flag}\n"
            f"   Всего: {total} · Отыгрыш: {rp} · Оффтоп: {off}"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n…"
    try:
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        log.warning(f"rp_list send error: {e}")


@dp.message(Command("rp_me"))
async def cmd_rp_me(message: types.Message):
    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_bot_owner(message):
        return

    target_id = message.from_user.id
    target_name = message.from_user.first_name or "Игрок"
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = message.reply_to_message.from_user.first_name or "Игрок"

    thread_id = get_thread_id(message)
    rows = await get_rp_top(message.chat.id, thread_id, [today_key()])
    my_row = next((r for r in rows if r["user_id"] == target_id), None)

    if not my_row:
        await message.answer(
            f"📭 У <b>{target_name}</b> пока нет статистики в этой ветке.",
            parse_mode="HTML"
        )
        return

    total = my_row["total_rp"] + my_row["total_off"]
    rp = my_row["total_rp"]
    off = my_row["total_off"]

    await message.answer(
        f"📊 <b>СТАТИСТИКА — {target_name}</b>\n"
        f"━━━━━━━━━━━━━\n\n"
        f"📝 Всего: <b>{total}</b> символов\n"
        f"💬 Оффтоп: <b>{off}</b> символов\n"
        f"✍️ Отыгрыш: <b>{rp}</b> символов",
        parse_mode="HTML"
    )


# ==================== СЧЁТЧИК (регистрируется ПОСЛЕДНИМ) ====================
@dp.message(F.text)
async def rp_stats_handler(message: types.Message):
    chat_id = message.chat.id
    if message.chat.type not in ("group", "supergroup"):
        return
    if not message.from_user:
        return
    if not await is_rp_chat_enabled(chat_id):
        return

    text = message.text or ""
    if not text:
        return

    # Пропускаем команды (начинаются с /, но НЕ с //)
    if text.startswith("/") and not text.startswith("//"):
        return

    rp_part, offtop_part = parse_message(text)
    rp_chars = count_chars(rp_part)
    offtop_chars = count_chars(offtop_part)

    if rp_chars == 0 and offtop_chars == 0:
        return

    thread_id = get_thread_id(message)
    try:
        await add_rp_chars(
            user_id=message.from_user.id,
            chat_id=chat_id,
            thread_id=thread_id,
            date_key=today_key(),
            rp_chars=rp_chars,
            offtop_chars=offtop_chars,
        )
    except Exception as e:
        log.exception(f"rp_stats save error: {e}")

    try:
        await remember_user_name(
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.username,
        )
    except Exception as e:
        log.warning(f"remember_user_name error: {e}")


# ==================== УТИЛИТА ====================
def _name(row) -> str:
    if row.get("username"):
        return f"@{row['username']}"
    if row.get("first_name"):
        return row["first_name"]
    return f"Игрок #{row['user_id']}"


# ==================== CLEANUP ====================
async def cleanup_rp_stats():
    from db import cleanup_old_data
    try:
        await cleanup_old_data()
        log.info("🧹 RP-статистика очищена (старше 8 дней)")
    except Exception as e:
        log.exception(f"cleanup_rp_stats error: {e}")