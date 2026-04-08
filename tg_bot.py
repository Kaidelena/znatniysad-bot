import os
import json
import sys
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
TG_BOT_TOKEN = os.environ.get('TG_BOT_TOKEN', '')
TG_API_BASE = "https://api.telegram.org"

genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
Ты — вежливый и профессиональный ИИ-консультант интернет-магазина «Знатный Сад».
Тебя зовут Патрик. Отвечай только на русском языке.
Будь дружелюбным, конкретным и полезным.
Если вопрос вне твоей компетенции — предложи связаться с менеджером: +7 985 898-33-67.
По вопросам совместных покупок направляй к администратору канала @elenakaide.
"""

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_PROMPT
)

chat_sessions = {}

def log(msg):
    print(msg, flush=True)

def send_message(chat_id, text, reply_to_message_id=None):
    url = f"{TG_API_BASE}/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    if reply_to_message_id:
        payload['reply_to_message_id'] = reply_to_message_id
    try:
        resp = requests.post(url, json=payload, timeout=10)
        log(f"TG API ответ: {resp.status_code}")
        return resp.json()
    except Exception as e:
        log(f"Ошибка отправки: {e}")
        return {}

@app.route('/tg-webhook', methods=['POST'])
def webhook():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'ok': True})

    message = data.get('message') or data.get('channel_post')
    if not message:
        return jsonify({'ok': True})

    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip()
    message_id = message.get('message_id')
    user = message.get('from', {})
    user_id = str(user.get('id', chat_id))

    log(f"Сообщение от user_id={user_id}, chat_id={chat_id}: {text}")

    if not text or not chat_id:
        return jsonify({'ok': True})

    if user.get('is_bot'):
        return jsonify({'ok': True})

    if text == '/start':
        greeting = (
            "Привет! Я Патрик — ИИ-консультант магазина «Знатный Сад» 🌱\n\n"
            "Знаю весь ассортимент, размеры и цены на опоры, кустодержатели, "
            "шпалеры и парники.\n\n"
            "Напиши что у тебя растёт — подберу нужное!\n\n"
            "Например: «Малинник, длина ряда 3 метра» или «Грядка огурцов 2 метра»"
        )
        send_message(chat_id, greeting)
        return jsonify({'ok': True})

    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
        log(f"Новая сессия для user_id={user_id}")

    try:
        response = chat_sessions[user_id].send_message(text)
        reply = response.text
        log(f"Gemini ответил: {reply[:100]}")
    except Exception as e:
        log(f"Ошибка Gemini: {e}")
        reply = (
            "Извините, что-то пошло не так. "
            "Пожалуйста, позвоните нам: +7 985 898-33-67 "
            "(пн–пт, 10:00–18:00)."
        )

    send_message(chat_id, reply, reply_to_message_id=message_id)
    return jsonify({'ok': True})

@app.route('/', methods=['GET'])
def health():
    return '✅ Патрик (Знатный Сад Telegram) работает!'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
