import random
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import json
import re
import os
import re

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables.")
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# Хранилище временных данных
user_temp_data = {}


# Инициализация БД
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                    (chat_id INTEGER PRIMARY KEY, 
                     username TEXT,
                     reminder_time TEXT DEFAULT '14:00',
                     streak INTEGER DEFAULT 0,
                     last_active TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS stats
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     chat_id INTEGER,
                     date TEXT,
                     mental_tasks INTEGER DEFAULT 0,
                     physical_tasks INTEGER DEFAULT 0,
                     FOREIGN KEY(chat_id) REFERENCES users(chat_id))''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS achievements
                    (chat_id INTEGER,
                     badge_name TEXT,
                     progress INTEGER,
                     FOREIGN KEY(chat_id) REFERENCES users(chat_id))''')

    conn.commit()
    conn.close()


# Загрузка заданий
def load_tasks():
    default_tasks = {
        "mental": ["Прочитай 10 страниц", "Выучи 5 новых слов"],
        "physical": ["10 отжиманий", "1 минута планки", "15 минут упражнений с гантелями"]
    }

    if not os.path.exists('tasks.json'):
        return default_tasks

    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_tasks


tasks = load_tasks()


# Клавиатуры
def get_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Начать работу 🚀")],
            [KeyboardButton(text="Моя статистика 📊"), KeyboardButton(text="Мои достижения 🏆")],
            [KeyboardButton(text="Настроить время ⏰")]
        ],
        resize_keyboard=True
    )


def get_tasks_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Все задания"), KeyboardButton(text="Только умственные 🧠")],
            [KeyboardButton(text="Только физические 💪"), KeyboardButton(text="Назад ↩️")]
        ],
        resize_keyboard=True
    )


def get_actions_kb(has_timer=False):
    if has_timer:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Включить таймер ⏱️")],
                [KeyboardButton(text="Выполнил! ✅"), KeyboardButton(text="Пропустить ❌")],
                [KeyboardButton(text="Назад ↩️")]
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Выполнил! ✅"), KeyboardButton(text="Пропустить ❌")],
                [KeyboardButton(text="Назад ↩️")]
            ],
            resize_keyboard=True
        )


# Извлечение времени из задания
def extract_minutes(task_text):
    match = re.search(r'(\d+)\s*минут', task_text)
    if match:
        return int(match.group(1))
    match = re.search(r'(\d+)\s*мин', task_text)
    if match:
        return int(match.group(1))
    return None


# Таймер
async def run_timer(chat_id, minutes):
    total_seconds = minutes * 60
    message = await bot.send_message(chat_id, f"⏳ Таймер запущен на {minutes} минут...")

    for remaining in range(total_seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        timer_text = f"⏱️ Осталось: {mins:02d}:{secs:02d}"
        try:
            await bot.edit_message_text(
                timer_text,
                chat_id=chat_id,
                message_id=message.message_id
            )
        except:
            pass
        await asyncio.sleep(1)

    await bot.send_message(chat_id, "🔔 Время вышло! Задание завершено!")


# Настройка напоминаний
async def setup_reminders():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''SELECT chat_id, reminder_time FROM users''')
        for chat_id, reminder_time in cursor.fetchall():
            if reminder_time:
                hours, minutes = map(int, reminder_time.split(':'))
                scheduler.add_job(
                    send_reminder,
                    'cron',
                    hour=hours,
                    minute=minutes,
                    args=[chat_id]
                )
    finally:
        conn.close()


# Отправка напоминания
async def send_reminder(chat_id):
    await bot.send_message(
        chat_id,
        "⏰ Время работать над собой! Нажми 'Начать работу 🚀'",
        reply_markup=get_main_kb()
    )


# Команда /start и кнопка "Начать работу"
@dp.message(Command("start"))
@dp.message(F.text == "Начать работу 🚀")
async def start(message: types.Message):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR IGNORE INTO users (chat_id, username) VALUES (?, ?)''',
                   (message.chat.id, message.from_user.username))
    conn.commit()
    conn.close()

    await message.answer(
        "🏆 Добро пожаловать в мотивационного бота!\n"
        "Выбери тип заданий:",
        reply_markup=get_tasks_kb()
    )


# Показ статистики
@dp.message(F.text == "Моя статистика 📊")
async def show_stats(message: types.Message):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''SELECT SUM(mental_tasks), SUM(physical_tasks) FROM stats 
                        WHERE chat_id = ?''', (message.chat.id,))
        mental, physical = cursor.fetchone() or (0, 0)

        cursor.execute('''SELECT streak FROM users WHERE chat_id = ?''', (message.chat.id,))
        streak_row = cursor.fetchone()
        streak = streak_row[0] if streak_row else 0

        response = (
            f"📊 Твоя статистика:\n\n"
            f"Умственные задания: {mental} выполнено\n"
            f"Физуха: {physical} раз\n"
            f"Дней подряд: {streak}"
        )

        await message.answer(response, reply_markup=get_main_kb())
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        conn.close()


# Показ достижений
@dp.message(F.text == "Мои достижения 🏆")
async def show_achievements(message: types.Message):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''SELECT badge_name FROM achievements 
                        WHERE chat_id = ?''', (message.chat.id,))
        badges = [row[0] for row in cursor.fetchall()]

        if badges:
            response = "Твои достижения:\n" + "\n".join(badges)
        else:
            response = "Пока ничего, работай дальше"

        await message.answer(response, reply_markup=get_main_kb())
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        conn.close()


# Выбор заданий
@dp.message(F.text.in_(["Все задания", "Только умственные 🧠", "Только физические 💪"]))
async def send_tasks(message: types.Message):
    mental = random.choice(tasks["mental"])
    physical = random.choice(tasks["physical"])

    if message.text == "Все задания":
        response = f"🧠 Умственное задание:\n{mental}\n\n💪 Физическое задание:\n{physical}"
        user_temp_data[message.chat.id] = {
            "type": "both",
            "physical_task": physical
        }
        has_timer = extract_minutes(physical) is not None
    elif message.text == "Только умственные 🧠":
        response = f"🧠 Умственное задание:\n{mental}"
        user_temp_data[message.chat.id] = {"type": "mental"}
        has_timer = False
    else:
        response = f"💪 Физическое задание:\n{physical}"
        user_temp_data[message.chat.id] = {
            "type": "physical",
            "physical_task": physical
        }
        has_timer = extract_minutes(physical) is not None

    await message.answer(response, reply_markup=get_actions_kb(has_timer=has_timer))


# Включение таймера
@dp.message(F.text == "Включить таймер ⏱️")
async def start_timer(message: types.Message):
    user_data = user_temp_data.get(message.chat.id, {})
    if "physical_task" in user_data:
        minutes = extract_minutes(user_data["physical_task"])
        if minutes:
            await message.answer(f"Таймер запущен на {minutes} минут!")
            await run_timer(message.chat.id, minutes)
        else:
            await message.answer("Для этого задания таймер не предусмотрен")
    else:
        await message.answer("Сначала получите задание")


# Обработка выполнения задания
@dp.message(F.text == "Выполнил! ✅")
async def task_completed(message: types.Message):
    task_type = user_temp_data.get(message.chat.id, {}).get("type", "both")
    today = datetime.now().strftime("%Y-%m-%d")

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    try:
        # Обновляем статистику
        cursor.execute('''INSERT OR IGNORE INTO stats (chat_id, date) VALUES (?, ?)''',
                       (message.chat.id, today))

        if task_type in ["both", "mental"]:
            cursor.execute('''UPDATE stats SET mental_tasks = mental_tasks + 1 
                           WHERE chat_id = ? AND date = ?''',
                           (message.chat.id, today))

        if task_type in ["both", "physical"]:
            cursor.execute('''UPDATE stats SET physical_tasks = physical_tasks + 1 
                           WHERE chat_id = ? AND date = ?''',
                           (message.chat.id, today))

        # Получаем последнюю активность
        cursor.execute('''SELECT last_active FROM users WHERE chat_id = ?''',
                       (message.chat.id,))
        last_active_row = cursor.fetchone()
        last_active = last_active_row[0] if last_active_row else None

        # Обновляем серию
        if last_active != today:
            cursor.execute('''UPDATE users 
                            SET streak = CASE WHEN last_active = date(?, '-1 day') THEN streak + 1 ELSE 1 END,
                                last_active = ?
                            WHERE chat_id = ?''',
                           (today, today, message.chat.id))

        conn.commit()
        await message.answer("✅ Задание засчитано! Так держать!", reply_markup=get_main_kb())
    except Exception as e:
        await message.answer(f"⚠ Ошибка: {e}")
    finally:
        conn.close()


# Настройка времени напоминаний
@dp.message(F.text == "Настроить время ⏰")
async def set_reminder_time(message: types.Message):
    await message.answer(
        "⏰ Введи время напоминаний в формате ЧЧ:MM (например, 09:30):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    user_temp_data[f"waiting_time_{message.chat.id}"] = True


@dp.message(F.text.regexp(r'^\d{2}:\d{2}$'))
async def process_time_input(message: types.Message):
    if user_temp_data.get(f"waiting_time_{message.chat.id}"):
        try:
            time_str = message.text
            hours, minutes = map(int, time_str.split(':'))

            if 0 <= hours < 24 and 0 <= minutes < 60:
                conn = sqlite3.connect('users.db')
                cursor = conn.cursor()
                cursor.execute('''UPDATE users SET reminder_time = ? WHERE chat_id = ?''',
                               (time_str, message.chat.id))
                conn.commit()
                conn.close()

                await message.answer(
                    f"⏰ Напоминания установлены на {time_str}",
                    reply_markup=get_main_kb()
                )
                user_temp_data.pop(f"waiting_time_{message.chat.id}")

                # Перезагружаем расписание
                scheduler.remove_all_jobs()
                await setup_reminders()
            else:
                await message.answer("Некорректное время. Используй формат ЧЧ:MM")
        except Exception as e:
            await message.answer(f"Ошибка: {e}")


# Кнопка "Назад"
@dp.message(F.text == "Назад ↩️")
async def back_to_main(message: types.Message):
    await message.answer("Главное меню:", reply_markup=get_main_kb())


# Пропуск задания
@dp.message(F.text == "Пропустить ❌")
async def skip_task(message: types.Message):
    await message.answer("Задание пропущено. Может быть, в следующий раз!", reply_markup=get_main_kb())


# Запуск бота
async def on_startup():
    init_db()
    await setup_reminders()
    scheduler.start()


async def main():
    await on_startup()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())