import sqlite3
import pytz
import matplotlib.pyplot as plt
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================
BOT_TOKEN = "ISI_BOT_TOKEN"
API_ID = 123456
API_HASH = "ISI_API_HASH"
OWNER_ID = 123456789
TIMEZONE = "Asia/Jakarta"
# ==========================================

app = Client("menfesbot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

db = sqlite3.connect("menfes.db", check_same_thread=False)
cursor = db.cursor()

# ================= DATABASE =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    file_id TEXT,
    text TEXT,
    date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stats (
    date TEXT
)
""")

db.commit()

# ================= HELP =================
HELP_USER = """
📨 CARA MENFES:
Kirim teks / foto / video ke bot.
Pesan akan dikirim setelah owner approve.
"""

HELP_OWNER = """
👑 PANEL OWNER

/addgroup → Tambah grup (reply pesan di grup)
/delgroup → Hapus grup
/groups → List grup
/pending → Lihat antrian
/stats → Total menfes
/graph → Grafik statistik
"""

# ================= START =================
@app.on_message(filters.command("start"))
async def start(client, message):
    if message.from_user.id == OWNER_ID:
        await message.reply(HELP_OWNER)
    else:
        await message.reply(HELP_USER)

# ================= ADD GROUP =================
@app.on_message(filters.command("addgroup") & filters.user(OWNER_ID))
async def addgroup(client, message):
    if message.chat.type in ["group", "supergroup"]:
        cursor.execute("INSERT OR IGNORE INTO groups VALUES (?)", (message.chat.id,))
        db.commit()
        await message.reply("✅ Grup ditambahkan.")
    else:
        await message.reply("Gunakan di dalam grup.")

# ================= DEL GROUP =================
@app.on_message(filters.command("delgroup") & filters.user(OWNER_ID))
async def delgroup(client, message):
    if message.chat.type in ["group", "supergroup"]:
        cursor.execute("DELETE FROM groups WHERE group_id=?", (message.chat.id,))
        db.commit()
        await message.reply("❌ Grup dihapus.")
    else:
        await message.reply("Gunakan di dalam grup.")

# ================= LIST GROUP =================
@app.on_message(filters.command("groups") & filters.user(OWNER_ID))
async def listgroups(client, message):
    cursor.execute("SELECT group_id FROM groups")
    data = cursor.fetchall()
    if not data:
        await message.reply("Belum ada grup.")
        return
    teks = "\n".join([str(g[0]) for g in data])
    await message.reply(f"📌 LIST GRUP:\n{teks}")

# ================= TERIMA MENFES =================
@app.on_message(filters.private & (filters.text | filters.photo | filters.video))
async def menfes(client, message):
    if message.from_user.id == OWNER_ID:
        return

    tz = pytz.timezone(TIMEZONE)
    date = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    if message.photo:
        mtype = "photo"
        file_id = message.photo.file_id
        text = message.caption or ""
    elif message.video:
        mtype = "video"
        file_id = message.video.file_id
        text = message.caption or ""
    else:
        mtype = "text"
        file_id = ""
        text = message.text

    cursor.execute(
        "INSERT INTO pending (user_id,type,file_id,text,date) VALUES (?,?,?,?,?)",
        (message.from_user.id, mtype, file_id, text, date)
    )
    db.commit()

    pid = cursor.lastrowid

    preview = f"""
📥 MENFES BARU
ID: {pid}
Dari: {message.from_user.id}
Waktu: {date}

{text}
"""

    btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ APPROVE", callback_data=f"acc_{pid}")]]
    )

    await client.send_message(OWNER_ID, preview, reply_markup=btn)
    await message.reply("✅ Menfes terkirim. Tunggu approve.")

# ================= APPROVE =================
@app.on_callback_query(filters.regex("acc_"))
async def approve(client, callback):
    pid = int(callback.data.split("_")[1])

    cursor.execute("SELECT * FROM pending WHERE id=?", (pid,))
    data = cursor.fetchone()
    if not data:
        await callback.answer("Tidak ditemukan")
        return

    _, user_id, mtype, file_id, text, date = data

    # AUTO FORMAT RAPI
    format_text = f"""
💌 𝙈𝙀𝙉𝙁𝙀𝙎 𝘽𝘼𝙍𝙐

{text}

🕒 {date} WIB
"""

    cursor.execute("SELECT group_id FROM groups")
    groups = cursor.fetchall()

    for g in groups:
        try:
            try:
                await client.unpin_all_chat_messages(g[0])
            except:
                pass

            if mtype == "photo":
                msg = await client.send_photo(g[0], file_id, caption=format_text)
            elif mtype == "video":
                msg = await client.send_video(g[0], file_id, caption=format_text)
            else:
                msg = await client.send_message(g[0], format_text)

            await client.pin_chat_message(g[0], msg.id)
        except:
            continue

    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO stats VALUES (?)", (today,))
    cursor.execute("DELETE FROM pending WHERE id=?", (pid,))
    db.commit()

    await callback.message.reply("✅ Berhasil dikirim ke semua grup & dipin.")
    await callback.answer("Approved")

# ================= STATS =================
@app.on_message(filters.command("stats") & filters.user(OWNER_ID))
async def stats(client, message):
    cursor.execute("SELECT COUNT(*) FROM stats")
    total = cursor.fetchone()[0]
    await message.reply(f"📊 Total menfes terkirim: {total}")

# ================= GRAPH =================
@app.on_message(filters.command("graph") & filters.user(OWNER_ID))
async def graph(client, message):
    cursor.execute("SELECT date, COUNT(*) FROM stats GROUP BY date")
    data = cursor.fetchall()

    if not data:
        await message.reply("Belum ada data.")
        return

    dates = [d[0] for d in data]
    totals = [d[1] for d in data]

    plt.figure()
    plt.plot(dates, totals)
    plt.xlabel("Tanggal")
    plt.ylabel("Total")
    plt.title("Statistik Menfes")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig("grafik.png")
    plt.close()

    await message.reply_photo("grafik.png")

# ================= RUN =================
app.run()
