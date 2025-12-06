import json
import logging
from datetime import datetime
from flask import Flask, request
import os

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

TOKEN = "YOUR_BOT_TOKEN"
SECRET_PASSWORD = "YOUR_SECRET_PASSWORD"

@app.route('/')
def home():
    return {'status': 'Bot server is running'}, 200
    @app.route('/webapp', methods=['GET', 'POST', 'HEAD'])
def handle_webapp():

    if request.method == 'GET':
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return {'error': 'index.html not found'}, 404
    
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
                logger.info(f"✅ Расчет: {username} | {event_data.get('result_power_kw')} кВт | {event_data.get('area')} м²")
            
            elif event_type == 'result_shared':
                statistics['total_shares'] += 1
                logger.info(f"📤 Поделился: {username}")
            
            with open('aircalc_events.log', 'a', encoding='utf-8') as f:
                f.write(f"{timestamp} | {event_type} | {username} ({user_id}) | {json.dumps(event_data, ensure_ascii=False)}\n")
            
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

