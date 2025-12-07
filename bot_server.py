import json
import logging
import re
from datetime import datetime
from flask import Flask, request
import os
from translations import get_text
import telebot
import requests
from telebot import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

statistics = {
    'total_opens': 0,
    'total_calculations': 0,
    'total_shares': 0,
    'calculations': [],
    'users': {}
}

TOKEN = "8392848867:AAFStBTp-LMRTZWeHPZQwbrLlW8XvVK0ANQ"          # сюда подставь токен (или возьми из os.getenv)
SECRET_PASSWORD = "YOUR_SECRET_PASSWORD"
bot = telebot.TeleBot(TOKEN)


@app.route('/')
def home():
    return {'status': 'Bot server is running'}, 200


@app.route('/webapp', methods=['GET', 'POST', 'HEAD'])
def handle_webapp():
    if request.method == 'GET':
        lang = request.args.get('lang', 'ru')

        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html = f.read()

            def replace_translation(match):
                key = match.group(1)
                return get_text(lang, key)

            html = re.sub(r'\{\{(\w+)\}\}', replace_translation, html)

            return html
        except Exception as e:
            return {'error': f'index.html not found: {str(e)}'}, 404

    if request.method == 'POST':
        try:
            data = request.json
            event_type = data.get('event')
            user_id = data.get('userId')
            username = data.get('username')
            timestamp = data.get('timestamp')
            event_data = data.get('data', {})

            if user_id not in statistics['users']:
                statistics['users'][user_id] = {
                    'username': username,
                    'first_seen': timestamp,
                    'events_count': 0
                }

            statistics['users'][user_id]['events_count'] += 1

            if event_type == 'aircalc_opened':
                statistics['total_opens'] += 1
                logger.info(f"🌊 Открытие: {username}")

            elif event_type == 'calculation_completed':
                statistics['total_calculations'] += 1
                calc_info = {
                    'user_id': user_id,
                    'username': username,
                    'timestamp': timestamp,
                    'area': event_data.get('area'),
                    'power': event_data.get('result_power_kw')
                }
                statistics['calculations'].append(calc_info)
                logger.info(
                    f"✅ Расчет: {username} | {event_data.get('result_power_kw')} кВт | {event_data.get('area')} м²"
                )

            elif event_type == 'result_shared':
                statistics['total_shares'] += 1
                logger.info(f"📤 Поделился: {username}")

            with open('aircalc_events.log', 'a', encoding='utf-8') as f:
                f.write(
                    f"{timestamp} | {event_type} | {username} ({user_id}) | "
                    f"{json.dumps(event_data, ensure_ascii=False)}\n"
                )

            return {'status': 'ok'}, 200

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return {'status': 'error', 'message': str(e)}, 400


@app.route('/stats', methods=['GET'])
def get_stats():
    password = request.args.get('password')

    if password != SECRET_PASSWORD:
        return {'error': 'Unauthorized'}, 401

    return {
        'timestamp': datetime.now().isoformat(),
        'total_opens': statistics['total_opens'],
        'total_calculations': statistics['total_calculations'],
        'total_shares': statistics['total_shares'],
        'unique_users': len(statistics['users']),
        'recent_calculations': statistics['calculations'][-10:]
    }


@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}


@bot.message_handler(commands=['stats'])
def send_stats(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        stats_response = requests.get(
            f'http://localhost:5000/stats?password={SECRET_PASSWORD}',
            timeout=5
        )

        if stats_response.status_code == 200:
            stats = stats_response.json()

            stats_text = f"""
📊 **СТАТИСТИКА AirCalc**

👥 Пользователей: {stats['unique_users']}
📱 Открытий: {stats['total_opens']}
🔢 Расчетов: {stats['total_calculations']}
📤 Поделиться: {stats['total_shares']}

⏰ Обновлено: {stats['timestamp']}

🔥 Последние расчеты:
"""

            recent_calcs = stats.get('recent_calculations', [])
            for calc in recent_calcs[:5]:
                area = calc.get('area', 'N/A')
                power = calc.get('power', 'N/A')
                time = calc.get('timestamp', 'N/A')[:16]
                stats_text += f"• {power} кВт ({area}м²) - {time}\n"

            bot.reply_to(message, stats_text, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Ошибка получения статистики", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Stats error for user {user_id}: {e}")
        bot.reply_to(message, "❌ Ошибка сервера статистики", parse_mode='Markdown')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("🚀 Flask + Bot запущены!")
    app.run(host='0.0.0.0', port=port, debug=False)
