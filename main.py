import logging, sqlite3, asyncio, os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = os.getenv('BOT_TOKEN', '8463058055:AAEHReRHUMRx5feJJoU-gvOtRh340MQZhzI')

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

class LibS(StatesGroup):
    f = State()
    t = State()
    a = State()
    d = State()
    r = State()
    edit_val = State()
    search_state = State()
    set_year_state = State()
    # Стани для швидкого додавання
    quick_year_state = State()
    quick_author_state = State()
    quick_desc_state = State()
    quick_rating_state = State()

def init_db():
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            title TEXT, author TEXT, description TEXT, 
            rating INTEGER, file_id TEXT, status TEXT,
            date_added TEXT, date_read TEXT, reread_count INTEGER DEFAULT 0,
            read_year INTEGER
        )''')
        for col in ['date_added', 'date_read', 'reread_count', 'read_year']:
            try:
                conn.execute(f"ALTER TABLE books ADD COLUMN {col}")
            except:
                pass

# ========== ШВИДКЕ ДОДАВАННЯ (БЕЗ ЗАЙВИХ ПИТАНЬ) ==========
@dp.message(F.text == "⚡ Швидке додавання")
async def quick_mode(m: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Прочитала", callback_data="q_read"),
         InlineKeyboardButton(text="⏳ В плани", callback_data="q_wish")]
    ])
    await m.answer("Оберіть статус:", reply_markup=kb)

@dp.callback_query(F.data.startswith("q_"))
async def quick_status(c: CallbackQuery, state: FSMContext):
    status = 'read' if c.data == "q_read" else 'wish'
    await state.update_data(quick_status=status)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Цього року", callback_data="qy_this"),
         InlineKeyboardButton(text="Інший рік", callback_data="qy_other")]
    ])
    await c.message.edit_text("Оберіть рік:", reply_markup=kb)

@dp.callback_query(F.data.startswith("qy_"))
async def quick_year(c: CallbackQuery, state: FSMContext):
    if c.data == "qy_this":
        await state.update_data(quick_year=datetime.now().year)
        await c.message.edit_text("✅ Тепер просто перешліть файл книги - я сам все збережу!")
        await state.set_state(LibS.quick_year_state)
    else:
        await c.message.edit_text("Введіть рік (наприклад: 2020):")
        await state.set_state(LibS.quick_year_state)

@dp.message(LibS.quick_year_state)
async def quick_receive(m: Message, state: FSMContext):
    data = await state.get_data()
    
    # Якщо ще немає року - це введення року
    if 'quick_year' not in data:
        try:
            year = int(m.text.strip())
            if 1900 <= year <= datetime.now().year:
                await state.update_data(quick_year=year)
                await m.answer("✅ Рік збережено! Тепер перешліть файл книги:")
                return
            else:
                await m.answer(f"❌ Введіть рік 1900-{datetime.now().year}")
                return
        except:
            await m.answer("❌ Введіть число!")
            return
    
    # Якщо є рік і це файл - ЗБЕРІГАЄМО БЕЗ ЗАЙВИХ ПИТАНЬ!
    if m.document:
        file_id = m.document.file_id
        file_name = m.document.file_name or "Невідома назва"
        title = file_name.rsplit('.', 1)[0]
        author = "Невідомий автор"
        description = "Додано через швидке додавання"
        year = data.get('quick_year', datetime.now().year)
        
        if data.get('quick_status') == 'read':
            with sqlite3.connect('my_library.db') as conn:
                conn.execute('''INSERT INTO books (title, author, description, rating, file_id, status, date_added, date_read, read_year) 
                               VALUES (?,?,?,?,?,?,?,?,?)''',
                               (title, author, description, 0, file_id, 'read', 
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S'), year))
            await m.answer(f"✅ {title} додано до ПРОЧИТАНИХ!\n📅 Рік: {year}")
        else:
            with sqlite3.connect('my_library.db') as conn:
                conn.execute('''INSERT INTO books (title, author, description, rating, file_id, status, date_added) 
                               VALUES (?,?,?,?,?,?,?)''',
                               (title, author, description, 0, file_id, 'wish', 
                                datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            await m.answer(f"✨ {title} додано до ПЛАНІВ!")
        
        await state.clear()
    else:
        await m.answer("❌ Перешліть файл книги!")
@dp.callback_query(F.data.startswith("qr_"))
async def quick_rating(c: CallbackQuery, state: FSMContext):
    rating = c.data.split("_")[1]
    data = await state.get_data()
    year = data.get('quick_year', datetime.now().year)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('INSERT INTO books (title, author, description, rating, file_id, status, date_added, date_read, read_year) VALUES (?,?,?,?,?,?,?,?,?)',
                    (data['quick_title'], data['quick_author'], data['quick_desc'], rating,
                     data['quick_file_id'], 'read', now, now, year))
    await c.message.edit_text(f"✅ '{data['quick_title']}' додано з оцінкою {rating}/10 за {year} рік!")
    await state.clear()

# ========== ЗМІНА РОКУ ==========
@dp.callback_query(F.data.startswith("change_year_"))
async def change_year_start(c: CallbackQuery, state: FSMContext):
    book_id = c.data.split("_")[2]
    await state.update_data(book_id=book_id)
    await state.set_state(LibS.set_year_state)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2024", callback_data="year_2024"), InlineKeyboardButton(text="2025", callback_data="year_2025"), InlineKeyboardButton(text="2026", callback_data="year_2026")],
        [InlineKeyboardButton(text="Інший рік", callback_data="year_other")]
    ])
    await c.message.answer("Оберіть рік:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("year_"))
async def set_year(c: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if c.data == "year_other":
        await c.message.answer("Введіть рік:")
        return
    year = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        conn.execute("UPDATE books SET read_year = ? WHERE id = ?", (year, data['book_id']))
    await c.message.edit_text(f"✅ Рік змінено на {year}")
    await state.clear()

@dp.message(LibS.set_year_state)
async def set_year_manual(m: Message, state: FSMContext):
    try:
        year = int(m.text.strip())
        if 1900 <= year <= datetime.now().year:
            data = await state.get_data()
            with sqlite3.connect('my_library.db') as conn:
                conn.execute("UPDATE books SET read_year = ? WHERE id = ?", (year, data['book_id']))
            await m.answer(f"✅ Рік змінено на {year}")
            await state.clear()
        else:
            await m.answer(f"❌ Рік 1900-{datetime.now().year}")
    except:
        await m.answer("❌ Введіть число!")

# ========== СТАТИСТИКА ==========
@dp.message(F.text == "📊 Статистика")
async def show_stats(m: Message):
    with sqlite3.connect('my_library.db') as conn:
        total_read = conn.execute('SELECT COUNT(*) FROM books WHERE status = "read"').fetchone()[0]
        total_wish = conn.execute('SELECT COUNT(*) FROM books WHERE status = "wish"').fetchone()[0]
        avg = conn.execute('SELECT AVG(rating) FROM books WHERE status = "read" AND rating > 0').fetchone()[0] or 0
        rereads = conn.execute('SELECT SUM(reread_count) FROM books WHERE status = "read"').fetchone()[0] or 0
        year_read = conn.execute('SELECT COUNT(*) FROM books WHERE status = "read" AND read_year = ?', (datetime.now().year,)).fetchone()[0]
        top = conn.execute('SELECT title, rating FROM books WHERE status = "read" AND rating > 0 ORDER BY rating DESC LIMIT 5').fetchall()
        text = f"📊 **СТАТИСТИКА**\n\n📚 Прочитано: {total_read}\n📌 В планах: {total_wish}\n⭐ Сер. рейтинг: {avg:.1f}/10\n🔄 Перечитань: {rereads}\n📅 За {datetime.now().year}: {year_read} книг\n\n⭐ **Топ-5:**\n" + "\n".join([f"{i+1}. {b[0]} - {b[1]}/10" for i,b in enumerate(top)]) if top else "Немає оцінок"
    await m.answer(text, parse_mode="Markdown")

# ========== ЗВІТ ЗА РІК ==========
@dp.message(F.text == "📅 Звіт за рік")
async def yearly_report(m: Message):
    with sqlite3.connect('my_library.db') as conn:
        years = conn.execute('SELECT DISTINCT read_year FROM books WHERE status = "read" AND read_year IS NOT NULL ORDER BY read_year DESC').fetchall()
    if not years:
        await m.answer("Немає даних")
        return
    buttons = [[InlineKeyboardButton(text=str(y[0]), callback_data=f"report_{y[0]}")] for y in years]
    await m.answer("Оберіть рік:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("report_"))
async def show_report(c: CallbackQuery):
    year = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        books = conn.execute('SELECT title, author, rating, reread_count FROM books WHERE status = "read" AND read_year = ? ORDER BY rating DESC', (year,)).fetchall()
    if not books:
        await c.message.answer(f"За {year} немає книг")
        return
    text = f"📚 **ЗВІТ ЗА {year}**\n\n📖 Всього: {len(books)}\n⭐ Сер. рейтинг: {sum(b[2] for b in books)/len(books):.1f}/10\n\n📖 Список:\n" + "\n".join([f"{i+1}. {b[0]} - {b[1]} (⭐{b[2]}/10)" + (f" 🔄{b[3]}" if b[3] else "") for i,b in enumerate(books)])
    await c.message.answer(text[:4000], parse_mode="Markdown")

# ========== ПОКАЗ КНИГ ==========
@dp.message(F.text.in_(["📚 Прочитане", "📝 Хочу прочитати"]))
async def show(m: Message):
    st = 'read' if "Прочитане" in m.text else 'wish'
    with sqlite3.connect('my_library.db') as conn:
        books = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE status = ?', (st,)).fetchall()
    if not books:
        return await m.answer("Порожньо.")
    for book in books:
        b_id, t, a, d, r, f_id, st, da, dr, rr, ry = book[:11]
        cap = f"📖 {t}\n👤 {a}\n📝 {d}\n"
        if st == 'read':
            cap += f"📊 ⭐ {r}/10\n"
            if ry: cap += f"📅 Прочитано: {ry} рік\n"
        else:
            cap += f"📌 В планах\n"
        btns = []
        if st == 'wish':
            btns.append([InlineKeyboardButton(text="✅ Вже прочитала", callback_data=f"finish_{b_id}")])
        btns.append([InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"menu_{b_id}"), InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_{b_id}")])
        try:
            await bot.send_document(m.chat.id, f_id, caption=cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        except:
            await m.answer(cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

# ========== ПОШУК ==========
@dp.message(F.text == "🔍 Пошук")
async def search_start(m: Message, state: FSMContext):
    await state.set_state(LibS.search_state)
    await m.answer("Введіть назву або автора:")

@dp.message(LibS.search_state)
async def search_logic(m: Message, state: FSMContext):
    if m.text in ["➕ Додати книгу", "⚡ Швидке додавання", "📚 Прочитане", "📝 Хочу прочитати", "🔍 Пошук", "📊 Статистика", "📅 Звіт за рік"]:
        await state.clear()
        return
    q = f"%{m.text.lower()}%"
    with sqlite3.connect('my_library.db') as conn:
        books = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE LOWER(title) LIKE ? OR LOWER(author) LIKE ?', (q, q)).fetchall()
    if not books:
        await m.answer("Нічого не знайдено")
        await state.clear()
        return
    await m.answer(f"🔍 Знайдено {len(books)} книг:")
    for book in books:
        b_id, t, a, d, r, f_id, st, da, dr, rr, ry = book[:11]
        cap = f"📖 {t}\n👤 {a}\n📝 {d}\n"
        if st == 'read':
            cap += f"📊 ⭐ {r}/10\n"
            if ry: cap += f"📅 Прочитано: {ry} рік\n"
        else:
            cap += f"📌 В планах\n"
        btns = []
        if st == 'wish':
            btns.append([InlineKeyboardButton(text="✅ Вже прочитала", callback_data=f"finish_{b_id}")])
        btns.append([InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"menu_{b_id}"), InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_{b_id}")])
        try:
            await bot.send_document(m.chat.id, f_id, caption=cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
        except:
            await m.answer(cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
    await state.clear()

# ========== ПЕРЕЧИТУВАННЯ ==========
@dp.callback_query(F.data.startswith("reread_"))
async def reread_book(c: CallbackQuery):
    book_id = c.data.split("_")[1]
    year = datetime.now().year
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('UPDATE books SET reread_count = reread_count + 1, read_year = ? WHERE id = ?', (year, book_id))
        title = conn.execute('SELECT title FROM books WHERE id = ?', (book_id,)).fetchone()[0]
    await c.message.answer(f"🔄 '{title}' перечитано за {year} рік!")
    await c.answer()

# ========== ПОКРОКОВЕ ДОДАВАННЯ ==========
@dp.message(F.text == "➕ Додати книгу")
async def add(m: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Прочитала", callback_data="s_read"), InlineKeyboardButton(text="⏳ В плани", callback_data="s_wish")]])
    await m.answer("Статус?", reply_markup=kb)

@dp.callback_query(F.data.startswith("s_"))
async def set_s(c: CallbackQuery, state: FSMContext):
    await state.update_data(st='read' if c.data == "s_read" else 'wish')
    await state.set_state(LibS.f)
    await c.message.edit_text("Надішли файл книги:")

@dp.message(LibS.f, F.document)
async def p_f(m: Message, state: FSMContext):
    await state.update_data(fid=m.document.file_id)
    await state.set_state(LibS.t)
    await m.answer("Назва книги:")

@dp.message(LibS.t)
async def p_t(m: Message, state: FSMContext):
    await state.update_data(t=m.text.strip())
    await state.set_state(LibS.a)
    await m.answer("Автор:")

@dp.message(LibS.a)
async def p_a(m: Message, state: FSMContext):
    await state.update_data(a=m.text.strip())
    await state.set_state(LibS.d)
    await m.answer("Опис:")

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
        await m.answer("✨ Додано в плани!")
        await state.clear()

@dp.callback_query(F.data.startswith("r_"))
async def p_r(c: CallbackQuery, state: FSMContext):
    rating = c.data.split("_")[1]
    data = await state.get_data()
    year = datetime.now().year
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('INSERT INTO books (title, author, description, rating, file_id, status, date_added, date_read, read_year) VALUES (?,?,?,?,?,?,?,?,?)', (data['t'], data['a'], data['d'], rating, data['fid'], 'read', now, now, year))
    await c.message.edit_text(f"✅ Збережено з оцінкою {rating}/10 за {year} рік!")
    await state.clear()

# ========== ЗАВЕРШЕННЯ З ПЛАНІВ ==========
@dp.callback_query(F.data.startswith("finish_"))
async def finish(c: CallbackQuery, state: FSMContext):
    await state.update_data(eid=c.data.split("_")[1])
    await state.set_state(LibS.r)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=str(i), callback_data=f"moverat_{i}") for i in range(1, 6)], [InlineKeyboardButton(text=str(i), callback_data=f"moverat_{i}") for i in range(6, 11)]])
    await c.message.answer("Оцінка 1-10:", reply_markup=kb)

@dp.callback_query(F.data.startswith("moverat_"))
async def save_move(c: CallbackQuery, state: FSMContext):
    rating = c.data.split("_")[1]
    data = await state.get_data()
    year = datetime.now().year
    with sqlite3.connect('my_library.db') as conn:
        conn.execute('UPDATE books SET status = "read", rating = ?, read_year = ? WHERE id = ?', (rating, year, data['eid']))
    await c.message.edit_text(f"🎊 Перенесено з оцінкою {rating}/10 за {year} рік!")
    await state.clear()

# ========== РЕДАГУВАННЯ ==========
@dp.callback_query(F.data.startswith("menu_"))
async def edit_m(c: CallbackQuery):
    b_id = c.data.split("_")[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назву", callback_data=f"ed_title_{b_id}"), InlineKeyboardButton(text="Автора", callback_data=f"ed_author_{b_id}")],
        [InlineKeyboardButton(text="Опис", callback_data=f"ed_desc_{b_id}"), InlineKeyboardButton(text="Рейтинг", callback_data=f"ed_rating_{b_id}")],
        [InlineKeyboardButton(text="Рік", callback_data=f"ed_year_{b_id}"), InlineKeyboardButton(text="◀️ Назад", callback_data=f"back_{b_id}")]
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
        await c.message.answer("Введіть нове значення:" if f != "year" else "Введіть новий рік:")
        await c.answer()

@dp.message(LibS.edit_val)
async def ed_sv(m: Message, state: FSMContext):
    data = await state.get_data()
    fields = {"title":"title","author":"author","desc":"description","rating":"rating","year":"read_year"}
    if data['fld'] == 'rating':
        try:
            v = int(m.text.strip())
            if not 1<=v<=10:
                await m.answer("Рейтинг 1-10!")
                return
        except:
            await m.answer("Введіть число!")
            return
    elif data['fld'] == 'year':
        try:
            v = int(m.text.strip())
            if not 1900<=v<=datetime.now().year:
                await m.answer(f"Рік 1900-{datetime.now().year}!")
                return
        except:
            await m.answer("Введіть число!")
            return
    else:
        v = m.text.strip()
    with sqlite3.connect('my_library.db') as conn:
        conn.execute(f"UPDATE books SET {fields[data['fld']]} = ? WHERE id = ?", (v, data['eid']))
    await m.answer("✅ Оновлено!")
    await state.clear()

@dp.callback_query(F.data.startswith("back_"))
async def back_to_book(c: CallbackQuery):
    b_id = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        book = conn.execute('SELECT id, title, author, description, rating, file_id, status, date_added, date_read, reread_count, read_year FROM books WHERE id = ?', (b_id,)).fetchone()
        if book:
            b_id, t, a, d, r, f_id, st, da, dr, rr, ry = book[:11]
            cap = f"📖 {t}\n👤 {a}\n📝 {d}\n"
            if st == 'read':
                cap += f"📊 ⭐ {r}/10\n"
                if ry: cap += f"📅 Прочитано: {ry} рік\n"
            else:
                cap += f"📌 В планах\n"
            btns = []
            if st == 'wish':
                btns.append([InlineKeyboardButton(text="✅ Вже прочитала", callback_data=f"finish_{b_id}")])
            btns.append([InlineKeyboardButton(text="✏️ Редагувати", callback_data=f"menu_{b_id}"), InlineKeyboardButton(text="🗑 Видалити", callback_data=f"del_{b_id}")])
            try:
                await bot.send_document(c.message.chat.id, f_id, caption=cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))
            except:
                await c.message.answer(cap, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("del_"))
async def delete(c: CallbackQuery):
    b_id = c.data.split("_")[1]
    with sqlite3.connect('my_library.db') as conn:
        conn.execute("DELETE FROM reading_history WHERE book_id = ?", (b_id,))
        conn.execute("DELETE FROM books WHERE id = ?", (b_id,))
    await c.message.delete()
    await c.answer("Видалено!")

# ========== ГОЛОВНЕ МЕНЮ ==========
@dp.message(Command("start"))
async def start(m: Message):
    init_db()
    kb = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="➕ Додати книгу"), types.KeyboardButton(text="⚡ Швидке додавання")],
        [types.KeyboardButton(text="📚 Прочитане"), types.KeyboardButton(text="📝 Хочу прочитати")],
        [types.KeyboardButton(text="🔍 Пошук"), types.KeyboardButton(text="📊 Статистика")],
        [types.KeyboardButton(text="📅 Звіт за рік")]
    ], resize_keyboard=True)
    await m.answer("📚 Твоя бібліотека!\n➕ Додати книгу - покроково\n⚡ Швидке додавання - просто перешли файл!", reply_markup=kb)

# ========== ЗАПУСК ==========
async def main():
    init_db()
    print("Бот запущений!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
