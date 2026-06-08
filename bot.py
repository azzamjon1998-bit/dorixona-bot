import asyncio
import os
import psycopg2
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class RegisterState(StatesGroup):
    waiting_for_name = State()

class BronState(StatesGroup):
    waiting_for_dori = State()

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (telegram_id BIGINT PRIMARY KEY, ism TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bronlar (id SERIAL PRIMARY KEY, telegram_id BIGINT, dori_nomi TEXT NOT NULL, sana TIMESTAMP DEFAULT NOW())""")
    conn.commit()
    conn.close()

def get_user(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT ism FROM users WHERE telegram_id = %s", (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def save_user(telegram_id, ism):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO users (telegram_id, ism) VALUES (%s, %s) ON CONFLICT (telegram_id) DO UPDATE SET ism = %s", (telegram_id, ism, ism))
    conn.commit()
    conn.close()

def add_bron(telegram_id, dori_nomi):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO bronlar (telegram_id, dori_nomi) VALUES (%s, %s)", (telegram_id, dori_nomi))
    conn.commit()
    conn.close()

def get_bronlar(telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, dori_nomi, sana FROM bronlar WHERE telegram_id = %s", (telegram_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def delete_bron(bron_id, telegram_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM bronlar WHERE id = %s AND telegram_id = %s", (bron_id, telegram_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT telegram_id, ism FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💊 Dori bron qilish", callback_data="bron_qilish")],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="mening_bronlarim")],
        [InlineKeyboardButton(text="❌ Bronni o'chirish", callback_data="bron_ochirish")],
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💊 Dori bron qilish", callback_data="bron_qilish")],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="mening_bronlarim")],
        [InlineKeyboardButton(text="❌ Bronni o'chirish", callback_data="bron_ochirish")],
        [InlineKeyboardButton(text="👥 Hamkasblar bronlari", callback_data="admin_panel")],
    ])

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    ism = get_user(message.from_user.id)
    if ism:
        menu = admin_menu() if message.from_user.id == ADMIN_ID else main_menu()
        await message.answer(f"👋 Xush kelibsiz, <b>{ism}</b>!", reply_markup=menu, parse_mode="HTML")
    else:
        await message.answer("👋 Salom! <b>Ismingizni</b> kiriting:", parse_mode="HTML")
        await state.set_state(RegisterState.waiting_for_name)

@dp.message(RegisterState.waiting_for_name)
async def save_name(message: Message, state: FSMContext):
    ism = message.text.strip()
    if len(ism) < 2:
        await message.answer("❗ Ism juda qisqa. Qayta kiriting:")
        return
    save_user(message.from_user.id, ism)
    await state.clear()
    menu = admin_menu() if message.from_user.id == ADMIN_ID else main_menu()
    await message.answer(f"✅ Ro'yxatdan o'tdingiz, <b>{ism}</b>!", reply_markup=menu, parse_mode="HTML")

@dp.callback_query(F.data == "bron_qilish")
async def bron_qilish(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("💊 <b>Dori nomini</b> yozing:", parse_mode="HTML")
    await state.set_state(BronState.waiting_for_dori)
    await callback.answer()

@dp.message(BronState.waiting_for_dori)
async def save_bron(message: Message, state: FSMContext):
    dori = message.text.strip()
    if len(dori) < 2:
        await message.answer("❗ Dori nomi qisqa. Qayta kiriting:")
        return
    add_bron(message.from_user.id, dori)
    await state.clear()
    menu = admin_menu() if message.from_user.id == ADMIN_ID else main_menu()
    await message.answer(f"✅ <b>{dori}</b> bron qilindi!", reply_markup=menu, parse_mode="HTML")

@dp.callback_query(F.data == "mening_bronlarim")
async def mening_bronlarim(callback: CallbackQuery):
    bronlar = get_bronlar(callback.from_user.id)
    menu = admin_menu() if callback.from_user.id == ADMIN_ID else main_menu()
    if not bronlar:
        await callback.message.answer("📋 Sizda hozircha bron yo'q.", reply_markup=menu)
    else:
        text = "📋 <b>Sizning bronlaringiz:</b>\n\n"
        for i, (bid, dori, sana) in enumerate(bronlar, 1):
            text += f"{i}. 💊 <b>{dori}</b>\n   📅 {sana}\n\n"
        await callback.message.answer(text, reply_markup=menu, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "bron_ochirish")
async def bron_ochirish(callback: CallbackQuery):
    bronlar = get_bronlar(callback.from_user.id)
    menu = admin_menu() if callback.from_user.id == ADMIN_ID else main_menu()
    if not bronlar:
        await callback.message.answer("❗ O'chirish uchun broningiz yo'q.", reply_markup=menu)
        await callback.answer()
        return
    buttons = [[InlineKeyboardButton(text=f"❌ {dori}", callback_data=f"del_{bid}")] for bid, dori, sana in bronlar]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="orqaga")])
    await callback.message.answer("Qaysi bronni o'chirmoqchisiz?", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_"))
async def confirm_delete(callback: CallbackQuery):
    bron_id = int(callback.data.split("_")[1])
    delete_bron(bron_id, callback.from_user.id)
    menu = admin_menu() if callback.from_user.id == ADMIN_ID else main_menu()
    await callback.message.answer("✅ Bron o'chirildi!", reply_markup=menu)
    await callback.answer()

@dp.callback_query(F.data == "orqaga")
async def orqaga(callback: CallbackQuery):
    menu = admin_menu() if callback.from_user.id == ADMIN_ID else main_menu()
    await callback.message.answer("Asosiy menyu:", reply_markup=menu)
    await callback.answer()

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    users = get_all_users()
    if not users:
        await callback.message.answer("👥 Hozircha hech kim ro'yxatdan o'tmagan.")
        await callback.answer()
        return
    buttons = [[InlineKeyboardButton(text=f"👤 {ism}", callback_data=f"user_{uid}")] for uid, ism in users if uid != ADMIN_ID]
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="orqaga")])
    await callback.message.answer("👥 <b>Hamkasblar:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data.startswith("user_"))
async def user_bronlari(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    user_id = int(callback.data.split("_")[1])
    ism = get_user(user_id)
    bronlar = get_bronlar(user_id)
    if not bronlar:
        await callback.message.answer(f"📋 <b>{ism}</b>ning broni yo'q.", parse_mode="HTML")
    else:
        text = f"📋 <b>{ism}</b>ning bronlari:\n\n"
        for i, (bid, dori, sana) in enumerate(bronlar, 1):
            text += f"{i}. 💊 <b>{dori}</b>\n   📅 {sana}\n\n"
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

async def main():
    init_db()
    print("Bot ishga tushdi!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
