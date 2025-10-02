import os
import asyncio
import aiomysql
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

BOT_TOKEN = os.getenv("6382553225:AAEnjV2KPiPaCR-7aLSPf40kKSk720IvFB0")

DB_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "port": int(os.getenv("MYSQLPORT", 3306)),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "db": os.getenv("MYSQLDATABASE"),
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Almaty")  # твой часовой пояс

# Кнопка подтверждения
def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Спасибо, Шер. Я выпила лекарство. 🥰", callback_data="confirm_taken")]
    ])

# Подключение к БД
async def get_conn():
    return await aiomysql.connect(**DB_CONFIG)

# Создание таблицы
async def init_db():
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            time VARCHAR(10),
            confirmed BOOLEAN DEFAULT FALSE
        )
        """)
    await conn.commit()
    conn.close()

# /start
@dp.message(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer("Улжака, Привет! Я помогу тебе не забывать пить лекарства 💊\n\n"
                         "Напиши время в формате `HH:MM` (например: 09:00), "
                         "и я буду напоминать тебе каждый день в это время.")

# Добавление времени
@dp.message(F.text.regexp(r"^\d{2}:\d{2}$"))
async def add_time(message: types.Message):
    time_str = message.text.strip()
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("INSERT INTO reminders (user_id, time) VALUES (%s, %s)", (message.from_user.id, time_str))
    await conn.commit()
    conn.close()

    # Планируем ежедневное напоминание
    hour, minute = map(int, time_str.split(":"))
    scheduler.add_job(send_reminder, CronTrigger(hour=hour, minute=minute), args=[message.from_user.id, 1])

    await message.answer(f"✅ Отлично! Теперь я буду напоминать тебе каждый день в {time_str}")

# Отправка напоминания
async def send_reminder(user_id: int, attempt: int = 1):
    try:
        await bot.send_message(user_id, f"💊 Напоминание #{attempt}: пора выпить лекарство!",
                               reply_markup=confirm_keyboard())

        # Если не подтвердил — планируем повтор через 30 минут
        if attempt < 5:
            run_time = datetime.now() + timedelta(minutes=30)
            scheduler.add_job(send_reminder, "date", run_date=run_time, args=[user_id, attempt + 1])

    except Exception as e:
        print(f"Ошибка при отправке: {e}")

# Подтверждение
@dp.callback_query(F.data == "confirm_taken")
async def confirm_taken(callback: types.CallbackQuery):
    conn = await get_conn()
    async with conn.cursor() as cur:
        await cur.execute("UPDATE reminders SET confirmed = TRUE WHERE user_id = %s", (callback.from_user.id,))
    await conn.commit()
    conn.close()

    await callback.message.edit_text("✅ Умничка! Ты выпил лекарство. Твоя кожа станет лучше. Потерпи, осталось совсем немного.")

    # Удаляем будущие напоминания для этого пользователя
    jobs = scheduler.get_jobs()
    for job in jobs:
        if job.args and job.args[0] == callback.from_user.id:
            job.remove()

async def main():
    await init_db()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
