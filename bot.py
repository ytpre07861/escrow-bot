import sqlite3
from telebot import TeleBot, types
import threading
from flask import Flask

# --- FLASK SERVER FOR CLOUD KEEP-ALIVE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# --- CONFIGURATION ---
BOT_TOKEN = "YAHAN_APNA_BOT_TOKEN_DALO"
ALLOWED_USERS = [6846649100, 8325196902]  

bot = TeleBot(BOT_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("digilocker.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_name TEXT UNIQUE,
            doc_value TEXT,
            file_type TEXT DEFAULT 'text'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            addr_name TEXT UNIQUE,
            addr_value TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def is_owner(message):
    return message.from_user.id in ALLOWED_USERS

def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📄 View Docs"),
        types.KeyboardButton("➕ Add Doc"),
        types.KeyboardButton("🏠 View Addresses"),
        types.KeyboardButton("➕ Add Address"),
        types.KeyboardButton("❌ Delete Item")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_owner(message):
        bot.reply_to(message, "❌ Access Denied!")
        return
    bot.send_message(message.chat.id, "👋 Welcome to your Advance DigiLocker!", reply_markup=main_menu())

# --- VIEW LOGIC ---
@bot.message_handler(func=lambda msg: msg.text in ["📄 View Docs", "🏠 View Addresses"] and is_owner(msg))
def view_data(message):
    table = "documents" if "Docs" in message.text else "addresses"
    conn = sqlite3.connect("digilocker.db")
    cursor = conn.cursor()
    if table == "documents":
        cursor.execute("SELECT doc_name, doc_value, file_type FROM documents")
        rows = cursor.fetchall()
    else:
        cursor.execute("SELECT addr_name, addr_value FROM addresses")
        rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.reply_to(message, "Nahi mila! Abhi tak koi data saved nahi hai.")
        return
        
    if table == "addresses":
        response = "🏠 <b>Saved Addresses:</b>\n\n"
        for name, value in rows:
            response += f"📍 <b>{name}:</b> <code>{value}</code>\n"
        bot.send_message(message.chat.id, response, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "📄 <b>Aapke Saved Documents:</b>")
        for name, value, f_type in rows:
            if f_type == "text":
                bot.send_message(message.chat.id, f"🔑 <b>{name}:</b> <code>{value}</code>", parse_mode="HTML")
            elif f_type == "photo":
                bot.send_photo(message.chat.id, value, caption=f"🖼️ <b>{name}</b>", parse_mode="HTML")
            elif f_type == "document":
                bot.send_document(message.chat.id, value, caption=f"📁 <b>{name}</b>", parse_mode="HTML")

# --- ADD LOGIC ---
@bot.message_handler(func=lambda msg: msg.text in ["➕ Add Doc", "➕ Add Address"] and is_owner(msg))
def ask_name(message):
    target = "doc" if "Doc" in message.text else "address"
    msg_text = "📑 Document ka naam dalein:" if target == "doc" else "📍 Address ka short name dalein:"
    sent_msg = bot.reply_to(message, msg_text, reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(sent_msg, process_name, target)

def process_name(message, target):
    name = message.text.strip()
    msg_text = f"✍️ Ab {name} ki details/photo/file bhejiye:" if target == "doc" else f"✍️ Ab {name} ka full address likhiye:"
    sent_msg = bot.send_message(message.chat.id, msg_text, parse_mode="HTML")
    bot.register_next_step_handler(sent_msg, save_data, target, name)

def save_data(message, target, name):
    table = "documents" if target == "doc" else "addresses"
    if target == "address":
        if message.content_type != 'text':
            bot.send_message(message.chat.id, "❌ Address sirf text me hona chahiye!", reply_markup=main_menu())
            return
        value = message.text.strip()
        f_type = "text"
    else:
        if message.content_type == 'text':
            value = message.text.strip()
            f_type = "text"
        elif message.content_type == 'photo':
            value = message.photo[-1].file_id
            f_type = "photo"
        elif message.content_type == 'document':
            value = message.document.file_id
            f_type = "document"
        else:
            bot.send_message(message.chat.id, "❌ Unsupported format!", reply_markup=main_menu())
            return

    try:
        conn = sqlite3.connect("digilocker.db")
        cursor = conn.cursor()
        if table == "documents":
            cursor.execute("INSERT OR REPLACE INTO documents (doc_name, doc_value, file_type) VALUES (?, ?, ?)", (name, value, f_type))
        else:
            cursor.execute("INSERT OR REPLACE INTO addresses (addr_name, addr_value) VALUES (?, ?)", (name, value))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ '{name}' successfully save ho gaya!", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}", reply_markup=main_menu())

# --- DELETE LOGIC ---
@bot.message_handler(func=lambda msg: msg.text == "❌ Delete Item" and is_owner(msg))
def ask_delete(message):
    sent_msg = bot.reply_to(message, "Delete karne ke liye item ka exact naam bhejiye:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(sent_msg, process_delete)

def process_delete(message):
    name = message.text.strip()
    conn = sqlite3.connect("digilocker.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE doc_name = ?", (name,))
    docs_deleted = cursor.rowcount
    cursor.execute("DELETE FROM addresses WHERE addr_name = ?", (name,))
    addrs_deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if docs_deleted > 0 or addrs_deleted > 0:
        bot.send_message(message.chat.id, f"🗑️ '{name}' delete ho gaya.", reply_markup=main_menu())
    else:
        bot.send_message(message.chat.id, f"❌ '{name}' nahi mila.", reply_markup=main_menu())

if __name__ == "__main__":
    # Start Flask Web Server in background thread
    threading.Thread(target=run_flask).start()
    print("🤖 Your Advance DigiLocker Bot is Running 24/7...")
    bot.infinity_polling()
