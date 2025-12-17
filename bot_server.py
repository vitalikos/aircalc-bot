import json
import logging
import re
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from translations import get_text
import telebot
import requests
from telebot import types
import threading

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

# Получай токен из переменной окружения или используй напрямую
TOKEN = os.getenv('BOT_TOKEN', "8392848867:AAFStBTp-LMRTZWeHPZQwbrLlW8XvVK0ANQ")
SECRET_PASSWORD = os.getenv('SECRET_PASSWORD', "admin123")

bot = telebot.TeleBot(TOKEN)

# ============ FLASK МАРШРУТЫ ============

@app.route('/')
def home():
    """Возвращает HTML приложение (Web App)"""
    lang = request.args.get('lang', 'ru')
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()

        def replace_translation(match):
            key = match.group(1)
            return get_text(lang, key)

        html = re.sub(r'\{\{(\w+)\}\}', replace_translation, html)
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки HTML: {e}")
        return {'error': f'index.html not found: {str(e)}'}, 404

@app.route('/webapp', methods=['GET', 'POST', 'HEAD'])
def handle_webapp():
    """Альтернативный маршрут для Web App (обратная совместимость)"""
    if request.method == 'GET':
        lang = request.args.get('lang', 'ru')
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                html = f.read()

            def replace_translation(match):
                key = match.group(1)
                return get_text(lang, key)

            html = re.sub(r'\{\{(\w+)\}\}', replace_translation, html)
            return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
        except Exception as e:
            logger.error(f"❌ Ошибка в /webapp: {e}")
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

            # Логирование события в файл
            with open('aircalc_events.log', 'a', encoding='utf-8') as f:
                f.write(
                    f"{timestamp} | {event_type} | {username} ({user_id}) | "
                    f"{json.dumps(event_data, ensure_ascii=False)}\n"
                )

            return {'status': 'ok'}, 200
        except Exception as e:
            logger.error(f"❌ Ошибка обработки события: {e}")
            return {'status': 'error', 'message': str(e)}, 400

@app.route('/stats', methods=['GET'])
def get_stats():
    """Возвращает статистику (защищено паролем)"""
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
    """Проверка здоровья сервиса"""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}

# ============ БОТ КОМАНДЫ ============

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Команда /start - приветствие с кнопкой Web App"""
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Создаём кнопку Web App
    markup = types.InlineKeyboardMarkup()
    web_app_button = types.InlineKeyboardButton(
        text="📊 Открыть AirCalc",
        web_app=types.WebAppInfo(url="https://aircalc-bot.ru/")
    )
    markup.add(web_app_button)
    
    bot.send_message(
        user_id,
        "👋 Добро пожаловать в AirCalc Bot! 🌊\n\n"
        "Нажми кнопку ниже, чтобы открыть приложение:\n\n"
        "/stats - показать статистику",
        reply_markup=markup,
        parse_mode='Markdown'
    )
    logger.info(f"✅ Welcome sent to {username}")

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Команда /stats - показать статистику"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.first_name

        # Пытаемся получить статистику с HTTP-эндпоинта
        try:
            stats_response = requests.get(
                f'http://localhost:5000/stats?password={SECRET_PASSWORD}',
                timeout=5
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить статистику с сервера: {e}")
            stats_response = None

        if stats_response is not None and stats_response.status_code == 200:
            stats = stats_response.json()
        else:
            # Fallback: используем данные из памяти
            stats = {
                'timestamp': datetime.now().isoformat(),
                'total_opens': statistics['total_opens'],
                'total_calculations': statistics['total_calculations'],
                'total_shares': statistics['total_shares'],
                'unique_users': len(statistics['users']),
                'recent_calculations': statistics['calculations'][-10:]
            }

        stats_text = f"""📊 **СТАТИСТИКА AirCalc**

👥 Пользователей: {stats['unique_users']}
📱 Открытий: {stats['total_opens']}
🔢 Расчетов: {stats['total_calculations']}
📤 Поделились: {stats['total_shares']}
⏰ Обновлено: {stats['timestamp']}

🔥 Последние расчеты:
"""

        recent_calcs = stats.get('recent_calculations', [])
        if recent_calcs:
            for calc in recent_calcs[:5]:
                area = calc.get('area', 'N/A')
                power = calc.get('power', 'N/A')
                time = calc.get('timestamp', 'N/A')[:16]
                stats_text += f"• {power} кВт ({area}м²) - {time}\n"
        else:
            stats_text += "• Нет данных\n"

        bot.reply_to(message, stats_text, parse_mode='Markdown')
        logger.info(f"✅ Stats sent to {username}")

    except Exception as e:
        logger.error(f"❌ Stats error for user {user_id}: {e}")
        bot.reply_to(message, f"❌ Ошибка сервера статистики: {str(e)}", parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Обработчик неизвестных команд"""
    bot.reply_to(
        message,
        "🤔 Команда не найдена. Напиши /stats для статистики",
        parse_mode='Markdown'
    )

# ============ ЗАПУСК БОТА В ОТДЕЛЬНОМ ПОТОКЕ ============

def run_bot():
    logger.info("🤖 Бот запущен (polling)...")
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")

if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("🚀 Bot thread started")

    # Запускаем Flask
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Flask запущен на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
