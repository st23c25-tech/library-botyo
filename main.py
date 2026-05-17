import logging, sqlite3, asyncio, os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# --- ТОКЕН ---
TOKEN = os.getenv('BOT_TOKEN', '8463058055:AAEx-o0K2coqsR0Tb5JHnM0JVzkY5Z4HXVI')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

class LibS(StatesGroup):
    f = State(); t = State(); a = State(); d = State(); r = State(); edit_val = State()
    search_state = State()
    set_year_state = State()

def init_db():
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, author TEXT, description TEXT, 
            rating INTEGER, file_id TEXT, status TEXT,
            date_added TEXT, date_read TEXT, reread_count INTEGER DEFAULT 0,
            read_year INTEGER
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS reading_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            read_date TEXT,
            FOREIGN KEY (book_id) REFERENCES books (id)
        )''')
        
        try:
            conn.execute("ALTER TABLE books ADD COLUMN date_added TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE books ADD COLUMN date_read TEXT")
        except:
            pass
        try:
            conn.execute("ALTER TABLE books ADD COLUMN reread_count INTEGER DEFAULT 0")
        except:
            pass
        try:
            conn.execute("ALTER TABLE books ADD COLUMN read_year INTEGER")
        except:
            pass

async def send_book_info(chat_id, book_data):
    b_id, t, a, d, r, f_id, st, date_added, date_read, reread, read_year = book_data
    
    cap = f"📖 {t}\n👤 {a}\n📝 {d}\n"
    
    if st == 'read':
        cap += f"📊 ⭐ {r}/10\n"
        if read_year:
            cap += f"📅 Прочитано: {read_year} рік\n"
        if reread and reread > 0:
            cap += f"🔄 Перечитано: {reread} раз(и)\n"
    else:
        cap += f"📌 В планах\n"
    
    btns = []
    if st == 'wish':
        btns.append([InlineKeyboardButton(text="✅ Вже прочитала", callback_data=f"finish_{b_id}")])
    else:
        btns.append([InlineKeyboardButton(text="🔄 Перечитати", callback_data=f"reread_{b_id}"),
                     InlineKeyboardButton(text="📅 Змінити рік", callback_data=f"change_year_{b_id}")])
    
    btns.append([
        InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"menu_{b_id}"),
        InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_{b_id}")
    ])
    
    try:
        await bot.send_document(chat_id, f_id, caption=cap, 
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    except:
        await bot.send_message(chat_id, cap, 
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# --- ЗМІНА РОКУ ---
@dp.callback_query(F.data.startswith("change_year_"))
async def change_year_start(c: CallbackQuery, state: FSMContext):
    book_id = c.data.split("_")[2]
    await state.update_data(book_id=book_id)
    await state.set_state(LibS.set_year_state)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2024", callback_data="year_2024"),
         InlineKeyboardButton(text="2025", callback_data="year_2025"),
         InlineKeyboardButton(text="2026", callback_data="year_2026")],
        [InlineKeyboardButton(text="Інший рік", callback_data="year_other")]
    ])
    await c.message.answer("Оберіть рік, коли ви прочитали цю книгу:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("year_"))
async def set_year(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    book_id = data['book_id']
    
    if c.data == "year_other":
        await c.message.answer("Введіть рік (наприклад: 2020):")
        return
    
    year = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        conn.execute("UPDATE books SET read_year = ? WHERE id = ?", (year, book_id))
    
    await c.message.edit_text(f"✅ Рік прочитання змінено на {year}")
    await state.clear()

@dp.message(LibS.set_year_state)
async def set_year_manual(m: Message, state: FSMContext):
    try:
        year = int(m.text.strip())
        if 1900 <= year <= datetime.now().year:
            data = await state.get_data()
            book_id = data['book_id']
            with sqlite3.connect('my_library.db') as conn:
                conn.execute("UPDATE books SET read_year = ? WHERE id = ?", (year, book_id))
            await m.answer(f"✅ Рік прочитання змінено на {year}")
            await state.clear()
        else:
            await m.answer(f"❌ Введіть коректний рік (від 1900 до {datetime.now().year})")
    except ValueError:
        await m.answer("❌ Будь ласка, введіть число (рік)")

# --- СТАТИСТИКА ---
@dp.message(F.text == "📊 Статистика")
async def show_stats(m: Message):
    with sqlite3.connect('my_library.db') as conn:
        total_read = conn.execute('SELECT COUNT(*) FROM books WHERE status = "read"').fetchone()[0]
        total_wish = conn.execute('SELECT COUNT(*) FROM books WHERE status = "wish"').fetchone()[0]
        avg_rating_result = conn.execute('SELECT AVG(rating) FROM books WHERE status = "read" AND rating > 0').fetchone()[0]
        avg_rating = avg_rating_result if avg_rating_result else 0
        total_rereads_result = conn.execute('SELECT SUM(reread_count) FROM books WHERE status = "read"').fetchone()[0]
        total_rereads = total_rereads_result if total_rereads_result else 0
        current_year = datetime.now().year
        year_read = conn.execute('SELECT COUNT(*) FROM books WHERE status = "read" AND read_year = ?', (current_year,)).fetchone()[0]
        top_books = conn.execute('''SELECT title, rating FROM books WHERE status = "read" AND rating > 0 ORDER BY rating DESC LIMIT 5''').fetchall()
        
        stats_text = f"""📊 **ВАША СТАТИСТИКА ЧИТАННЯ**

📚 **Загалом:**
• Прочитано книг: {total_read}
• В планах: {total_wish}
• Середній рейтинг: {avg_rating:.1f}/10
• Всього перечитувань: {total_rereads}

📅 **За {current_year} рік:**
• Прочитано: {year_read} книг

⭐ **Топ-5 книг:**
{chr(10).join([f"{i+1}. {book[0]} - {book[1]}/10" for i, book in enumerate(top_books)]) if top_books else "Немає оцінених книг"}"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📅 За роками", callback_data="stats_years")]])
    await m.answer(stats_text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "stats_years")
async def stats_by_years(c: CallbackQuery):
    with sqlite3.connect('my_library.db') as conn:
        years_data = conn.execute('''SELECT read_year, COUNT(*) FROM books WHERE status = "read" AND read_year IS NOT NULL GROUP BY read_year ORDER BY read_year DESC''').fetchall()
        if not years_data:
            await c.message.answer("Немає даних про прочитані книги за роками")
            return
        text = "📅 **Статистика по роках:**\n\n" + "\n".join([f"• {year}: {count} книг" for year, count in years_data])
        await c.message.answer(text, parse_mode="Markdown")

# --- ЗВІТ ЗА РІК ---
@dp.message(F.text == "📅 Звіт за рік")
async def yearly_report(m: Message):
    with sqlite3.connect('my_library.db') as conn:
        years = conn.execute('SELECT DISTINCT read_year FROM books WHERE status = "read" AND read_year IS NOT NULL ORDER BY read_year DESC').fetchall()
    buttons = [[InlineKeyboardButton(text=str(year[0]), callback_data=f"report_{year[0]}")] for year in years]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await m.answer("Оберіть рік для звіту:", reply_markup=kb)

@dp.callback_query(F.data.startswith("report_"))
async def show_report(c: CallbackQuery):
    year = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        books_year = conn.execute('SELECT title, author, rating, read_year, reread_count FROM books WHERE status = "read" AND read_year = ? ORDER BY rating DESC', (year,)).fetchall()
        if not books_year:
            await c.message.answer(f"За {year} рік немає прочитаних книг")
            return
        rereads_year = sum(b[4] for b in books_year if b[4])
        ratings = [b[2] for b in books_year if b[2] > 0]
        avg_rating = sum(ratings)/len(ratings) if ratings else 0
        report_text = f"📚 **ЗВІТ ПРО ЧИТАННЯ ЗА {year} РІК**\n\n📖 Всього прочитано: {len(books_year)} книг\n🔄 Перечитано: {rereads_year} раз(и)\n⭐ Середній рейтинг: {avg_rating:.1f}/10\n\n📖 **Список прочитаного:**\n"
        for i, b in enumerate(books_year, 1):
            reread_info = f" (перечитано {b[4]} раз)" if b[4] and b[4] > 0 else ""
            report_text += f"{i}. {b[0]} - {b[1]} (⭐{b[2]}/10){reread_info}\n"
    await c.message.answer(report_text, parse_mode="Markdown")

# --- ДОДАВАННЯ КНИГ ---
@dp.message(F.text == "➕ Додати книгу")
async def add(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Прочитала", callback_data="s_read"), InlineKeyboardButton(text="⏳ В плани", callback_data="s_wish")]])
    await m.answer("Який статус книги?", reply_markup=kb)

@dp.callback_query(F.data.startswith("s_"))
async def set_s(c: CallbackQuery, state: FSMContext):
    await state.update_data(st='read' if c.data == "s_read" else 'wish')
    await state.set_state(LibS.f)
    await c.message.edit_text("Надішли файл книги:")

@dp.message(LibS.f, F.document)
async def p_f(m: Message, state: FSMContext):
    await state.update_data(fid=m.document.file_id)
    await state.set_state(LibS.t)
    await m.answer("Введи назву книги:")

@dp.message(LibS.t)
async def p_t(m: Message, state: FSMContext):
    await state.update_data(t=m.text.strip())
    await state.set_state(LibS.a)
    await m.answer("Введи автора:")

@dp.message(LibS.a)
async def p_a(m: Message, state: FSMContext):
    await state.update_data(a=m.text.strip())
    await state.set_state(LibS.d)
    await m.answer("Додай опис або відгук:")

@dp.message(LibS.d)
async def p_d(m: Message, state: FSMContext):
    data = await state.get_data()
    if data['st'] == 'read':
        await state.update_data(d=m.text.strip())
        await state.set_state(LibS.r)
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(i), callback_data=f"r_{i}") for i in range(1, 6)], [InlineKeyboardButton(text=str(i), callback_data=f"r_{i}") for i in range(6, 11)]])
        await m.answer("Оцінка 1-10:", reply_markup=kb)
    else:
        with sqlite3.connect('my_library.db') as conn:
            conn.execute('INSERT INTO books (title, author, description, rating, file_id, status, date_added) VALUES (?,?,?,?,?,?,?)', (data['t'], data['a'], m.text.strip(), 0, data['fid'], 'wish', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        await m.answer("✨ Книгу додано в плани!")
        await state.clear()

@dp.callback_query(F.data.startswith("r_"))
async def p_r(c: CallbackQuery, state: FSMContext):
    rat = c.data.split("_")[1]
    data = await state.get_data()
    current_year = datetime.now().year
    await state.update_data(rating=rat, new_book_data=data)
    await state.set_state(LibS.set_year_state)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Цього року", callback_data="year_this"), InlineKeyboardButton(text="Інший рік", callback_data="year_choose")]])
    await c.message.answer("Коли ви прочитали цю книгу?", reply_markup=kb)

@dp.callback_query(F.data == "year_this")
async def save_with_current_year(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    book_data = data['new_book_data']
    rating = data['rating']
    current_year = datetime.now().year
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('INSERT INTO books (title, author, description, rating, file_id, status, date_added, date_read, read_year) VALUES (?,?,?,?,?,?,?,?,?)', (book_data['t'], book_data['a'], book_data['d'], rating, book_data['fid'], 'read', current_time, current_time, current_year))
    await c.message.edit_text(f"✅ Збережено з оцінкою {rating}/10 за {current_year} рік!")
    await state.clear()

@dp.callback_query(F.data == "year_choose")
async def ask_for_year(c: CallbackQuery, state: FSMContext):
    await c.message.answer("Введіть рік (наприклад: 2020):")

@dp.message(LibS.set_year_state)
async def save_with_custom_year(m: Message, state: FSMContext):
    try:
        year = int(m.text.strip())
        if 1900 <= year <= datetime.now().year:
            data = await state.get_data()
            book_data = data['new_book_data']
            rating = data['rating']
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with sqlite3.connect('my_library.db') as conn:
                conn.execute('INSERT INTO books (title, author, description, rating, file_id, status, date_added, date_read, read_year) VALUES (?,?,?,?,?,?,?,?,?)', (book_data['t'], book_data['a'], book_data['d'], rating, book_data['fid'], 'read', current_time, current_time, year))
            await m.answer(f"✅ Збережено з оцінкою {rating}/10 за {year} рік!")
            await state.clear()
        else:
            await m.answer(f"❌ Введіть коректний рік (від 1900 до {datetime.now().year})")
    except ValueError:
        await m.answer("❌ Будь ласка, введіть число (рік)")

# --- ПЕРЕЧИТУВАННЯ ---
@dp.callback_query(F.data.startswith("reread_"))
async def reread_book(c: CallbackQuery):
    book_id = c.data.split("_")[1]
    current_year = datetime.now().year
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('UPDATE books SET reread_count = reread_count + 1, read_year = ? WHERE id = ?', (current_year, book_id))
        title = conn.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()[0]
    await c.message.answer(f"🔄 Книгу '{title}' додано до перечитаних за {current_year} рік!")
    await c.answer()

# --- ПОКАЗ КНИГ ---
@dp.message(F.text.in_(["📚 Прочитане", "📝 Хочу прочитати"]))
async def show(m: Message):
    st = 'read' if "Прочитане" in m.text else 'wish'
    with sqlite3.connect('my_library.db') as conn:
        books = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE status = ?', (st,)).fetchall()
    if not books:
        return await m.answer("Тут порожньо.")
    for book in books:
        await send_book_info(m.chat.id, book)

# --- ЗАВЕРШЕННЯ КНИГИ З ПЛАНІВ ---
@dp.callback_query(F.data.startswith("finish_"))
async def finish(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=c.data.split("_")[1])
    await state.set_state(LibS.r)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(i), callback_data=f"moverat_{i}") for i in range(1, 6)], [InlineKeyboardButton(text=str(i), callback_data=f"moverat_{i}") for i in range(6, 11)]])
    await c.message.answer("Яку оцінку поставиш?", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("moverat_"))
async def save_move(c: CallbackQuery, state: FSMContext):
    rat = c.data.split("_")[1]
    data = await state.get_data()
    current_year = datetime.now().year
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('UPDATE books SET status = "read", rating = ?, read_year = ? WHERE id = ?', (rat, current_year, data['eid']))
    await c.message.edit_text(f"🎊 Перенесено в прочитане з оцінкою {rat}/10 за {current_year} рік!")
    await state.clear()

# --- ПОШУК ---
@dp.message(F.text == "🔍 Пошук")
async def search_start(m: Message, state: FSMContext):
    await state.set_state(LibS.search_state)
    await m.answer("Введи назву книги або автора (можна частину слова):")

@dp.message(LibS.search_state)
async def search_logic(m: Message, state: FSMContext):
    if m.text in ["➕ Додати книгу", "📚 Прочитане", "📝 Хочу прочитати", "🔍 Пошук", "📊 Статистика", "📅 Звіт за рік"]:
        await state.clear()
        return
    query = f"%{m.text.lower()}%"
    with sqlite3.connect('my_library.db') as conn:
        cursor = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?', (query, query))
        found_books = cursor.fetchall()
    if not found_books:
        await m.answer(f"За запитом '{m.text}' нічого не знайдено. 🔍")
        await state.clear()
        return
    await m.answer(f"🔍 Знайдено {len(found_books)} книг:")
    for book in found_books:
        await send_book_info(m.chat.id, book)
    await state.clear()

# --- РЕДАГУВАННЯ ---
@dp.callback_query(F.data.startswith("menu_"))
async def edit_m(c: CallbackQuery):
    b_id = c.data.split("_")[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назву", callback_data=f"ed_title_{b_id}"), InlineKeyboardButton(text="Автора", callback_data=f"ed_author_{b_id}")],
        [InlineKeyboardButton(text="Опис", callback_data=f"ed_desc_{b_id}"), InlineKeyboardButton(text="Рейтинг", callback_data=f"ed_rating_{b_id}")],
        [InlineKeyboardButton(text="📅 Рік прочитання", callback_data=f"ed_year_{b_id}"), InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{b_id}")]
    ])
    await c.message.answer("Що змінити?", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("ed_"))
async def ed_st(c: CallbackQuery, state: FSMContext):
    parts = c.data.split("_")
    if len(parts) == 3:
        _, f, b_id = parts
        await state.update_data(eid=b_id, fld=f)
        await state.set_state(LibS.edit_val)
        await c.message.answer("Введи нове значення:" if f != "year" else "Введи новий рік прочитання (наприклад: 2020):")
        await c.answer()

@dp.callback_query(F.data.startswith("back_"))
async def back_to_book(c: CallbackQuery):
    b_id = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        book = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE id = ?', (b_id,)).fetchone()
        if book:
            await send_book_info(c.message.chat.id, book)

@dp.message(LibS.edit_val)
async def ed_sv(m: Message, state: FSMContext):
    data = await state.get_data()
    field_map = {"title": "title", "author": "author", "desc": "description", "rating": "rating", "year": "read_year"}
    
    if data['fld'] == 'rating':
        try:
            new_value = int(m.text.strip())
            if not 1 <= new_value <= 10:
                await m.answer("Рейтинг має бути від 1 до 10!")
                return
        except ValueError:
            await m.answer("Введіть число від 1 до 10!")
            return
    elif data['fld'] == 'year':
        try:
            new_value = int(m.text.strip())
            if not 1900 <= new_value <= datetime.now().year:
                await m.answer(f"Введіть коректний рік (1900-{datetime.now().year})!")
                return
        except ValueError:
            await m.answer("Введіть число (рік)!")
            return
    else:
        new_value = m.text.strip()
    
    with sqlite3.connect('my_library.db') as conn:
        conn.execute(f"UPDATE books SET {field_map[data['fld']]} = ? WHERE id = ?", (new_value, data['eid']))
    await m.answer("✅ Оновлено!")
    await state.clear()

@dp.callback_query(F.data.startswith("del_"))
async def delete(c: CallbackQuery):
    book_id = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        conn.execute("DELETE FROM reading_history WHERE book_id = ?", (book_id,))
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await c.message.delete()
    await c.answer("Книгу видалено!")

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def health_check(request):
    return web.Response(text="Bot is running!")

async def start_web():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    return runner

# --- ГОЛОВНЕ МЕНЮ ---
@dp.message(Command("start"))
async def start(m: Message):
    init_db()
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="➕ Додати книгу")],
        [types.KeyboardButton(text="📚 Прочитане"), types.KeyboardButton(text="📝 Хочу прочитати")],
        [types.KeyboardButton(text="🔍 Пошук"), types.KeyboardButton(text="📊 Статистика")],
        [types.KeyboardButton(text="📅 Звіт за рік")]
    ], resize_keyboard=True)
    await m.answer("📚 Твоя бібліотека готова до роботи!", reply_markup=kb)

# --- ЗАПУСК ---
async def main():
    init_db()
    # Запускаємо веб-сервер для Render
    web_runner = await start_web()
    print("Бот запущений і готовий до роботи!")
    try:
        await dp.start_polling(bot)
    finally:
        await web_runner.cleanup()

if __name__ == '__main__':
    asyncio.run(main())