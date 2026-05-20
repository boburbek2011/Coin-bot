import os
import asyncio
import sqlite3
import random
import io
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.utils import executor
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# ============= TOKENNI YUKLASH =============
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 1190566388))

if not API_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! .env faylini tekshiring.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ============= DATABAZA =============
conn = sqlite3.connect('notcoin_game.db', check_same_thread=False)
c = conn.cursor()

# Foydalanuvchilar
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY,
              coins INTEGER DEFAULT 0,
              energy INTEGER DEFAULT 1000,
              level INTEGER DEFAULT 1,
              referrer_id INTEGER DEFAULT 0,
              tap_count INTEGER DEFAULT 0,
              is_admin INTEGER DEFAULT 0)''')

# Stikerlar inventari
c.execute('''CREATE TABLE IF NOT EXISTS user_stickers
             (user_id INTEGER,
              sticker_id TEXT,
              quantity INTEGER,
              PRIMARY KEY(user_id, sticker_id))''')

# Stikerlar ro'yxati
c.execute('''CREATE TABLE IF NOT EXISTS stickers_list
             (sticker_id TEXT PRIMARY KEY,
              name TEXT,
              emoji TEXT,
              rarity TEXT,
              base_price INTEGER)''')

# Vazifalar
c.execute('''CREATE TABLE IF NOT EXISTS tasks
             (task_id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              description TEXT,
              reward_type TEXT,
              reward_value TEXT,
              required_taps INTEGER DEFAULT 0,
              is_active INTEGER DEFAULT 1)''')

# Bajarilgan vazifalar
c.execute('''CREATE TABLE IF NOT EXISTS user_tasks
             (user_id INTEGER,
              task_id INTEGER,
              completed INTEGER DEFAULT 0,
              PRIMARY KEY(user_id, task_id))''')

# Do'kon mahsulotlari
c.execute('''CREATE TABLE IF NOT EXISTS shop_items
             (item_id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT,
              description TEXT,
              price INTEGER,
              file_path TEXT,
              is_available INTEGER DEFAULT 1)''')

# Sotib olingan mahsulotlar
c.execute('''CREATE TABLE IF NOT EXISTS user_purchases
             (user_id INTEGER,
              item_id INTEGER,
              purchase_date TIMESTAMP)''')

conn.commit()

# ============= 3D RENDER FUNKSIYASI =============
def generate_3d_render(user_id, coins, level, tap_count, sticker_count=0):
    """3D-stilizatsiyadagi rasm yaratadi, variables rasmga yoziladi"""
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color=(8, 8, 28))
    draw = ImageDraw.Draw(img)
    
    # 3D effekt - nur chiziqlari
    for i in range(0, width, 50):
        offset = (tap_count % 100) / 100 * 50
        x = i + offset
        draw.line([(x, 0), (x + 150, height)], fill=(50, 150, 255, 80), width=2)
    
    # Markaziy doiralar (3D effekt)
    for r in range(80, 220, 25):
        alpha = int(150 - (r-80)/2)
        draw.ellipse([width//2 - r, height//2 - r, width//2 + r, height//2 + r], 
                     outline=(255, 200, 0, alpha), width=2)
    
    # Yorqin markaz
    draw.ellipse([width//2 - 30, height//2 - 30, width//2 + 30, height//2 + 30], 
                 fill=(255, 200, 50, 150))
    
    # Font yuklash
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
        font_small = font
    
    # Variables rasmga yoziladi
    info_lines = [
        f"👤 ID: {user_id}",
        f"🪙 Coins: {coins}",
        f"📈 Level: {level}",
        f"👆 Tap: {tap_count}",
        f"🎨 Stickers: {sticker_count}"
    ]
    
    y_offset = height - 120
    for line in info_lines:
        draw.text((15, y_offset), line, fill=(255, 255, 255), font=font_small)
        y_offset += 22
    
    # Render vaqti
    draw.text((width - 170, height - 25), f"⚡ {datetime.now().strftime('%H:%M:%S')}", 
              fill=(100, 150, 255), font=font_small)
    
    # Rasmni bytes ga o'tkazish
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return InputFile(img_io, filename=f"render_{user_id}.png")

# ============= YORDAMCHI FUNKSIYALAR =============
def is_admin(user_id):
    if user_id == ADMIN_ID:
        return True
    c.execute("SELECT is_admin FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row and row[0] == 1

def get_user_data(user_id):
    c.execute("SELECT coins, energy, level, tap_count FROM users WHERE user_id=?", (user_id,))
    return c.fetchone()

def get_sticker_count(user_id):
    c.execute("SELECT SUM(quantity) FROM user_stickers WHERE user_id=?", (user_id,))
    row = c.fetchone()
    return row[0] if row[0] else 0

def get_user_stickers(user_id):
    c.execute("SELECT sticker_id, quantity FROM user_stickers WHERE user_id=?", (user_id,))
    return c.fetchall()

# ============= KLAVIATURALAR =============
def main_menu(user_id):
    data = get_user_data(user_id)
    if not data:
        return None
    coins, energy, level, _ = data
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"🪙 Tap +{level*10}", callback_data="tap"),
        InlineKeyboardButton(f"⚡ {energy}/1000", callback_data="energy_info")
    )
    keyboard.add(
        InlineKeyboardButton("📊 Stats", callback_data="stats"),
        InlineKeyboardButton("🎨 Stikerlar", callback_data="stickers")
    )
    keyboard.add(
        InlineKeyboardButton("📦 Do'kon", callback_data="shop"),
        InlineKeyboardButton("🔄 Trade", callback_data="trade_menu")
    )
    keyboard.add(
        InlineKeyboardButton("📋 Vazifalar", callback_data="tasks"),
        InlineKeyboardButton("⬆️ Level up", callback_data="upgrade")
    )
    if is_admin(user_id):
        keyboard.add(InlineKeyboardButton("👑 Admin", callback_data="admin_panel"))
    return keyboard

# ============= STARTER MA'LUMOTLAR =============
def init_database():
    # Standart stikerlar
    stickers = [
        ("common_cat", "Mushuk", "🐱", "common", 100),
        ("rare_diamond", "Olmos", "💎", "rare", 500),
        ("epic_phoenix", "Anqa", "🔥", "epic", 2000),
        ("legendary_dragon", "Ajdar", "🐉", "legendary", 10000)
    ]
    for s in stickers:
        c.execute("INSERT OR IGNORE INTO stickers_list VALUES (?,?,?,?,?)", s)
    
    # Standart vazifalar
    tasks = [
        ("Boshlang'ich", "100 marta tap qil", "coins", "500", 100),
        ("Tajribali", "500 marta tap qil", "sticker", "rare_diamond", 500),
        ("Legenda", "1000 marta tap qil", "coins", "5000", 1000)
    ]
    for t in tasks:
        c.execute("INSERT OR IGNORE INTO tasks (name, description, reward_type, reward_value, required_taps) VALUES (?,?,?,?,?)", t)
    
    conn.commit()

# ============= BOT KOMANDALARI =============
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    referrer = 0
    
    if len(message.text.split()) > 1:
        try:
            referrer = int(message.text.split()[1])
        except:
            pass
    
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, referrer_id) VALUES (?,?)", (user_id, referrer))
        if referrer and referrer != user_id:
            c.execute("UPDATE users SET coins = coins + 5000 WHERE user_id=?", (referrer,))
        conn.commit()
    
    data = get_user_data(user_id)
    sticker_count = get_sticker_count(user_id)
    render_img = generate_3d_render(user_id, data[0], data[2], data[3], sticker_count)
    
    await message.answer_photo(
        photo=render_img,
        caption="🌟 **CUSTOM NOTCOIN** 🌟\n\n👇 Tap qil va coin yig'!\n🎨 Stikerlar yig'!\n🔄 Trade qil!",
        parse_mode="Markdown",
        reply_markup=main_menu(user_id)
    )

@dp.callback_query_handler(lambda c: c.data == "tap")
async def tap_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    if not data:
        return
    
    coins, energy, level, taps = data
    
    if energy < 10:
        await callback.answer("⚡ Energiya yetarli emas! 10 soniyada to'ldiradi.", show_alert=True)
        return
    
    reward = level * 10
    new_coins = coins + reward
    new_energy = energy - 10
    new_taps = taps + 1
    
    c.execute("UPDATE users SET coins=?, energy=?, tap_count=? WHERE user_id=?", 
              (new_coins, new_energy, new_taps, user_id))
    conn.commit()
    
    # Vazifalarni tekshirish
    c.execute("SELECT task_id, required_taps, reward_type, reward_value FROM tasks WHERE required_taps>0 AND is_active=1")
    tasks = c.fetchall()
    for task_id, req_taps, rtype, rval in tasks:
        if new_taps >= req_taps:
            c.execute("SELECT completed FROM user_tasks WHERE user_id=? AND task_id=?", (user_id, task_id))
            if not c.fetchone():
                if rtype == "coins":
                    c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (int(rval), user_id))
                    await callback.message.answer(f"✅ Vazifa bajarildi! +{rval} coin")
                elif rtype == "sticker":
                    c.execute("INSERT INTO user_stickers (user_id, sticker_id, quantity) VALUES (?,?,1) ON CONFLICT(user_id,sticker_id) DO UPDATE SET quantity = quantity + 1", (user_id, rval))
                    await callback.message.answer(f"✅ Vazifa bajarildi! '{rval}' stikerini oldingiz!")
                c.execute("INSERT INTO user_tasks VALUES (?,?,1)", (user_id, task_id))
                conn.commit()
    
    sticker_count = get_sticker_count(user_id)
    render_img = generate_3d_render(user_id, new_coins, level, new_taps, sticker_count)
    
    await callback.message.answer_photo(
        photo=render_img,
        caption=f"✨ +{reward} 🪙 | ⚡ {new_energy}/1000",
        reply_markup=main_menu(user_id)
    )
    await callback.answer(f"+{reward} coin!")

@dp.callback_query_handler(lambda c: c.data == "stats")
async def stats_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    sticker_count = get_sticker_count(user_id)
    
    if data:
        coins, energy, level, taps = data
        text = f"📊 **SIZNING STATISTIKA**\n\n"
        text += f"🪙 Coins: {coins}\n"
        text += f"⚡ Energiya: {energy}/1000\n"
        text += f"📈 Level: {level}\n"
        text += f"👆 Tap soni: {taps}\n"
        text += f"🎨 Stikerlar: {sticker_count}\n"
        text += f"\n💰 Keyingi level: {level * 5000} coin"
    
    await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=main_menu(user_id))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "stickers")
async def stickers_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    stickers = get_user_stickers(user_id)
    
    if not stickers:
        text = "📭 **Sizda stiker yo'q**\n\nVazifalarni bajarib stiker yig'ing!"
    else:
        text = "🎨 **SIZNING STIKERLARINGIZ**\n\n"
        for sid, qty in stickers:
            c.execute("SELECT name, emoji, rarity FROM stickers_list WHERE sticker_id=?", (sid,))
            row = c.fetchone()
            if row:
                name, emoji, rarity = row
                rarity_emoji = {"common": "⚪", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}.get(rarity, "⚪")
                text += f"{emoji} {name} {rarity_emoji} x{qty}\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "shop")
async def shop_callback(callback: types.CallbackQuery):
    c.execute("SELECT item_id, name, description, price FROM shop_items WHERE is_available=1")
    items = c.fetchall()
    
    if not items:
        text = "📦 **Do'kon bo'sh**\n\nAdmin tez orada mahsulot qo'shadi."
    else:
        text = "🛒 **FAYLLAR DO'KONI**\n\n"
        for item_id, name, desc, price in items:
            text += f"📄 *{name}*\n   {desc}\n   Narx: {price} coin\n   `/buy_{item_id}`\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=kb)

@dp.message_handler(commands=['buy_'])
async def buy_item(message: types.Message):
    user_id = message.from_user.id
    try:
        item_id = int(message.text.split('_')[1])
    except:
        await message.answer("❌ Noto'g'ri format! `/buy_1` ko'rinishida yozing")
        return
    
    c.execute("SELECT price, file_path, name FROM shop_items WHERE item_id=?", (item_id,))
    row = c.fetchone()
    if not row:
        await message.answer("❌ Bunday mahsulot topilmadi")
        return
    
    price, file_path, name = row
    data = get_user_data(user_id)
    
    if data[0] < price:
        await message.answer(f"❌ Yetarli coin yo'q! Kerak: {price} coin")
        return
    
    c.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (price, user_id))
    c.execute("INSERT INTO user_purchases VALUES (?,?,?)", (user_id, item_id, datetime.now()))
    conn.commit()
    
    if os.path.exists(file_path):
        await bot.send_document(user_id, InputFile(file_path), caption=f"✅ Siz *{name}* faylini sotib oldingiz!", parse_mode="Markdown")
    else:
        await message.answer(f"✅ Siz *{name}* faylini sotib oldingiz! Admin sizga yuboradi.", parse_mode="Markdown")
    
    await message.answer("🎉 Xarid muvaffaqiyatli!")

@dp.callback_query_handler(lambda c: c.data == "trade_menu")
async def trade_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Coin yuborish", callback_data="trade_coin"),
        InlineKeyboardButton("🎨 Stiker yuborish", callback_data="trade_sticker")
    )
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    await callback.message.edit_caption(caption="🔄 **TRADE MENYUSI**\n\nKimga va nima yubormoqchisiz?", parse_mode="Markdown", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "trade_coin")
async def trade_coin_start(callback: types.CallbackQuery):
    await callback.message.answer("💰 **COIN YUBORISH**\n\n`/sendcoin [user_id] [miqdor]`\n\nMisol: `/sendcoin 123456789 1000`")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "trade_sticker")
async def trade_sticker_start(callback: types.CallbackQuery):
    await callback.message.answer("🎨 **STIKER YUBORISH**\n\n`/sendsticker [user_id] [stiker_id] [miqdor]`\n\n📋 Mavjud stikerlar:\n• common_cat\n• rare_diamond\n• epic_phoenix\n• legendary_dragon\n\nMisol: `/sendsticker 123456789 common_cat 2`")
    await callback.answer()

@dp.message_handler(commands=['sendcoin'])
async def send_coin(message: types.Message):
    sender = message.from_user.id
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Format: `/sendcoin user_id miqdor`")
        return
    
    if amount <= 0:
        await message.answer("❌ Miqdor musbat bo'lishi kerak")
        return
    
    data = get_user_data(sender)
    if data[0] < amount:
        await message.answer(f"❌ Yetarli coin yo'q! Sizda: {data[0]} coin")
        return
    
    c.execute("SELECT user_id FROM users WHERE user_id=?", (target_id,))
    if not c.fetchone():
        await message.answer("❌ Bunday foydalanuvchi topilmadi")
        return
    
    c.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (amount, sender))
    c.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, target_id))
    conn.commit()
    
    await message.answer(f"✅ {amount} coin {target_id} ga yuborildi!")
    await bot.send_message(target_id, f"🎉 Sizga {amount} coin yuborildi! @{message.from_user.username} dan")

@dp.message_handler(commands=['sendsticker'])
async def send_sticker(message: types.Message):
    sender = message.from_user.id
    try:
        parts = message.text.split()
        target_id = int(parts[1])
        sticker_id = parts[2]
        qty = int(parts[3])
    except:
        await message.answer("❌ Format: `/sendsticker user_id stiker_id miqdor`")
        return
    
    c.execute("SELECT quantity FROM user_stickers WHERE user_id=? AND sticker_id=?", (sender, sticker_id))
    row = c.fetchone()
    if not row or row[0] < qty:
        await message.answer(f"❌ Sizda yetarli stiker yo'q! {sticker_id} dan {row[0] if row else 0} dona bor")
        return
    
    c.execute("SELECT user_id FROM users WHERE user_id=?", (target_id,))
    if not c.fetchone():
        await message.answer("❌ Bunday foydalanuvchi topilmadi")
        return
    
    c.execute("UPDATE user_stickers SET quantity = quantity - ? WHERE user_id=? AND sticker_id=?", (qty, sender, sticker_id))
    c.execute("INSERT INTO user_stickers (user_id, sticker_id, quantity) VALUES (?,?,?) ON CONFLICT(user_id,sticker_id) DO UPDATE SET quantity = quantity + ?", 
              (target_id, sticker_id, qty, qty))
    conn.commit()
    
    await message.answer(f"✅ {qty} dona {sticker_id} stikeri {target_id} ga yuborildi!")
    
    c.execute("SELECT name FROM stickers_list WHERE sticker_id=?", (sticker_id,))
    sticker_name = c.fetchone()
    sticker_name = sticker_name[0] if sticker_name else sticker_id
    await bot.send_message(target_id, f"🎁 Sizga {qty} dona *{sticker_name}* stikeri yuborildi! @{message.from_user.username} dan", parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "tasks")
async def tasks_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    c.execute("SELECT task_id, name, description, required_taps, reward_type, reward_value FROM tasks WHERE is_active=1")
    tasks = c.fetchall()
    
    if not tasks:
        text = "📋 **Hozircha vazifalar yo'q**\n\nAdmin tez orada qo'shadi."
    else:
        text = "📋 **VAZIFALAR**\n\n"
        for task_id, name, desc, taps, rtype, rval in tasks:
            c.execute("SELECT completed FROM user_tasks WHERE user_id=? AND task_id=?", (user_id, task_id))
            done = c.fetchone()
            status = "✅" if done else "❌"
            reward_text = f"+{rval} coin" if rtype == "coins" else f"+{rval} stiker"
            text += f"{status} *{name}*\n   {desc} ({taps} tap) → {reward_text}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main"))
    await callback.message.edit_caption(caption=text, parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "upgrade")
async def upgrade_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    coins, energy, level, taps = data
    cost = level * 5000
    
    if coins >= cost:
        c.execute("UPDATE users SET coins = coins - ?, level = level + 1 WHERE user_id=?", (cost, user_id))
        conn.commit()
        await callback.answer(f"✅ Level {level+1} ga ko'tarildi!", show_alert=True)
        
        sticker_count = get_sticker_count(user_id)
        render_img = generate_3d_render(user_id, coins - cost, level + 1, taps, sticker_count)
        await callback.message.edit_caption(caption=f"⬆️ **LEVEL {level+1}**", parse_mode="Markdown", reply_markup=main_menu(user_id))
    else:
        await callback.answer(f"❌ Kerak: {cost} coin | Sizda: {coins} coin", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = get_user_data(user_id)
    sticker_count = get_sticker_count(user_id)
    render_img = generate_3d_render(user_id, data[0], data[2], data[3], sticker_count)
    await callback.message.answer_photo(photo=render_img, caption="🌟 **CUSTOM NOTCOIN**", parse_mode="Markdown", reply_markup=main_menu(user_id))

# ============= ADMIN PANELI =============
@dp.callback_query_handler(lambda c: c.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Faqat admin!", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("💰 Cheksiz coin", callback_data="admin_inf_coins"),
        InlineKeyboardButton("⚡ Cheksiz energy", callback_data="admin_inf_energy"),
        InlineKeyboardButton("📈 Cheksiz level", callback_data="admin_inf_level")
    )
    kb.add(
        InlineKeyboardButton("🎨 Stiker qo'shish", callback_data="admin_add_sticker"),
        InlineKeyboardButton("📋 Vazifa qo'shish", callback_data="admin_add_task"),
        InlineKeyboardButton("📦 Fayl qo'shish", callback_data="admin_add_file")
    )
    kb.add(
        InlineKeyboardButton("📊 Statistik", callback_data="admin_stats"),
        InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")
    )
    await callback.message.edit_caption(caption="👑 **ADMIN PANELI**\n\nQuyidagi funksiyalardan birini tanlang:", parse_mode="Markdown", reply_markup=kb)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("admin_inf_"))
async def admin_infinite(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    typ = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    if typ == "coins":
        c.execute("UPDATE users SET coins = 999999999 WHERE user_id=?", (user_id,))
        await callback.answer("✅ 999,999,999 coin qo'shildi!", show_alert=True)
    elif typ == "energy":
        c.execute("UPDATE users SET energy = 100000 WHERE user_id=?", (user_id,))
        await callback.answer("✅ 100,000 energiya qo'shildi!", show_alert=True)
    elif typ == "level":
        c.execute("UPDATE users SET level = 100 WHERE user_id=?", (user_id,))
        await callback.answer("✅ Level 100 ga ko'tarildi!", show_alert=True)
    conn.commit()

@dp.callback_query_handler(lambda c: c.data == "admin_add_sticker")
async def admin_add_sticker_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    text = "🎨 **STIKER QO'SHISH**\n\n"
    text += "Format:\n`stiker_id | nomi | emoji | rarity | narx`\n\n"
    text += "**Rarity turlari:** common, rare, epic, legendary\n\n"
    text += "**Misol:**\n`gold_coin | Oltin tanga | 🪙 | legendary | 5000`\n\n"
    text += "❗ Stiker ID da probel va maxsus belgilar bo'lmasin!"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_add_task")
async def admin_add_task_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    text = "📋 **VAZIFA QO'SHISH**\n\n"
    text += "Format:\n`vazifa_nomi | tavsif | tap_soni | coins/sticker | qiymat`\n\n"
    text += "**Misol coin:**\n`Kunlik | 100 tap qil | 100 | coins | 500`\n\n"
    text += "**Misol sticker:**\n`Yangi yil | 50 tap qil | 50 | sticker | gold_coin`"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_add_file")
async def admin_add_file_prompt(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    text = "📦 **FAYL QO'SHISH**\n\n"
    text += "Format:\n`fayl_nomi | tavsif | narx | fayl_yoli`\n\n"
    text += "**Misol:**\n`Premium rasm | Chiroyli fon rasmi | 5000 | shop_files/wallpaper.jpg`\n\n"
    text += "❗ Faylni avval 'shop_files' papkasiga yuklang!"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT SUM(coins) FROM users")
    total_coins = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(tap_count) FROM users")
    total_taps = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM shop_items")
    total_items = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = c.fetchone()[0]
    
    text = f"📊 **ADMIN STATISTIKA**\n\n"
    text += f"👥 Foydalanuvchilar: {total_users}\n"
    text += f"🪙 Jami coinlar: {total_coins}\n"
    text += f"👆 Jami tap: {total_taps}\n"
    text += f"📦 Do'kon mahsulotlari: {total_items}\n"
    text += f"📋 Vazifalar: {total_tasks}\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# Admin uchun qo'shimcha: boshqa foydalanuvchilarga adminlik berish
@dp.message_handler(commands=['makeadmin'])
async def make_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz super admin emassiz!")
        return
    
    try:
        target_id = int(message.text.split()[1])
        c.execute("UPDATE users SET is_admin = 1 WHERE user_id=?", (target_id,))
        conn.commit()
        await message.answer(f"✅ {target_id} admin qilindi!")
    except:
        await message.answer("❌ Format: `/makeadmin user_id`")

# ============= MATNLI XABARLARNI QAYTA ISHLASH =============
@dp.message_handler(content_types=['text'])
async def handle_text_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Admin yaratish (stiker, vazifa, fayl)
    if is_admin(user_id):
        # Stiker qo'shish: id | nom | emoji | rarity | narx
        if " | " in text and len(text.split(" | ")) == 5:
            parts = [p.strip() for p in text.split(" | ")]
            
            # Stiker yaratish
            if len(parts) == 5 and not any([p in ["coins", "sticker"] for p in parts]):
                try:
                    sticker_id, name, emoji, rarity, price = parts
                    price = int(price)
                    
                    if rarity not in ["common", "rare", "epic", "legendary"]:
                        await message.answer("❌ Rarity: common, rare, epic, legendary bo'lishi kerak!")
                        return
                    
                    c.execute("INSERT OR REPLACE INTO stickers_list VALUES (?,?,?,?,?)", 
                              (sticker_id, name, emoji, rarity, price))
                    conn.commit()
                    await message.answer(f"✅ Stiker qo'shildi!\n\n{emoji} {name} ({rarity}) - {price} coin")
                except Exception as e:
                    await message.answer(f"❌ Xato: {e}")
                return
            
            # Vazifa qo'shish
            elif len(parts) == 5 and parts[3] in ["coins", "sticker"]:
                try:
                    name, desc, taps, rtype, rval = parts
                    taps = int(taps)
                    
                    c.execute("INSERT INTO tasks (name, description, required_taps, reward_type, reward_value) VALUES (?,?,?,?,?)",
                              (name, desc, taps, rtype, rval))
                    conn.commit()
                    await message.answer(f"✅ Vazifa qo'shildi!\n\n{name}: {desc} → +{rval} {rtype}")
                except Exception as e:
                    await message.answer(f"❌ Xato: {e}")
                return
        
        # Fayl qo'shish
        elif " | " in text and len(text.split(" | ")) == 4:
            parts = [p.strip() for p in text.split(" | ")]
            try:
                name, desc, price, file_path = parts
                price = int(price)
                
                c.execute("INSERT INTO shop_items (name, description, price, file_path) VALUES (?,?,?,?)",
                          (name, desc, price, file_path))
                conn.commit()
                await message.answer(f"✅ Fayl do'konga qo'shildi!\n\n{name} - {price} coin")
            except Exception as e:
                await message.answer(f"❌ Xato: {e}")
            return
    
    # Boshqa xabarlarni ignore qilish
    if not text.startswith('/'):
        await message.answer("❓ Tushunarsiz buyruq. /start bilan botni qayta ishga tushiring.")

# ============= ENERGIYA TIKLANISHI =============
async def energy_recovery():
    while True:
        await asyncio.sleep(10)
        c.execute("UPDATE users SET energy = MIN(1000, energy + 5)")
        conn.commit()

# ============= ISHGA TUSHIRISH =============
if __name__ == "__main__":
    # Papkalarni yaratish
    os.makedirs("shop_files", exist_ok=True)
    
    # Databazani init qilish
    init_database()
    
    print("🤖 Bot ishga tushdi!")
    print(f"👑 Admin ID: {ADMIN_ID}")
    
    # Energiya tiklashni ishga tushirish
    loop = asyncio.get_event_loop()
    loop.create_task(energy_recovery())
    
    # Botni ishga tushirish
    executor.start_polling(dp, skip_updates=True)