import os
import json
import random
import time
import requests
from flask import Flask
from threading import Thread
from collections import deque
from telegram import Update, ChatAction
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

# Keep‑alive Flask
app = Flask(__name__)
@app.route('/')
def home(): return "Kaoruko is here~ 💗"
def run_flask(): app.run(host="0.0.0.0", port=8080)
def keep_alive(): Thread(target=run_flask, daemon=True).start()

# Config
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "gpt-4o-mini"
MEMORY_FILE = "memory.json"
STATE_FILE = "last_seen.json"
SELFIE_FOLDER = "selfies"

# Initialize memory files
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f: json.dump({}, f)
if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as f: json.dump({"start_time": time.time()}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f: return json.load(f)
def save_memory(data):
    with open(MEMORY_FILE, "w") as f: json.dump(data, f)

with open(STATE_FILE, "r") as f:
    START_TIME = json.load(f).get("start_time", time.time())

def get_user_key(update):
    return update.effective_user.username and f"@{update.effective_user.username}" or str(update.effective_user.id)

def ask_openrouter(prompt, memory_context):
    system_prompt = (
        "You are Kaoruko Waguri — a sweet, polite, shy anime girl. "
        "You talk softly in Hinglish or English depending on the user, never robotic. "
        "Keep replies short (under 30 words), emotional, and realistic like WhatsApp style. "
        "Use gentle emojis like 💗, 🌸, 🥺, ~ when needed."
    )
    msgs = [{"role":"system","content":system_prompt}]
    for m in memory_context[-10:]:
        msgs += [{"role":"user","content":m["user"]},
                 {"role":"assistant","content":m["bot"]}]
    msgs.append({"role":"user","content":prompt})

    headers = {"Authorization":f"Bearer {OPENROUTER_API_KEY}"}
    payload = {"model":MODEL,"messages":msgs,"max_tokens":100,"temperature":1.2}
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                          json=payload,headers=headers)
        return r.json()["choices"][0]["message"]["content"]
    except:
        return "Kaoruko got confused... 🥺"

def handle_message(update: Update, context: CallbackContext):
    if update.message.date.timestamp() < START_TIME: return
    txt = update.message.text or ""
    msg = txt.lower().strip()
    key = get_user_key(update)
    mem = load_memory()
    user_mem = mem.setdefault(key, {"history":[]})
    context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    in_group = update.message.chat.type != "private"
    replied = update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.get_me().id
    mentioned = any(n in msg for n in ["kaoruko","kaoru","waguri kaoruko"])
    if in_group and not (mentioned or replied): return

    if any(k in msg for k in ["pic","selfie","image"]):
        pics = os.listdir(SELFIE_FOLDER)
        if pics:
            path = os.path.join(SELFIE_FOLDER, random.choice(pics))
            update.message.reply_photo(photo=open(path,"rb"))
            return

    resp = ask_openrouter(txt, user_mem["history"])
    user_mem["history"].append({"user":txt,"bot":resp})
    user_mem["history"] = user_mem["history"][-10:]
    save_memory(mem)

    time.sleep(random.uniform(0.7,1.2))
    update.message.reply_text(resp if len(resp)<300 else resp[:290]+"...")

if __name__ == "__main__":
    with open(STATE_FILE,"w") as f: json.dump({"start_time":time.time()},f)
    keep_alive()
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    updater.start_polling()
    updater.idle()
import sys
print("Running Python version:", sys.version)
