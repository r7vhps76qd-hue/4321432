"""
Веб-интерфейс мониторинга агентов на ПК1
"""
from flask import Flask, render_template, jsonify, send_file, request
import os
import json
import sqlite3
from datetime import datetime, timedelta
import threading

# Конфигурация
MONITORING_STORAGE = "./monitoring_storage"
DB_PATH = f"{MONITORING_STORAGE}/monitoring.db"

# Создаем папки
os.makedirs(MONITORING_STORAGE, exist_ok=True)

app = Flask(__name__, 
            static_folder='static',
            template_folder='templates')

def get_db_connection():
    """Подключение к базе данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Главная страница мониторинга"""
    return render_template('monitoring_dashboard.html')

@app.route('/api/agents')
def get_agents():
    """Получение списка агентов"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем список агентов с последними метриками
        cursor.execute('''
            SELECT 
                a.agent_id,
                a.hostname,
                a.os,
                a.status,
                a.ip_address,
                a.last_seen,
                (SELECT cpu_percent FROM cpu_monitoring 
                 WHERE agent_id = a.agent_id 
                 ORDER BY timestamp DESC LIMIT 1) as last_cpu,
                (SELECT ram_percent FROM memory_monitoring 
                 WHERE agent_id = a.agent_id 
                 ORDER BY timestamp DESC LIMIT 1) as last_ram,
                (SELECT COUNT(*) FROM events 
                 WHERE agent_id = a.agent_id AND severity = 'ERROR' 
                 AND timestamp > datetime('now', '-1 day')) as errors_last_24h
            FROM agents a
            ORDER BY a.last_seen DESC
        ''')
        
        agents = []
        for row in cursor.fetchall():
            agent = dict(row)
            
            # Проверяем активность
            last_seen = datetime.fromisoformat(agent['last_seen']) if agent['last_seen'] else datetime.now()
            time_diff = (datetime.now() - last_seen).total_seconds()
            
            if time_diff > 300:  # 5 минут
                agent['status'] = 'OFFLINE'
                agent['active_minutes_ago'] = int(time_diff // 60)
            else:
                agent['status'] = 'ONLINE'
                agent['active_minutes_ago'] = 0
            
            agents.append(agent)
        
        # Статистика
        total_agents = len(agents)
        online_agents = sum(1 for a in agents if a['status'] == 'ONLINE')
        
        conn.close()
        
        return jsonify({
            'agents': agents,
            'stats': {
                'total': total_agents,
                'online': online_agents,
                'offline': total_agents - online_agents
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/<agent_id>')
def get_agent_details(agent_id):
    """Получение детальной информации об агенте"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Информация об агенте
        cursor.execute('SELECT * FROM agents WHERE agent_id = ?', (agent_id,))
        agent_row = cursor.fetchone()
        
        if not agent_row:
            return jsonify({'error': 'Agent not found'}), 404
        
        agent_info = dict(agent_row)
        
        # История CPU (последние 100 записей)
        cursor.execute('''
            SELECT timestamp, cpu_percent, cpu_freq 
            FROM cpu_monitoring 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''', (agent_id,))
        
        cpu_history = [dict(row) for row in cursor.fetchall()]
        
        # История памяти
        cursor.execute('''
            SELECT timestamp, ram_percent, ram_used_gb, ram_total_gb
            FROM memory_monitoring 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 100
        ''', (agent_id,))
        
        memory_history = [dict(row) for row in cursor.fetchall()]
        
        # История дисков
        cursor.execute('''
            SELECT timestamp, mountpoint, disk_percent, disk_used_gb, disk_total_gb
            FROM disk_monitoring 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''', (agent_id,))
        
        disk_history = [dict(row) for row in cursor.fetchall()]
        
        # Последние процессы
        cursor.execute('''
            SELECT timestamp, process_name, pid, cpu_percent, memory_percent, username, status
            FROM processes 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''', (agent_id,))
        
        processes = [dict(row) for row in cursor.fetchall()]
        
        # События
        cursor.execute('''
            SELECT timestamp, event_type, event_message, severity
            FROM events 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''', (agent_id,))
        
        events = [dict(row) for row in cursor.fetchall()]
        
        # Сетевая активность
        cursor.execute('''
            SELECT timestamp, local_address, remote_address, status, pid
            FROM network_connections 
            WHERE agent_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''', (agent_id,))
        
        network = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'agent_info': agent_info,
            'cpu_history': cpu_history,
            'memory_history': memory_history,
            'disk_history': disk_history,
            'processes': processes,
            'events': events,
            'network': network,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/<agent_id>/stats')
def get_agent_stats(agent_id):
    """Получение статистики агента"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Средняя загрузка за последние 24 часа
        cursor.execute('''
            SELECT 
                AVG(cpu_percent) as avg_cpu,
                AVG(ram_percent) as avg_ram,
                MAX(cpu_percent) as max_cpu,
                MAX(ram_percent) as max_ram,
                COUNT(*) as samples
            FROM (
                SELECT 
                    (SELECT cpu_percent FROM cpu_monitoring 
                     WHERE agent_id = ? AND timestamp > datetime('now', '-1 day')
                     ORDER BY timestamp DESC LIMIT 1) as cpu_percent,
                    (SELECT ram_percent FROM memory_monitoring 
                     WHERE agent_id = ? AND timestamp > datetime('now', '-1 day')
                     ORDER BY timestamp DESC LIMIT 1) as ram_percent
            )
        ''', (agent_id, agent_id))
        
        stats_row = cursor.fetchone()
        stats = dict(stats_row) if stats_row else {}
        
        # Количество процессов
        cursor.execute('SELECT COUNT(*) FROM processes WHERE agent_id = ?', (agent_id,))
        stats['total_processes'] = cursor.fetchone()[0]
        
        # Количество событий по типам
        cursor.execute('''
            SELECT severity, COUNT(*) as count
            FROM events 
            WHERE agent_id = ? 
            GROUP BY severity
        ''', (agent_id,))
        
        event_stats = {row['severity']: row['count'] for row in cursor.fetchall()}
        stats['events'] = event_stats
        
        conn.close()
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/<agent_id>/command', methods=['POST'])
def send_command(agent_id):
    """Отправка команды агенту"""
    try:
        data = request.json
        command = data.get('command', '')
        
        # Здесь будет реализация отправки команд агенту
        # Пока просто логируем
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO events (agent_id, timestamp, event_type, event_message, severity)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            agent_id,
            datetime.now().isoformat(),
            'COMMAND',
            f'Command sent: {command}',
            'INFO'
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Command logged for {agent_id}: {command}',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/stats')
def get_dashboard_stats():
    """Статистика для дашборда"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute('SELECT COUNT(*) FROM agents')
        total_agents = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM agents WHERE status = "ONLINE"')
        online_agents = cursor.fetchone()[0]
        
        # Загрузка за последний час
        cursor.execute('''
            SELECT 
                AVG(cpu_percent) as avg_cpu,
                AVG(ram_percent) as avg_ram
            FROM (
                SELECT 
                    (SELECT cpu_percent FROM cpu_monitoring 
                     WHERE timestamp > datetime('now', '-1 hour')
                     ORDER BY timestamp DESC LIMIT 1) as cpu_percent,
                    (SELECT ram_percent FROM memory_monitoring 
                     WHERE timestamp > datetime('now', '-1 hour')
                     ORDER BY timestamp DESC LIMIT 1) as ram_percent
            )
        ''')
        
        load_row = cursor.fetchone()
        
        # Последние события
        cursor.execute('''
            SELECT agent_id, timestamp, event_type, event_message, severity
            FROM events 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        
        recent_events = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'total_agents': total_agents,
            'online_agents': online_agents,
            'avg_cpu': load_row['avg_cpu'] if load_row and load_row['avg_cpu'] else 0,
            'avg_ram': load_row['avg_ram'] if load_row and load_row['avg_ram'] else 0,
            'recent_events': recent_events,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def get_alerts():
    """Получение оповещений"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Оповещения за последние 24 часа
        cursor.execute('''
            SELECT agent_id, timestamp, event_type, event_message, severity
            FROM events 
            WHERE severity IN ('ERROR', 'WARNING') 
            AND timestamp > datetime('now', '-1 day')
            ORDER BY timestamp DESC
        ''')
        
        alerts = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'alerts': alerts,
            'total': len(alerts),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_monitoring_dashboard():
    """Запуск веб-интерфейса мониторинга"""
    print("=" * 60)
    print("📊 ВЕБ-ИНТЕРФЕЙС МОНИТОРИНГА АГЕНТОВ")
    print("=" * 60)
    print(f"📡 Адрес: http://localhost:8082")
    print(f"🗄️  База данных: {DB_PATH}")
    print("=" * 60)
    
    # Создаем папку для шаблонов
    os.makedirs('templates', exist_ok=True)
    
    app.run(host='0.0.0.0', port=8082, debug=False)

if __name__ == '__main__':
    run_monitoring_dashboard()