"""
Веб-интерфейс для системы управления на ПК1
"""
from flask import Flask, render_template, jsonify, send_file, request
import os
import json
from datetime import datetime
import threading

# Конфигурация
BASE_STORAGE = "./storage"
TELEGRAM_STORAGE = f"{BASE_STORAGE}/telegram"
LOGS_PATH = f"{BASE_STORAGE}/logs"

# Создаем папки если их нет
os.makedirs(TELEGRAM_STORAGE, exist_ok=True)
os.makedirs(LOGS_PATH, exist_ok=True)

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

def log_web_event(message):
    """Логирование событий веб-интерфейса"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [WEB] {message}"
    
    # Сохраняем в файл
    log_file = f"{LOGS_PATH}/web_{datetime.now().strftime('%Y%m%d')}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

@app.route('/')
def index():
    """Главная страница"""
    log_web_event("Открыта главная страница")
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Получение статуса системы"""
    try:
        # Получаем список файлов
        files = []
        if os.path.exists(TELEGRAM_STORAGE):
            for file in os.listdir(TELEGRAM_STORAGE):
                filepath = os.path.join(TELEGRAM_STORAGE, file)
                if os.path.isfile(filepath):
                    files.append({
                        'name': file,
                        'size': os.path.getsize(filepath),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    })
        
        # Считаем статистику
        total_size = sum(f['size'] for f in files)
        
        status = {
            'status': 'running',
            'server_time': datetime.now().isoformat(),
            'telegram_files': len(files),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'files': sorted(files, key=lambda x: x['modified'], reverse=True)[:10]  # последние 10
        }
        
        log_web_event("Запрос статуса системы")
        return jsonify(status)
        
    except Exception as e:
        log_web_event(f"Ошибка получения статуса: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/files')
def list_files():
    """Список файлов в хранилище"""
    try:
        files = []
        if os.path.exists(TELEGRAM_STORAGE):
            for file in os.listdir(TELEGRAM_STORAGE):
                filepath = os.path.join(TELEGRAM_STORAGE, file)
                if os.path.isfile(filepath):
                    files.append({
                        'name': file,
                        'size': os.path.getsize(filepath),
                        'size_mb': os.path.getsize(filepath) / (1024 * 1024),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S'),
                        'type': 'zip' if file.endswith('.zip') else 'other'
                    })
        
        return jsonify({'files': sorted(files, key=lambda x: x['modified'], reverse=True)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Скачивание файла"""
    try:
        # Безопасный путь
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(TELEGRAM_STORAGE, safe_filename)
        
        if os.path.exists(filepath):
            log_web_event(f"Скачивание файла: {safe_filename}")
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'Файл не найден'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def get_logs():
    """Получение логов"""
    try:
        log_file = f"{LOGS_PATH}/server_{datetime.now().strftime('%Y%m%d')}.log"
        logs = []
        
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                logs = [line.strip() for line in f.readlines()[-50:]]  # последние 50 строк
        
        return jsonify({'logs': logs})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Удаление файла"""
    try:
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(TELEGRAM_STORAGE, safe_filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            log_web_event(f"Удален файл: {safe_filename}")
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Файл не найден'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system_info')
def system_info():
    """Информация о системе"""
    import psutil
    
    try:
        info = {
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_total': psutil.virtual_memory().total,
            'memory_used': psutil.virtual_memory().used,
            'disk_usage': psutil.disk_usage('/').percent,
            'boot_time': psutil.boot_time(),
            'processes': len(psutil.pids()),
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        }
        
        return jsonify(info)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_web_server():
    """Запуск веб-сервера"""
    print("=" * 60)
    print("🌐 ЗАПУСК ВЕБ-ИНТЕРФЕЙСА")
    print("=" * 60)
    print(f"📡 Адрес: http://localhost:8080")
    print(f"📁 Хранилище: {os.path.abspath(TELEGRAM_STORAGE)}")
    print("=" * 60)
    
    # Создаем папки для статики и шаблонов
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    app.run(host='0.0.0.0', port=8080, debug=False)

if __name__ == '__main__':
    run_web_server()