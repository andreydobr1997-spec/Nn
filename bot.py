import asyncio
import logging
import os
import sqlite3
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
STARS_PER_INVITE = int(os.getenv("STARS_PER_INVITE", "5"))  # сколько звёзд давать за приглашённого

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ---------- БАЗА ДАННЫХ ----------

def db_connect():
    conn = sqlite3.connect("bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db_connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            ref_by INTEGER,
            stars INTEGER DEFAULT 0,
            invited_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = db_connect()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row

def create_user(user_id: int, username: str, ref_by: int | None):
    conn = db_connect()
    conn.execute(
        "INSERT INTO users (user_id, username, ref_by) VALUES (?, ?, ?)",
        (user_id, username, ref_by),
    )
    conn.commit()
    conn.close()

def add_stars(user_id: int, amount: int):
    conn = db_connect()
    conn.execute(
        "UPDATE users SET stars = stars + ?, invited_count = invited_count + 1 WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()

# ---------- ХЕНДЛЕРЫ ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.full_name

    existing = get_user(user_id)

    if existing is None:
        ref_by = None
        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].startswith("ref"):
            try:
                ref_by_candidate = int(args[1].replace("ref", ""))
                # нельзя реферить самого себя, и реферер должен существовать
                if ref_by_candidate != user_id and get_user(ref_by_candidate):
                    ref_by = ref_by_candidate
            except ValueError:
                pass

        create_user(user_id, username, ref_by)

        if ref_by:
            add_stars(ref_by, STARS_PER_INVITE)
            try:
                await bot.send_message(
                    ref_by,
                    f"🎉 По твоей ссылке зашёл новый человек!\n"
                    f"Начислено: <b>{STARS_PER_INVITE}⭐</b>"
                )
            except Exception:
                pass  # если у реферера закрыты личные сообщения от бота

    await message.answer(
        "👋 Привет! Это бот с реферальной системой.\n\n"
        "Приглашай друзей и получай звёзды за каждого!\n\n"
        "Команды:\n"
        "/invite — получить свою реферальную ссылку\n"
        "/balance — посмотреть баланс и статистику"
    )

@dp.message(Command("invite"))
async def cmd_invite(message: Message):
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref{user_id}"
    await message.answer(
        f"🔗 Твоя реферальная ссылка:\n{link}\n\n"
        f"За каждого приглашённого — {STARS_PER_INVITE}⭐"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    user = get_user(message.from_user.id)
    if user is None:
        await message.answer("Сначала нажми /start")
        return
    await message.answer(
        f"⭐ Баланс: {user['stars']}\n"
        f"👥 Приглашено: {user['invited_count']}"
    )

# ---------- ЗАПУСК ----------

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
