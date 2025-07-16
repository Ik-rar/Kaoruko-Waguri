import os
import json
import random
import time
import requests
from flask import Flask
from threading import Thread
from collections import deque
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ------------------ FLASK KEEP-ALIVE ------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Kaoruko is here~ 💗"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()
# ------------------------------------------------------

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "gpt-4o-mini"

MEMORY_FILE = "memory.json"
STATE_FILE = "last_seen.json"
SELFIE_FOLDER = "selfies"

if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f:
        json.dump({}, f)

if not os.path.exists(STATE_FILE):
    with open(STATE_FILE, "w") as f:
        json.dump({"start_time": time.time()}, f)

def load_memory():
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f)

with open(STATE_FILE, "r") as f:
    START_TIME = json.load(f).get("start_time", time.time())

def get_user_key(update):
    return update.effective_user.username and f"@{update.effective_user.username}" or str(update.effective_user.id)

# GPT-4o-mini REPLY FUNCTION
def ask_openrouter(prompt, memory_context, username=""):
    system_prompt = (
        "You are Kaoruko Waguri — a sweet, polite, shy anime girl. "
        "You talk softly in Hinglish or English depending on the user, never robotic. "
        "Keep replies short (under 30 words), emotional, and realistic like WhatsApp style. "
        "Use gentle emojis like 💗, 🌸, 🥺, ~ when needed. Speak like a soft-spoken schoolgirl."
    )
    messages = [{"role": "system", "content": system_prompt}]
    for m in memory_context[-10:]:
        messages.append({"role": "user", "content": m["user"]})
        messages.append({"role": "assistant", "content": m["bot"]})
    messages.append({"role": "user", "content": prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "max_tokens": 100,
        "temperature": 1.2,
        "messages": messages
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("OpenRouter error:", e)
        return "Kaoruko got confused... 🥺"

# MAIN MESSAGE HANDLER
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_date = update.message.date.timestamp()
    if msg_date < START_TIME:
        return

    txt = update.message.text or ""
    msg = txt.lower().strip()
    key = get_user_key(update)
    memory = load_memory()
    user_mem = memory.setdefault(key, {})
    user_mem.setdefault("history", [])

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    in_group = update.message.chat.type != "private"
    replied = update.message.reply_to_message and (
        update.message.reply_to_message.from_user.id == context.bot.id
    )
    mentioned = any(name in msg for name in ["kaoruko", "kaoru", "waguri kaoruko"])

    if in_group and not (mentioned or replied):
        return

    if any(k in msg for k in ["pic", "selfie", "image"]):
        selfies = os.listdir(SELFIE_FOLDER)
        if selfies:
            img_path = os.path.join(SELFIE_FOLDER, random.choice(selfies))
            await update.message.reply_photo(photo=open(img_path, "rb"))
            return

    response = ask_openrouter(txt, user_mem["history"], username=key)
    user_mem["history"].append({"user": txt, "bot": response})
    user_mem["history"] = user_mem["history"][-10:]
    memory[key] = user_mem
    save_memory(memory)

    await asyncio.sleep(random.uniform(0.7, 1.2))
    await update.message.reply_text(response if len(response) < 300 else response[:290] + "...")

# RUNNING THE BOT
if __name__ == "__main__":
    import asyncio

    with open(STATE_FILE, "w") as f:
        json.dump({"start_time": time.time()}, f)

    keep_alive()
    app_telegram = ApplicationBuilder().token(TOKEN).build()
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app_telegram.run_polling()
