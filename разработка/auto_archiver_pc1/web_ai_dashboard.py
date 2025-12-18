"""
Веб-интерфейс с AI-аналитикой для ПК1
"""
from flask import Flask, render_template, jsonify, send_file, request
import os
import json
from datetime import datetime
import threading

# Импортируем AI модуль
try:
    from ai_analyzer import AIAnalyzer, ArchiveManager
    AI_ENABLED = True
except ImportError:
    AI_ENABLED = False
    print("⚠️  AI модуль не найден, аналитика будет ограничена")

# Конфигурация
BASE_STORAGE = "./secure_storage"
TELEGRAM_STORAGE = f"{BASE_STORAGE}/telegram"
DECRYPTED_STORAGE = f"{BASE_STORAGE}/decrypted"
AI_RESULTS_PATH = f"{BASE_STORAGE}/ai_results"
LOGS_PATH = f"{BASE_STORAGE}/logs"

# Создаем папки
os.makedirs(DECRYPTED_STORAGE, exist_ok=True)
os.makedirs(AI_RESULTS_PATH, exist_ok=True)
os.makedirs(f"{AI_RESULTS_PATH}/reports", exist_ok=True)
os.makedirs(f"{AI_RESULTS_PATH}/stats", exist_ok=True)

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

# Инициализация AI анализатора
if AI_ENABLED:
    analyzer = AIAnalyzer()
    archive_manager = ArchiveManager()

def log_web_event(message, agent_id=None):
    """Логирование событий веб-интерфейса"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] [WEB] {agent_id if agent_id else ''} {message}"
    
    log_file = f"{LOGS_PATH}/web_{datetime.now().strftime('%Y%m%d')}.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

@app.route('/')
def index():
    """Главная страница с AI аналитикой"""
    log_web_event("Открыта главная страница")
    return render_template('ai_dashboard.html', ai_enabled=AI_ENABLED)

@app.route('/api/status')
def get_status():
    """Получение статуса системы"""
    try:
        # Список архивов
        archives = []
        if os.path.exists(DECRYPTED_STORAGE):
            for file in os.listdir(DECRYPTED_STORAGE):
                if file.endswith('.zip'):
                    filepath = os.path.join(DECRYPTED_STORAGE, file)
                    archives.append({
                        'name': file,
                        'size': os.path.getsize(filepath),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    })
        
        # Список отчетов AI
        ai_reports = []
        if AI_ENABLED and os.path.exists(f"{AI_RESULTS_PATH}/reports"):
            for file in os.listdir(f"{AI_RESULTS_PATH}/reports"):
                if file.endswith('.txt'):
                    filepath = os.path.join(f"{AI_RESULTS_PATH}/reports", file)
                    ai_reports.append({
                        'name': file,
                        'size': os.path.getsize(filepath),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    })
        
        total_size = sum(a['size'] for a in archives)
        
        status = {
            'status': 'running',
            'ai_enabled': AI_ENABLED,
            'server_time': datetime.now().isoformat(),
            'telegram_archives': len(archives),
            'ai_reports': len(ai_reports),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }
        
        log_web_event("Запрос статуса системы")
        return jsonify(status)
        
    except Exception as e:
        log_web_event(f"Ошибка получения статуса: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/archives')
def list_archives():
    """Список архивов с AI информацией"""
    try:
        archives = []
        if os.path.exists(DECRYPTED_STORAGE):
            for file in os.listdir(DECRYPTED_STORAGE):
                if file.endswith('.zip'):
                    filepath = os.path.join(DECRYPTED_STORAGE, file)
                    
                    # Проверяем есть ли AI анализ для этого архива
                    ai_report = None
                    if AI_ENABLED:
                        report_name = file.replace('.zip', '') + '_report.txt'
                        report_path = f"{AI_RESULTS_PATH}/reports/{report_name}"
                        if os.path.exists(report_path):
                            # Ищем актуальный отчет
                            for r_file in os.listdir(f"{AI_RESULTS_PATH}/reports"):
                                if r_file.startswith(file.replace('.zip', '')) and r_file.endswith('_report.txt'):
                                    report_path = f"{AI_RESULTS_PATH}/reports/{r_file}"
                                    ai_report = r_file
                                    break
                    
                    archives.append({
                        'name': file,
                        'path': filepath,
                        'size': os.path.getsize(filepath),
                        'size_mb': os.path.getsize(filepath) / (1024 * 1024),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S'),
                        'has_ai_analysis': ai_report is not None,
                        'ai_report': ai_report
                    })
        
        return jsonify({'archives': sorted(archives, key=lambda x: x['modified'], reverse=True)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/analyze/<archive_name>')
def analyze_archive(archive_name):
    """Запуск AI анализа архива"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI модуль не загружен'}), 500
    
    try:
        safe_name = os.path.basename(archive_name)
        archive_path = os.path.join(DECRYPTED_STORAGE, safe_name)
        
        if not os.path.exists(archive_path):
            return jsonify({'error': 'Архив не найден'}), 404
        
        log_web_event(f"Запуск AI анализа: {safe_name}")
        
        # Запускаем анализ в отдельном потоке
        def analyze_in_background():
            try:
                result = analyzer.analyze_telegram_archive(archive_path)
                log_web_event(f"AI анализ завершен: {safe_name}")
            except Exception as e:
                log_web_event(f"Ошибка AI анализа: {e}", "ERROR")
        
        thread = threading.Thread(target=analyze_in_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'AI анализ запущен для {safe_name}',
            'archive': safe_name
        })
        
    except Exception as e:
        log_web_event(f"Ошибка запуска AI анализа: {e}", "ERROR")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/analyze_all')
def analyze_all_archives():
    """Анализ всех архивов"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI модуль не загружен'}), 500
    
    try:
        log_web_event("Запуск AI анализа всех архивов")
        
        def analyze_all_in_background():
            try:
                results = analyzer.analyze_all_archives()
                log_web_event(f"AI анализ всех архивов завершен: {len(results)} архивов")
            except Exception as e:
                log_web_event(f"Ошибка AI анализа всех архивов: {e}", "ERROR")
        
        thread = threading.Thread(target=analyze_all_in_background)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'AI анализ всех архивов запущен'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/reports')
def list_ai_reports():
    """Список AI отчетов"""
    try:
        reports = []
        if os.path.exists(f"{AI_RESULTS_PATH}/reports"):
            for file in os.listdir(f"{AI_RESULTS_PATH}/reports"):
                if file.endswith('.txt'):
                    filepath = os.path.join(f"{AI_RESULTS_PATH}/reports", file)
                    
                    # Читаем первую строку для предпросмотра
                    preview = ""
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            preview = f.read(500)  # Первые 500 символов
                    except:
                        preview = "Не удалось прочитать отчет"
                    
                    reports.append({
                        'name': file,
                        'size': os.path.getsize(filepath),
                        'size_kb': os.path.getsize(filepath) // 1024,
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M:%S'),
                        'preview': preview[:200] + "..." if len(preview) > 200 else preview
                    })
        
        return jsonify({'reports': sorted(reports, key=lambda x: x['modified'], reverse=True)})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/report/<report_name>')
def get_ai_report(report_name):
    """Получение AI отчета"""
    try:
        safe_name = os.path.basename(report_name)
        report_path = os.path.join(f"{AI_RESULTS_PATH}/reports", safe_name)
        
        if not os.path.exists(report_path):
            return jsonify({'error': 'Отчет не найден'}), 404
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'name': safe_name,
            'content': content,
            'size': len(content)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/stats')
def get_ai_stats():
    """Статистика AI анализа"""
    if not AI_ENABLED:
        return jsonify({'error': 'AI модуль не загружен'}), 500
    
    try:
        # Собираем статистику из JSON файлов
        stats_files = []
        if os.path.exists(f"{AI_RESULTS_PATH}/stats"):
            for file in os.listdir(f"{AI_RESULTS_PATH}/stats"):
                if file.endswith('.json'):
                    filepath = os.path.join(f"{AI_RESULTS_PATH}/stats", file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            
                            stats_files.append({
                                'archive': data.get('archive_name', file),
                                'messages': data.get('basic_stats', {}).get('total_messages', 0),
                                'users': data.get('basic_stats', {}).get('unique_users', 0),
                                'sentiment': data.get('sentiment_analysis', {}).get('sentiment_score', 0),
                                'anomalies': len(data.get('anomalies', [])),
                                'date': data.get('analysis_date', '')
                            })
                    except:
                        continue
        
        # Общая статистика
        total_analyzed = len(stats_files)
        total_messages = sum(s['messages'] for s in stats_files)
        total_users = sum(s['users'] for s in stats_files)
        avg_sentiment = sum(s['sentiment'] for s in stats_files) / total_analyzed if total_analyzed > 0 else 0
        
        # Распределение по тональности
        sentiment_dist = {
            'positive': sum(1 for s in stats_files if s['sentiment'] > 0.1),
            'neutral': sum(1 for s in stats_files if -0.1 <= s['sentiment'] <= 0.1),
            'negative': sum(1 for s in stats_files if s['sentiment'] < -0.1)
        }
        
        return jsonify({
            'total_analyzed': total_analyzed,
            'total_messages': total_messages,
            'total_users': total_users,
            'avg_sentiment': avg_sentiment,
            'sentiment_distribution': sentiment_dist,
            'recent_analyses': stats_files[:10]  # Последние 10 анализов
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Скачивание файла"""
    try:
        safe_filename = os.path.basename(filename)
        
        # Пробуем разные папки
        possible_paths = [
            os.path.join(DECRYPTED_STORAGE, safe_filename),
            os.path.join(f"{AI_RESULTS_PATH}/reports", safe_filename),
            os.path.join(TELEGRAM_STORAGE, safe_filename)
        ]
        
        for filepath in possible_paths:
            if os.path.exists(filepath):
                log_web_event(f"Скачивание файла: {safe_filename}")
                return send_file(filepath, as_attachment=True)
        
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
                logs = [line.strip() for line in f.readlines()[-100:]]
        
        return jsonify({'logs': logs})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup_old_files():
    """Очистка старых файлов"""
    try:
        if not AI_ENABLED:
            return jsonify({'error': 'AI модуль не загружен'}), 500
        
        days = request.json.get('days', 30)
        cleaned = archive_manager.cleanup_old_archives(days_old=days)
        
        log_web_event(f"Очистка старых файлов (старше {days} дней): удалено {cleaned}")
        
        return jsonify({
            'success': True,
            'cleaned': cleaned,
            'days': days
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_ai_dashboard():
    """Запуск веб-интерфейса с AI"""
    print("=" * 60)
    print("🧠 ВЕБ-ИНТЕРФЕЙС С AI-АНАЛИТИКОЙ")
    print("=" * 60)
    print(f"📡 Адрес: http://localhost:8081")
    print(f"🤖 AI аналитика: {'✅ ВКЛЮЧЕНА' if AI_ENABLED else '❌ ВЫКЛЮЧЕНА'}")
    print(f"📁 Хранилище: {os.path.abspath(BASE_STORAGE)}")
    print("=" * 60)
    
    # Создаем папки для шаблонов
    os.makedirs('templates', exist_ok=True)
    
    app.run(host='0.0.0.0', port=8081, debug=False)

if __name__ == '__main__':
    run_ai_dashboard()