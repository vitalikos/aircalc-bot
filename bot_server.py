import json
import logging
from datetime import datetime
from flask import Flask, request
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Хранилище статистики
statistics = {
    'total_opens': 0,
    'total_calculations': 0,
    'total_shares': 0,
    'calculations': [],
    'users': {}
}

# ВАЖНО: Замените на реальные значения!
TOKEN = "YOUR_BOT_TOKEN"
SECRET_PASSWORD = "YOUR_SECRET_PASSWORD"

@app.route('/webapp', methods=['POST'])
def handle_web_app_data():
    """Получение данных из Web App"""
    try:
        data = request.json
        
        event = data.get('event')
        user_id = data.get('userId')
        username = data.get('username')
        timestamp = data.get('timestamp')
        event_data = data.get('data', {})
        
        # Добавляем пользователя
        if user_id not in statistics['users']:
            statistics['users'][user_id] = {
                'username': username,
                'first_seen': timestamp,
                'events_count': 0
            }
        
        statistics['users'][user_id]['events_count'] += 1
        
        # Обрабатываем события
        if event == 'aircalc_opened':
            statistics['total_opens'] += 1
            logger.info(f"🌊 Открытие: {username}")
        
        elif event == 'calculation_completed':
            statistics['total_calculations'] += 1
            calc_info = {
                'user_id': user_id,
                'username': username,
                'timestamp': timestamp,
                'area': event_data.get('area'),
                'power': event_data.get('result_power_kw')
            }
            statistics['calculations'].append(calc_info)
            logger.info(f"✅ Расчет: {username} | {event_data.get('result_power_kw')} кВт | {event_data.get('area')} м²")
        
        elif event == 'result_shared':
            statistics['total_shares'] += 1
            logger.info(f"📤 Поделился: {username}")
        
        # Логирование в файл
        with open('events.log', 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} | {event} | {username} ({user_id}) | {json.dumps(event_data, ensure_ascii=False)}\n")
        
        return {'status': 'ok'}, 200
    
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """REST API для получения статистики"""
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
    """Проверка здоровья сервера"""
    return {'status': 'ok', 'timestamp': datetime.now().isoformat()}

if __name__ == '__main__':
    app.run()
