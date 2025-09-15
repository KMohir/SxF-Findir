import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import CommandStart
from datetime import datetime
import os
from environs import Env
import gspread
from google.oauth2.service_account import Credentials
import platform
import sqlite3
import psycopg2
from psycopg2 import sql, IntegrityError
import re

# Загрузка переменных окружения
env = Env()
env.read_env()
API_TOKEN = env.str('BOT_TOKEN')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

# Состояния
class Form(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

# Кнопки выбора Kirim/Chiqim
start_kb = InlineKeyboardMarkup(row_width=2)
start_kb.add(
    InlineKeyboardButton('🟢 Kirim', callback_data='type_kirim'),
    InlineKeyboardButton('🔴 Chiqim', callback_data='type_chiqim')
)

# Категории
categories = [
    ("Мижозлардан", "cat_mijozlar"),
    ("Аренда техника и инструменты", "cat_arenda"),
    ("Бетон тайёрлаб бериш", "cat_beton"),
    ("Геология ва лойиха ишлари", "cat_geologiya"),
    ("Геология ишлари", "cat_geologiya_ish"),
    ("Диз топливо для техники", "cat_diz"),
    ("Дорожные расходы", "cat_doroga"),
    ("Заправка", "cat_zapravka"),
    ("Коммунал и интернет", "cat_kommunal"),
    ("Кунлик ишчи", "cat_kunlik"),
    ("Объем усталар", "cat_ustalar"),
    ("Перевод", "cat_perevod"),
    ("Ойлик ишчилар", "cat_oylik"),
    ("Олиб чикиб кетилган мусор", "cat_musor"),
    ("Перечесления Расход", "cat_perechisleniya"),
    ("Питание", "cat_pitanie"),
    ("Прочие расходы", "cat_prochie"),
    ("Ремонт техники и запчасти", "cat_remont"),
    ("Сотиб олинган материал", "cat_material"),
    ("Карз", "cat_qarz"),
    ("Сотиб олинган снос уйлар", "cat_snos"),
    ("Валюта операция", "cat_valyuta"),
    ("Хизмат (Прочие расходы)", "cat_xizmat"),
    ("Хоз товары и инвентарь", "cat_xoz"),
    ("SXF Kapital", "cat_sxf"),
    ("Хожи Ака", "cat_xoji"),
    ("Эхсон", "cat_exson"),
    ("Хомийлик", "cat_xomiy")
]

# Словарь соответствий: категория -> эмодзи (теперь не используется, но оставляем для совместимости)
category_emojis = {
    "Мижозлардан": "",
    "Аренда техника и инструменты": "",
    "Бетон тайёрлаб бериш": "",
    "Геология ва лойиха ишлари": "",
    "Геология ишлари": "",
    "Диз топливо для техники": "",
    "Дорожные расходы": "",
    "Заправка": "",
    "Коммунал и интернет": "",
    "Кунлик ишчи": "",
    "Объем усталар": "",
    "Перевод": "",
    "Ойлик ишчилар": "",
    "Олиб чикиб кетилган мусор": "",
    "Перечесления Расход": "",
    "Питание": "",
    "Прочие расходы": "",
    "Ремонт техники и запчасти": "",
    "Сотиб олинган материал": "",
    "Карз": "",
    "Сотиб олинган снос уйлар": "",
    "Валюта операция": "",
    "Хизмат (Прочие расходы)": "",
    "Хоз товары и инвентарь": "",
    "SXF Kapital": "",
    "Хожи Ака": "",
    "Эхсон": "",
    "Хомийлик": ""
}

def get_category_with_emoji(category_name):
    emoji = category_emojis.get(category_name, "")
    return f"{emoji} {category_name}".strip()

def get_categories_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for name in get_categories():
        cb = f"cat_{name}"
        # Просто показываем название категории без эмодзи
        kb.add(InlineKeyboardButton(name, callback_data=cb))
    return kb

# Тип оплаты
pay_types = [
    ("Plastik", "pay_plastik"),
    ("Naxt", "pay_naxt"),
    ("Perevod", "pay_perevod"),
    ("Bank", "pay_bank")
]

def get_pay_types_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    for name in get_pay_types():
        cb = f"pay_{name}"
        kb.add(InlineKeyboardButton(name, callback_data=cb))
    return kb

# Кнопка пропуска для Izoh
skip_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="skip_comment"))

# Кнопки подтверждения
confirm_kb = InlineKeyboardMarkup(row_width=2)
confirm_kb.add(
    InlineKeyboardButton('✅ Ha', callback_data='confirm_yes'),
    InlineKeyboardButton('❌ Yoq', callback_data='confirm_no')
)

# --- Google Sheets settings ---
SHEET_ID = '10KP00nakL0LK9lyB7jQrfUtmtIQO6gzqJDP0rogTEww'
SHEET_NAME = 'Dashboard1'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = 'credentials.json'

def clean_emoji(text):
    # Удаляет только эмодзи/спецсимволы в начале строки, остальной текст не трогает
    return re.sub(r'^[^\w\s]+', '', text).strip()

def check_user_access(user_id):
    """Проверяет доступ пользователя к боту"""
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Проверяем, является ли пользователь супер-админом
        if user_id in ADMINS:
            return True, "admin"
        
        # Проверяем статус пользователя в базе
        c.execute("SELECT status FROM users WHERE user_id = %s", (user_id,))
        result = c.fetchone()
        
        if result:
            status = result[0]
            if status == 'approved':
                return True, "approved"
            else:
                return False, f"blocked ({status})"
        else:
            return False, "not_registered"
            
    except Exception as e:
        print(f"Ошибка при проверке доступа пользователя {user_id}: {e}")
        return False, "error"
    finally:
        if 'conn' in locals():
            conn.close()


def add_to_google_sheet(data):
    print("🚨🚨🚨 ФУНКЦИЯ add_to_google_sheet ВЫЗВАНА! 🚨🚨🚨")
    print(f"🚨🚨🚨 Данные: {data} 🚨🚨🚨")
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        # Jadval ustunlari: Kun, Summa, Nomi, Kirim-Chiqim, To'lov turi, Kategoriyalar, Izoh, Vaqt
        from datetime import datetime
        now = datetime.now()
        # Формат даты: 7/30/2025
        if platform.system() == 'Windows':
            date_str = now.strftime('%-m/%-d/%Y')  # Убираем ведущие нули
        else:
            date_str = now.strftime('%-m/%-d/%Y')  # Убираем ведущие нули
        time_str = now.strftime('%H:%M')
        user_name = get_user_name(data.get('user_id', data.get('user_id', '')))
        print(f"DEBUG: user_id = {data.get('user_id')}, user_name = '{user_name}'")
        debug_users_table()  # Показываем содержимое базы данных
        # Определяем, куда записать сумму в зависимости от выбранной валюты
        currency = data.get('currency', 'Sum')
        dollar_amount = ''
        sum_amount = ''
        
        if currency == 'Dollar':
            dollar_amount = data.get('amount', '')
        else:
            sum_amount = data.get('amount', '')
        
        row = [
            date_str,      # Kun (A) - дата
            time_str,      # Vaqt (B) - время
            dollar_amount,                    # $ (C) - доллары
            sum_amount,                       # Summa (D) - суммы
            clean_emoji(data.get('type', '')), # Kirim-Chiqim (E)
            data.get('pay_type', ''),         # To'lov turi (F)
            clean_emoji(data.get('category', '')), # Kotegoriyalar (G)
            '',                               # Loyihalar (H) - пусто
            data.get('comment', ''),          # Izoh (I)
            '',                               # Oylik ko'rsatkich (J) - пусто
            user_name                         # User (K) - имя пользователя
        ]
        print(f"DEBUG: Row data: {row}")
        worksheet.append_row(row)
        print(f"✅ Данные успешно записаны в Google Sheets")
        
        # Получаем остатки из первой строки
        try:
            # Читаем значения из первой строки (C1 и D1)
            dollar_balance = worksheet.acell('C1').value or '0'
            sum_balance = worksheet.acell('D1').value or '0'
            
            # Форматируем остатки
            balance_text = f"💰 <b>Остатки:</b>\n"
            balance_text += f"💵 <b>Доллары:</b> {dollar_balance}\n"
            balance_text += f"💸 <b>Суммы:</b> {sum_balance}"
            
            return balance_text
        except Exception as e:
            print(f"❌ Ошибка при получении остатков: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка при записи в Google Sheets: {e}")
        # Можно добавить логирование ошибки
        return None

def format_summary(data):
    tur_emoji = '🟢' if data.get('type') == 'Kirim' else '🔴'
    dt = data.get('dt', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # Показываем категорию без эмодзи
    category_name = data.get('category', '-')
    currency = data.get('currency', 'Sum')
    currency_symbol = '💵' if currency == 'Dollar' else '💸'
    return (
        f"<b>Natija:</b>\n"
        f"<b>Tur:</b> {tur_emoji} {data.get('type', '-')}\n"
        f"<b>Kotegoriya:</b> {category_name}\n"
        f"<b>Valyuta:</b> {currency_symbol} {currency}\n"
        f"<b>Summa:</b> {data.get('amount', '-')}\n"
        f"<b>To'lov turi:</b> {data.get('pay_type', '-')}\n"
        f"<b>Izoh:</b> {data.get('comment', '-')}\n"
        f"<b>Vaqt:</b> {dt}"
    )

# --- Админы ---
ADMINS = [5657091547, 5048593195]  # Здесь можно добавить id других админов через запятую

# --- Инициализация БД ---
def get_db_conn():
    return psycopg2.connect(
        dbname=env.str('POSTGRES_DB', 'kapital'),
        user=env.str('POSTGRES_USER', 'postgres'),
        password=env.str('POSTGRES_PASSWORD', 'postgres'),
        host=env.str('POSTGRES_HOST', 'localhost'),
        port=env.str('POSTGRES_PORT', '5432')
    )

def init_db():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE,
        name TEXT,
        phone TEXT,
        status TEXT,
        reg_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pay_types (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )''')
    # Заполняем дефолтные значения, если таблицы пусты
    c.execute('SELECT COUNT(*) FROM pay_types')
    if c.fetchone()[0] == 0:
        for name in ["Plastik", "Naxt", "Perevod", "Bank"]:
            c.execute('INSERT INTO pay_types (name) VALUES (%s)', (name,))
    c.execute('SELECT COUNT(*) FROM categories')
    if c.fetchone()[0] == 0:
        for name in ["Мижозлардан", "Аренда техника и инструменты", "Бетон тайёрлаб бериш", "Геология ва лойиха ишлари", "Геология ишлари", "Диз топливо для техники", "Дорожные расходы", "Заправка", "Коммунал и интернет", "Кунлик ишчи", "Объем усталар", "Перевод", "Ойлик ишчилар", "Олиб чикиб кетилган мусор", "Перечесления Расход", "Питание", "Прочие расходы", "Ремонт техники и запчасти", "Сотиб олинган материал", "Карз", "Сотиб олинган снос уйлар", "Валюта операция", "Хизмат (Прочие расходы)", "Хоз товары и инвентарь", "SXF Kapital", "Хожи Ака", "Эхсон", "Хомийлик"]:
            c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
    conn.commit()
    conn.close()

init_db()

# --- Проверка статуса пользователя ---
def get_user_status(user_id):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT status FROM users WHERE user_id=%s', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

# --- Регистрация пользователя ---
def register_user(user_id, name, phone):
    from datetime import datetime
    print(f"DEBUG: register_user called with user_id={user_id}, name='{name}', phone='{phone}'")
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (user_id, name, phone, status, reg_date) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO NOTHING',
                  (user_id, name, phone, 'pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        print(f"DEBUG: User registered successfully in database")
    except IntegrityError:
        print(f"DEBUG: User already exists in database")
        conn.rollback()
    except Exception as e:
        print(f"DEBUG: Error registering user: {e}")
        conn.rollback()
    conn.close()

# --- Обновление статуса пользователя ---
def update_user_status(user_id, status):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('UPDATE users SET status=%s WHERE user_id=%s', (status, user_id))
    conn.commit()
    conn.close()

# --- Проверка содержимого базы данных ---
def debug_users_table():
    print("DEBUG: Checking users table contents:")
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, name, phone, status, reg_date FROM users ORDER BY id DESC LIMIT 5')
        rows = c.fetchall()
        for row in rows:
            print(f"  User: ID={row[0]}, Name='{row[1]}', Phone='{row[2]}', Status='{row[3]}', Date='{row[4]}'")
    except Exception as e:
        print(f"DEBUG: Error reading users table: {e}")
    conn.close()

# --- Получение имени пользователя для Google Sheets ---
def get_user_name(user_id):
    print(f"DEBUG: get_user_name called with user_id = {user_id}")
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT name FROM users WHERE user_id=%s', (user_id,))
    row = c.fetchone()
    conn.close()
    result = row[0] if row else ''
    print(f"DEBUG: get_user_name result = '{result}'")
    return result

# --- Получение актуальных списков ---
def get_pay_types():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT name FROM pay_types')
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result

def get_categories():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('SELECT name FROM categories')
    result = [row[0] for row in c.fetchall()]
    conn.close()
    return result

# Удален старый обработчик /start с регистрацией

# Удалены все обработчики регистрации и ограничений доступа

# Старт
@dp.message_handler(commands=['start'])
async def start(msg: types.Message, state: FSMContext):
    await state.finish()
    
    # Проверяем доступ пользователя
    has_access, access_type = check_user_access(msg.from_user.id)
    
    if not has_access:
        if access_type == "not_registered":
            text = "❌ <b>Ruxsat yo'q!</b>\n\n"
            text += "Siz botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n"
            text += "Ro'yxatdan o'tish uchun /register ni bosing"
        elif "blocked" in access_type:
            text = "❌ <b>Akkauntiz bloklangan!</b>\n\n"
            text += "Sizning akkauntingiz admin tomonidan bloklangan.\n"
            text += "Batafsil ma'lumot uchun admin bilan bog'laning: @usernamti"
        else:
            text = "❌ <b>Xatolik!</b>\n\n"
            text += "Tizimda xatolik yuz berdi. Ro'yxatdan o'tish uchun /register ni bosing"
        
        await msg.answer(text)
        return
    
    # Создаем клавиатуру
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(types.KeyboardButton("📊 Barcha ma'lumotlar"))
    
    text = "🤖 <b>Botga xush kelibsiz!</b>\n\n"
    text += "Mavjud buyruqlar:\n"
    text += "/all - Barcha ma'lumotlarni ko'rsatish\n"
    text += "/register - Ro'yxatdan o'tish"
    
    await msg.answer(text, reply_markup=keyboard)

# Команда регистрации
@dp.message_handler(commands=['register'], state='*')
async def register_cmd(msg: types.Message, state: FSMContext):
    await state.finish()
    
    # Проверяем, не зарегистрирован ли уже пользователь
    has_access, access_type = check_user_access(msg.from_user.id)
    
    if has_access:
        await msg.answer("✅ Siz allaqachon ro'yxatdan o'tgansiz!")
        return
    
    if access_type == "not_registered":
        await msg.answer("📝 <b>Ro'yxatdan o'tish</b>\n\n"
                        "Ismingizni yuboring:")
        await Form.waiting_name.set()
    else:
        await msg.answer(f"❌ Sizning hisobingiz {access_type} holatida. Admin bilan bog'laning.")

# Обработчик имени при регистрации
@dp.message_handler(state=Form.waiting_name)
async def process_register_name(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    if len(name) < 2:
        await msg.answer("❌ Ism juda qisqa! Iltimos, to'liq ismingizni yuboring:")
        return
    
    await state.update_data(name=name)
    await msg.answer("📞 Telefon raqamingizni yuboring:\n\n"
                    "Misol: +998901234567")
    await Form.waiting_phone.set()

# Обработчик телефона при регистрации
@dp.message_handler(state=Form.waiting_phone)
async def process_register_phone(msg: types.Message, state: FSMContext):
    phone = msg.text.strip()
    
    # Простая проверка номера телефона
    if not phone.startswith('+') or len(phone) < 10:
        await msg.answer("❌ Noto'g'ri telefon raqam! Iltimos, to'g'ri formatda yuboring:\n\n"
                        "Misol: +998901234567")
        return
    
    data = await state.get_data()
    name = data.get('name')
    
    try:
        # Добавляем пользователя в базу со статусом "pending"
        conn = get_db_conn()
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO users (user_id, name, phone, status, reg_date) 
            VALUES (%s, %s, %s, 'pending', NOW())
            ON CONFLICT (user_id) DO UPDATE SET
            name = EXCLUDED.name,
            phone = EXCLUDED.phone,
            status = 'pending'
        """, (msg.from_user.id, name, phone))
        
        conn.commit()
        
        # Уведомляем админов
        await notify_admins_new_registration(msg.from_user.id, name, phone)
        
        await msg.answer("✅ <b>Ro'yxatdan o'tish muvaffaqiyatli!</b>\n\n"
                        f"👤 <b>Ism:</b> {name}\n"
                        f"📞 <b>Telefon:</b> {phone}\n\n"
                        "⏳ Admin tasdigini kutishda...\n"
                        "Tasdiqlanganidan so'ng siz botdan foydalanish mumkin bo'ladi.")
        
        await state.finish()
        
    except Exception as e:
        await msg.answer(f"❌ Xatolik yuz berdi: {e}")
        await state.finish()
    finally:
        if 'conn' in locals():
            conn.close()

# Функция уведомления админов о новой регистрации
async def notify_admins_new_registration(user_id, name, phone):
    """Уведомляет админов о новой регистрации"""
    text = "🆕 <b>Yangi ro'yxatdan o'tish!</b>\n\n"
    text += f"👤 <b>Ism:</b> {name}\n"
    text += f"📞 <b>Telefon:</b> {phone}\n"
    text += f"🆔 <b>ID:</b> {user_id}\n\n"
    text += "Tasdiqlash uchun quyidagi tugmalardan foydalaning:"
    
    # Создаем кнопки для админа
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{user_id}")
    )
    
    # Отправляем всем админам
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка отправки уведомления админу {admin_id}: {e}")

# Обработчики кнопок для админов
@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def approve_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer("Faqat admin uchun!")
        return
    
    user_id = int(call.data.split('_')[1])
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Обновляем статус пользователя на "approved"
        c.execute("UPDATE users SET status = 'approved' WHERE user_id = %s", (user_id,))
        conn.commit()
        
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id, "✅ <b>Tabriklaymiz!</b>\n\n"
                                           "Sizning hisobingiz tasdiqlandi!\n"
                                           "Endi siz botdan to'liq foydalanish mumkin.")
        except Exception as e:
            print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        await call.message.edit_text(f"✅ Foydalanuvchi tasdiqlandi: {user_id}")
        await call.answer()
        
    except Exception as e:
        await call.answer(f"Xatolik: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

@dp.callback_query_handler(lambda c: c.data.startswith('reject_'))
async def reject_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer("Faqat admin uchun!")
        return
    
    user_id = int(call.data.split('_')[1])
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Обновляем статус пользователя на "rejected"
        c.execute("UPDATE users SET status = 'rejected' WHERE user_id = %s", (user_id,))
        conn.commit()
        
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id, "❌ <b>Kechirasiz!</b>\n\n"
                                           "Sizning so'rovingiz rad etildi.\n"
                                           "Batafsil ma'lumot uchun admin bilan bog'laning.")
        except Exception as e:
            print(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        
        await call.message.edit_text(f"❌ Foydalanuvchi rad etildi: {user_id}")
        await call.answer()
        
    except Exception as e:
        await call.answer(f"Xatolik: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

# Обработчик для кнопки клавиатуры
@dp.message_handler(lambda message: message.text == "📊 Barcha ma'lumotlar", state='*')
async def keyboard_all_cmd(msg: types.Message, state: FSMContext):
    await state.finish()
    
    # Проверяем доступ пользователя
    has_access, access_type = check_user_access(msg.from_user.id)
    
    if not has_access:
        if access_type == "not_registered":
            text = "❌ <b>Ruxsat yo'q!</b>\n\n"
            text += "Siz botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n"
            text += "Ro'yxatdan o'tish uchun /register ni bosing"
        elif "blocked" in access_type:
            text = "❌ <b>Akkauntiz bloklangan!</b>\n\n"
            text += "Sizning akkauntingiz admin tomonidan bloklangan.\n"
            text += "Batafsil ma'lumot uchun admin bilan bog'laning: @usernamti"
        else:
            text = "❌ <b>Xatolik!</b>\n\n"
            text += "Tizimda xatolik yuz berdi. Ro'yxatdan o'tish uchun /register ni bosing"
        
        await msg.answer(text)
        return
    
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        
        # Получаем заголовки из 2-й строки (индекс 1)
        headers = all_values[1] if len(all_values) > 1 else []
        
        # Берем только строки начиная с 3-й (индекс 2)
        data_rows = all_values[2:] if len(all_values) > 2 else []
        
        # Фильтруем только строки с данными в первой колонке
        data_rows = [row for row in data_rows if row and row[0]]
        
        # Формируем красивое сообщение
        text = "📊 <b>SXF moliyaviy malumot</b>\n\n"
        
        # Столбцы которые нужно исключить
        excluded_headers = [
            "Som Kirim",
            "Som chiqim", 
            "Kirim $",
            "Chiqim $",
            "Bank kirim",
            "Bank chiqim"
        ]
        
        for i, row in enumerate(data_rows, 1):
            # Показываем название компании
            text += f"<b>{i}. {row[0] if row[0] else 'Не указано'}</b>\n"
            
            # Показываем все данные из строки с заголовками
            for j, cell_value in enumerate(row[1:], 1):  # начиная со 2-го столбца
                if cell_value:  # показываем только непустые ячейки
                    # Получаем заголовок для этого столбца
                    header = headers[j] if j < len(headers) else f"Столбец {j+1}"
                    
                    # Проверяем, не нужно ли исключить этот столбец
                    if header not in excluded_headers:
                        text += f"   <b>{header}:</b> {cell_value}\n"
            
            text += "\n"
        
        # Добавляем Umumiy qoldiq
        try:
            # Читаем значения из ячеек
            d1_value = worksheet.acell('D1').value or '0'
            g1_value = worksheet.acell('G1').value or '0'
            j1_value = worksheet.acell('J1').value or '0'
            m1_value = worksheet.acell('M1').value or '0'
            n1_value = worksheet.acell('N1').value or '0'
            o1_value = worksheet.acell('O1').value or '0'
            
            text += "💰 <b>Umumiy qoldiq</b>\n"
            text += f"Ostatka Som : {d1_value}\n"
            text += f"Ostatka $ : {g1_value}\n"
            text += f"Ostatka Bank : {j1_value}\n"
            text += f"Bugungi qarzdorlar : {m1_value}\n"
            text += f"Umumiy Qarzdorlar : {n1_value}\n"
            text += f"Mavjud Obektlar summasi : {o1_value}\n"
            
        except Exception as e:
            text += "❌ Umumiy qoldiq ma'lumotlarini olishda xatolik\n"

        await msg.answer(text)
        
    except FileNotFoundError:
        await msg.answer("❌ Файл credentials.json не найден. Проверьте настройки подключения.")
    except Exception as e:
        await msg.answer(f"❌ Не удалось получить данные из Google Sheets: {e}")

# Удалены все FSM обработчики для ввода данных

# --- Команды для админа ---
@dp.message_handler(commands=['add_tolov'], state='*')
async def add_paytype_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    await msg.answer('Yangi To‘lov turi nomini yuboring:')
    await state.set_state('add_paytype')

@dp.message_handler(state='add_paytype', content_types=types.ContentTypes.TEXT)
async def add_paytype_save(msg: types.Message, state: FSMContext):
    name = msg.text.strip()
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO pay_types (name) VALUES (%s)', (name,))
        conn.commit()
        await msg.answer(f'✅ Yangi To‘lov turi qo‘shildi: {name}')
    except IntegrityError:
        await msg.answer('❗️ Bu nom allaqachon mavjud.')
        conn.rollback()
    conn.close()
    await state.finish()

@dp.message_handler(commands=['add_category'], state='*')
async def add_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    await msg.answer('Yangi kategoriya nomini yuboring:')
    await state.set_state('add_category')

def split_emoji_and_text(text):
    match = re.match(r'^([^ -\w\s]+)?\s*(.*)', text)
    if match:
        emoji = match.group(1) or ''
        name = match.group(2)
        return emoji, name
    return '', text

@dp.message_handler(state='add_category', content_types=types.ContentTypes.TEXT)
async def add_category_save(msg: types.Message, state: FSMContext):
    emoji, name = split_emoji_and_text(msg.text.strip())
    conn = get_db_conn()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO categories (name, emoji) VALUES (%s, %s)', (name, emoji))
        conn.commit()
        await msg.answer(f'✅ Yangi kategoriya qo‘shildi: {emoji} {name}'.strip())
    except IntegrityError:
        await msg.answer('❗️ Bu nom allaqachon mavjud.')
        conn.rollback()
    conn.close()
    await state.finish()

# --- Удаление и изменение To'lov turi ---
@dp.message_handler(commands=['del_tolov'], state='*')
async def del_tolov_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_pay_types():
        kb.add(InlineKeyboardButton(f'❌ {name}', callback_data=f'del_tolov_{name}'))
    await msg.answer('O‘chirish uchun To‘lov turini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('del_tolov_'))
async def del_tolov_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    name = call.data[len('del_tolov_'):]
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('DELETE FROM pay_types WHERE name=%s', (name,))
    conn.commit()
    conn.close()
    await call.message.edit_text(f'❌ To‘lov turi o‘chirildi: {name}')
    await call.answer()

@dp.message_handler(commands=['edit_tolov'], state='*')
async def edit_tolov_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_pay_types():
        kb.add(InlineKeyboardButton(f'✏️ {name}', callback_data=f'edit_tolov_{name}'))
    await msg.answer('Tahrirlash uchun To‘lov turini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('edit_tolov_'))
async def edit_tolov_cb(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    old_name = call.data[len('edit_tolov_'):]
    await state.update_data(edit_tolov_old=old_name)
    await call.message.answer(f'Yangi nomini yuboring (eski: {old_name}):')
    await state.set_state('edit_tolov_new')
    await call.answer()

@dp.message_handler(state='edit_tolov_new', content_types=types.ContentTypes.TEXT)
async def edit_tolov_save(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get('edit_tolov_old')
    new_name = msg.text.strip()
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('UPDATE pay_types SET name=%s WHERE name=%s', (new_name, old_name))
    conn.commit()
    conn.close()
    await msg.answer(f'✏️ To‘lov turi o‘zgartirildi: {old_name} → {new_name}')
    await state.finish()

# --- Удаление и изменение Kotegoriyalar ---
@dp.message_handler(commands=['del_category'], state='*')
async def del_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_categories():
        kb.add(InlineKeyboardButton(f'❌ {name}', callback_data=f'del_category_{name}'))
    await msg.answer('O‘chirish uchun kategoriya tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('del_category_'))
async def del_category_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    name = call.data[len('del_category_'):]
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('DELETE FROM categories WHERE name=%s', (name,))
    conn.commit()
    conn.close()
    await call.message.edit_text(f'❌ Kategoriya o‘chirildi: {name}')
    await call.answer()

@dp.message_handler(commands=['edit_category'], state='*')
async def edit_category_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    kb = InlineKeyboardMarkup(row_width=1)
    for name in get_categories():
        kb.add(InlineKeyboardButton(f'✏️ {name}', callback_data=f'edit_category_{name}'))
    await msg.answer('Tahrirlash uchun kategoriya tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('edit_category_'))
async def edit_category_cb(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    old_name = call.data[len('edit_category_'):]
    await state.update_data(edit_category_old=old_name)
    await call.message.answer(f'Yangi nomini yuboring (eski: {old_name}):')
    await state.set_state('edit_category_new')
    await call.answer()

@dp.message_handler(state='edit_category_new', content_types=types.ContentTypes.TEXT)
async def edit_category_save(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    old_name = data.get('edit_category_old')
    new_name = msg.text.strip()
    conn = get_db_conn()
    c = conn.cursor()
    c.execute('UPDATE categories SET name=%s WHERE name=%s', (new_name, old_name))
    conn.commit()
    conn.close()
    await msg.answer(f'✏️ Kategoriya o‘zgartirildi: {old_name} → {new_name}')
    await state.finish()

@dp.message_handler(commands=['debug_db'], state='*')
async def debug_db_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Проверяем таблицу users
        c.execute("SELECT COUNT(*) FROM users")
        users_count = c.fetchone()[0]
        
        c.execute("SELECT user_id, name, phone, status, reg_date FROM users ORDER BY id DESC LIMIT 5")
        recent_users = c.fetchall()
        
        conn.close()
        
        text = f"<b>База данных:</b>\n"
        text += f"Всего пользователей: {users_count}\n\n"
        text += f"<b>Последние 5 пользователей:</b>\n"
        
        if recent_users:
            for i, (user_id, name, phone, status, reg_date) in enumerate(recent_users, 1):
                text += f"{i}. ID: {user_id}, Имя: {name}, Статус: {status}\n"
        else:
            text += "Пользователей нет\n"
            
        await msg.answer(text)
        
    except Exception as e:
        await msg.answer(f"❌ Ошибка при проверке БД: {e}")

@dp.message_handler(commands=['test_user'], state='*')
async def test_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    user_id = msg.from_user.id
    user_name = get_user_name(user_id)
    
    text = f"<b>Тест функции get_user_name:</b>\n"
    text += f"Ваш user_id: {user_id}\n"
    text += f"Результат get_user_name: '{user_name}'\n"
    
    if user_name:
        text += "✅ Имя пользователя найдено в базе"
    else:
        text += "❌ Имя пользователя НЕ найдено в базе"
    
    await msg.answer(text)

@dp.message_handler(commands=['recreate_db'], state='*')
async def recreate_db_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Удаляем старую таблицу categories
        c.execute('DROP TABLE IF EXISTS categories')
        
        # Создаем новую таблицу categories без столбца emoji
        c.execute('''CREATE TABLE categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )''')
        
        # Заполняем дефолтными значениями
        for name in ["Мижозлардан", "Аренда техника и инструменты", "Бетон тайёрлаб бериш", "Геология ва лойиха ишлари", "Геология ишлари", "Диз топливо для техники", "Дорожные расходы", "Заправка", "Коммунал и интернет", "Кунлик ишчи", "Объем усталар", "Перевод", "Ойлик ишчилар", "Олиб чикиб кетилган мусор", "Перечесления Расход", "Питание", "Прочие расходы", "Ремонт техники и запчасти", "Сотиб олинган материал", "Карз", "Сотиб олинган снос уйлар", "Валюта операция", "Хизмат (Прочие расходы)", "Хоз товары и инвентарь", "SXF Kapital", "Хожи Ака", "Эхсон", "Хомийлик"]:
            c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
        
        conn.commit()
        conn.close()
        
        await msg.answer('✅ База данных пересоздана! Таблица categories обновлена.')
        
    except Exception as e:
        await msg.answer(f'❌ Ошибка при пересоздании БД: {e}')

@dp.message_handler(commands=['sync_categories'], state='*')
async def sync_categories_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        # Очищаем таблицу categories
        c.execute('DELETE FROM categories')
        
        # Добавляем актуальные категории
        categories = [
            "Мижозлардан",
            "Аренда техника и инструменты",
            "Бетон тайёрлаб бериш",
            "Геология ва лойиха ишлари",
            "Геология ишлари",
            "Диз топливо для техники",
            "Дорожные расходы",
            "Заправка",
            "Коммунал и интернет",
            "Кунлик ишчи",
            "Объем усталар",
            "Перевод",
            "Ойлик ишчилар",
            "Олиб чикиб кетилган мусор",
            "Перечесления Расход",
            "Питание",
            "Прочие расходы",
            "Ремонт техники и запчасти",
            "Сотиб олинган материал",
            "Карз",
            "Сотиб олинган снос уйлар",
            "Валюта операция",
            "Хизмат (Прочие расходы)",
            "Хоз товары и инвентарь",
            "SXF Kapital",
            "Хожи Ака",
            "Эхсон",
            "Хомийлик"
        ]
        
        for name in categories:
            c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
        
        conn.commit()
        conn.close()
        
        await msg.answer('✅ Категории синхронизированы!')
        
    except Exception as e:
        await msg.answer(f'❌ Ошибка при синхронизации: {e}')

@dp.message_handler(commands=['show_categories'], state='*')
async def show_categories_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    try:
        conn = get_db_conn()
        c = conn.cursor()
        
        c.execute('SELECT name FROM categories ORDER BY id')
        categories = c.fetchall()
        conn.close()
        
        if categories:
            text = '<b>Текущие категории в базе данных:</b>\n\n'
            for i, (name,) in enumerate(categories, 1):
                text += f"{i}. {name}\n"
        else:
            text = '❌ Категории не найдены в базе данных'
        
        await msg.answer(text)
        
    except Exception as e:
        await msg.answer(f'❌ Ошибка при получении категорий: {e}')

@dp.message_handler(commands=['load_categories_from_file'], state='*')
async def load_categories_from_file_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()
    
    try:
        # Читаем категории из файла
        with open('categories.txt', 'r', encoding='utf-8') as f:
            categories = [line.strip() for line in f if line.strip()]
        
        conn = get_db_conn()
        c = conn.cursor()
        
        # Очищаем таблицу categories
        c.execute('DELETE FROM categories')
        
        # Добавляем категории из файла
        for name in categories:
            c.execute('INSERT INTO categories (name) VALUES (%s)', (name,))
        
        conn.commit()
        conn.close()
        
        await msg.answer(f'✅ Загружено {len(categories)} категорий из файла categories.txt')
        
    except FileNotFoundError:
        await msg.answer('❌ Файл categories.txt не найден')
    except Exception as e:
        await msg.answer(f'❌ Ошибка при загрузке категорий: {e}')


@dp.message_handler(commands=['all'], state='*')
async def all_cmd(msg: types.Message, state: FSMContext):
    await state.finish()
    
    # Проверяем доступ пользователя
    has_access, access_type = check_user_access(msg.from_user.id)
    
    if not has_access:
        if access_type == "not_registered":
            text = "❌ <b>Ruxsat yo'q!</b>\n\n"
            text += "Siz botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n"
            text += "Ro'yxatdan o'tish uchun /register ni bosing"
        elif "blocked" in access_type:
            text = "❌ <b>Akkauntiz bloklangan!</b>\n\n"
            text += "Sizning akkauntingiz admin tomonidan bloklangan.\n"
            text += "Batafsil ma'lumot uchun admin bilan bog'laning: @usernamti"
        else:
            text = "❌ <b>Xatolik!</b>\n\n"
            text += "Tizimda xatolik yuz berdi. Ro'yxatdan o'tish uchun /register ni bosing"
        
        await msg.answer(text)
        return
    
    try:
        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        worksheet = sh.worksheet(SHEET_NAME)
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        
        # Получаем заголовки из 2-й строки (индекс 1)
        headers = all_values[1] if len(all_values) > 1 else []
        
        # Берем только строки начиная с 3-й (индекс 2)
        data_rows = all_values[2:] if len(all_values) > 2 else []
        
        # Фильтруем только строки с данными в первой колонке
        data_rows = [row for row in data_rows if row and row[0]]
        
        # Формируем красивое сообщение
        text = "📊 <b>SXF moliyaviy malumot</b>\n\n"
        
        # Столбцы которые нужно исключить
        excluded_headers = [
            "Som Kirim",
            "Som chiqim", 
            "Kirim $",
            "Chiqim $",
            "Bank kirim",
            "Bank chiqim"
        ]
        
        for i, row in enumerate(data_rows, 1):
            # Показываем название компании
            text += f"<b>{i}. {row[0] if row[0] else 'Не указано'}</b>\n"
            
            # Показываем все данные из строки с заголовками
            for j, cell_value in enumerate(row[1:], 1):  # начиная со 2-го столбца
                if cell_value:  # показываем только непустые ячейки
                    # Получаем заголовок для этого столбца
                    header = headers[j] if j < len(headers) else f"Столбец {j+1}"
                    
                    # Проверяем, не нужно ли исключить этот столбец
                    if header not in excluded_headers:
                        text += f"   <b>{header}:</b> {cell_value}\n"
            
            text += "\n"
        
        # Добавляем Umumiy qoldiq
        try:
            # Читаем значения из ячеек
            d1_value = worksheet.acell('D1').value or '0'
            g1_value = worksheet.acell('G1').value or '0'
            j1_value = worksheet.acell('J1').value or '0'
            m1_value = worksheet.acell('M1').value or '0'
            n1_value = worksheet.acell('N1').value or '0'
            o1_value = worksheet.acell('O1').value or '0'
            
            text += "💰 <b>Umumiy qoldiq</b>\n"
            text += f"Ostatka Som : {d1_value}\n"
            text += f"Ostatka $ : {g1_value}\n"
            text += f"Ostatka Bank : {j1_value}\n"
            text += f"Bugungi qarzdorlar : {m1_value}\n"
            text += f"Umumiy Qarzdorlar : {n1_value}\n"
            text += f"Mavjud Obektlar summasi : {o1_value}\n"
            
        except Exception as e:
            text += "❌ Umumiy qoldiq ma'lumotlarini olishda xatolik\n"
        
        await msg.answer(text)
        
    except FileNotFoundError:
        await msg.answer("❌ Файл credentials.json не найден. Проверьте настройки подключения.")
    except Exception as e:
        await msg.answer(f"❌ Не удалось получить данные из Google Sheets: {e}")


@dp.message_handler(commands=['reboot'], state='*')
async def reboot_cmd(msg: types.Message, state: FSMContext):
    await state.finish()  # Останавливаем FSM состояние
    
    # Проверяем доступ пользователя
    has_access, access_type = check_user_access(msg.from_user.id)
    
    if not has_access:
        if access_type == "not_registered":
            text = "❌ <b>Ruxsat yo'q!</b>\n\n"
            text += "Siz botdan foydalanish uchun ro'yxatdan o'tishingiz kerak.\n"
            text += "Ro'yxatdan o'tish uchun /register ni bosing"
        elif "blocked" in access_type:
            text = "❌ <b>Akkauntiz bloklangan!</b>\n\n"
            text += "Sizning akkauntingiz admin tomonidan bloklangan.\n"
            text += "Batafsil ma'lumot uchun admin bilan bog'laning: @usernamti"
        else:
            text = "❌ <b>Xatolik!</b>\n\n"
            text += "Tizimda xatolik yuz berdi. Ro'yxatdan o'tish uchun /register ni bosing"
        
        await msg.answer(text)
        return
    
    # Создаем клавиатуру
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    keyboard.add(types.KeyboardButton("📊 Barcha ma'lumotlar"))
    
    text = "🔄 <b>Bot qayta ishga tushirildi!</b>\n\n"
    text += "Mavjud buyruqlar:\n"
    text += "/all - Barcha ma'lumotlarni ko'rsatish\n"
    text += "/start - Asosiy menyu"
    await msg.answer(text, reply_markup=keyboard)

# Команда для регистрации новых пользователей (только для админов)
@dp.message_handler(commands=['add_user'], state='*')
async def add_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    
    # Парсим команду: /add_user user_id name phone
    try:
        parts = msg.text.split(' ', 3)
        if len(parts) < 4:
            await msg.answer('❌ Noto\'g\'ri format!\n\n'
                           'Foydalanish: /add_user <user_id> <name> <phone>\n'
                           'Misol: /add_user 123456789 "John Doe" "+998901234567"')
            return
        
        user_id = int(parts[1])
        name = parts[2]
        phone = parts[3]
        
        # Добавляем пользователя в базу
        conn = get_db_conn()
        c = conn.cursor()
        
        # Проверяем, существует ли пользователь
        c.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
        if c.fetchone():
            await msg.answer(f'❌ Foydalanuvchi {user_id} allaqachon mavjud!')
            return
        
        # Добавляем нового пользователя
        c.execute("""
            INSERT INTO users (user_id, name, phone, status, reg_date) 
            VALUES (%s, %s, %s, 'approved', NOW())
        """, (user_id, name, phone))
        
        conn.commit()
        await msg.answer(f'✅ Foydalanuvchi muvaffaqiyatli qo\'shildi!\n\n'
                        f'ID: {user_id}\n'
                        f'Ism: {name}\n'
                        f'Telefon: {phone}\n'
                        f'Status: approved')
        
    except ValueError:
        await msg.answer('❌ User ID raqam bo\'lishi kerak!')
    except Exception as e:
        await msg.answer(f'❌ Xatolik: {e}')
    finally:
        if 'conn' in locals():
            conn.close()

# Команда для просмотра заявок на регистрацию
@dp.message_handler(commands=['pending_users'], state='*')
async def pending_users_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    
    await state.finish()
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name, phone, reg_date FROM users WHERE status='pending' ORDER BY reg_date DESC")
    rows = c.fetchall()
    
    if not rows:
        await msg.answer('⏳ Hali birorta ham kutilayotgan so\'rov yo\'q.')
        return
    
    text = '<b>⏳ Kutilayotgan so\'rovlar:</b>\n\n'
    for i, (user_id, name, phone, reg_date) in enumerate(rows, 1):
        text += f"{i}. <b>{name}</b>\n"
        text += f"   ID: <code>{user_id}</code>\n"
        text += f"   Telefon: <code>{phone}</code>\n"
        text += f"   Sana: {reg_date}\n\n"
    
    await msg.answer(text)

@dp.message_handler(commands=['userslist'], state='*')
async def users_list_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name, phone, reg_date FROM users WHERE status='approved'")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await msg.answer('Hali birorta ham tasdiqlangan foydalanuvchi yo‘q.')
        return
    text = '<b>Tasdiqlangan foydalanuvchilar:</b>\n'
    for i, (user_id, name, phone, reg_date) in enumerate(rows, 1):
        text += f"\n{i}. <b>{name}</b>\nID: <code>{user_id}</code>\nTelefon: <code>{phone}</code>\nRo‘yxatdan o‘tgan: {reg_date}\n"
    await msg.answer(text)

@dp.message_handler(commands=['block_user'], state='*')
async def block_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name FROM users WHERE status='approved'")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await msg.answer('Hali birorta ham tasdiqlangan foydalanuvchi yo‘q.')
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for user_id, name in rows:
        kb.add(InlineKeyboardButton(f'🚫 {name} ({user_id})', callback_data=f'blockuser_{user_id}'))
    await msg.answer('Bloklash uchun foydalanuvchini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('blockuser_'))
async def block_user_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    user_id = int(call.data[len('blockuser_'):])
    update_user_status(user_id, 'denied')
    try:
        await bot.send_message(user_id, '❌ Sizga botdan foydalanishga ruxsat berilmagan. (Admin tomonidan bloklandi)')
    except Exception:
        pass
    await call.message.edit_text(f'🚫 Foydalanuvchi bloklandi: {user_id}')
    await call.answer()

@dp.message_handler(commands=['approve_user'], state='*')
async def approve_user_cmd(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMINS:
        await msg.answer('Faqat admin uchun!')
        return
    await state.finish()  # Сброс состояния
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id, name FROM users WHERE status='denied'")
    rows = c.fetchall()
    conn.close()
    if not rows:
        await msg.answer('Hali birorta ham bloklangan foydalanuvchi yo‘q.')
        return
    kb = InlineKeyboardMarkup(row_width=1)
    for user_id, name in rows:
        kb.add(InlineKeyboardButton(f'✅ {name} ({user_id})', callback_data=f'approveuser_{user_id}'))
    await msg.answer('Qayta tasdiqlash uchun foydalanuvchini tanlang:', reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('approveuser_'))
async def approve_user_cb(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        await call.answer('Faqat admin uchun!', show_alert=True)
        return
    user_id = int(call.data[len('approveuser_'):])
    update_user_status(user_id, 'approved')
    try:
        await bot.send_message(user_id, '✅ Sizga botdan foydalanishga yana ruxsat berildi! /start')
    except Exception:
        pass
    await call.message.edit_text(f'✅ Foydalanuvchi qayta tasdiqlandi: {user_id}')
    await call.answer()

async def set_user_commands(dp):
    commands = [
        types.BotCommand("start", "Botni boshlash"),
        types.BotCommand("register", "Ro'yxatdan o'tish"),
        types.BotCommand("reboot", "Qayta boshlash - FSM ni to'xtatish"),
        types.BotCommand("all", "Barcha ma'lumotlarni ko'rsatish"),
    ]
    await dp.bot.set_my_commands(commands)

async def notify_all_users(bot):
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE status='approved'")
    rows = c.fetchall()
    conn.close()
    for (user_id,) in rows:
        try:
            await bot.send_message(user_id, "Iltimos, /start ni bosing va botdan foydalanishni davom eting!")
        except Exception:
            pass  # Пользователь мог заблокировать бота или быть недоступен

if __name__ == '__main__':
    from aiogram import executor
    async def on_startup(dp):
        await set_user_commands(dp)
        await notify_all_users(dp.bot)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup) 
