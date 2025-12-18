"""
Главный сервер системы на ПК1 с поддержкой мониторинга агентов
"""
import socket
import json
import os
import base64
import hashlib
from datetime import datetime
import threading
from cryptography.fernet import Fernet, InvalidToken
import sqlite3

class MonitoringServer:
    def __init__(self, host='0.0.0.0', port=9090):
        self.host = host
        self.port = port
        self.running = True
        
        # Хранилище
        self.base_storage = "./monitoring_storage"
        self.agents_storage = f"{self.base_storage}/agents"
        self.db_path = f"{self.base_storage}/monitoring.db"
        self.logs_path = f"{self.base_storage}/logs"
        
        # Создаем структуру папок
        self._create_folders()
        
        # Инициализируем базу данных
        self._init_database()
        
        # Загружаем ключи шифрования
        self.encryption_keys = self._load_encryption_keys()
        
        # Список активных агентов
        self.active_agents = {}
        
        print("=" * 60)
        print("🚀 СИСТЕМА МОНИТОРИНГА АГЕНТОВ")
        print("=" * 60)
        print(f"📡 Сервер запускается на {self.host}:{self.port}")
        print(f"🗄️  База данных: {self.db_path}")
        print(f"🤖 Загружено ключей: {len(self.encryption_keys)}")
        print("=" * 60)
    
    def _create_folders(self):
        """Создание структуры папок"""
        folders = [
            self.base_storage,
            self.agents_storage,
            self.logs_path,
            f"{self.agents_storage}/screenshots",
            f"{self.agents_storage}/logs"
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
            print(f"📁 Создана папка: {folder}")
    
    def _init_database(self):
        """Инициализация базы данных"""
        try:
            self.db_conn = sqlite3.connect(self.db_path)
            self.db_cursor = self.db_conn.cursor()
            
            # Таблица агентов
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    hostname TEXT,
                    os TEXT,
                    cpu_info TEXT,
                    memory_gb REAL,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    status TEXT,
                    ip_address TEXT
                )
            ''')
            
            # Таблица мониторинга CPU
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS cpu_monitoring (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    cpu_percent REAL,
                    cpu_freq REAL,
                    user_percent REAL,
                    system_percent REAL,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица мониторинга памяти
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory_monitoring (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    ram_percent REAL,
                    ram_used_gb REAL,
                    ram_total_gb REAL,
                    swap_percent REAL,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица мониторинга дисков
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS disk_monitoring (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    mountpoint TEXT,
                    disk_percent REAL,
                    disk_used_gb REAL,
                    disk_total_gb REAL,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица процессов
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    process_name TEXT,
                    pid INTEGER,
                    cpu_percent REAL,
                    memory_percent REAL,
                    username TEXT,
                    status TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица сетевых подключений
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS network_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    local_address TEXT,
                    remote_address TEXT,
                    status TEXT,
                    pid INTEGER,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица скриншотов
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS screenshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    filename TEXT,
                    filepath TEXT,
                    size_bytes INTEGER,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            # Таблица событий
            self.db_cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT,
                    timestamp TIMESTAMP,
                    event_type TEXT,
                    event_message TEXT,
                    severity TEXT,
                    FOREIGN KEY (agent_id) REFERENCES agents (agent_id)
                )
            ''')
            
            self.db_conn.commit()
            print("✅ База данных инициализирована")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации базы данных: {e}")
    
    def _load_encryption_keys(self):
        """Загрузка ключей шифрования"""
        keys = {}
        keys_path = f"{self.base_storage}/keys"
        os.makedirs(keys_path, exist_ok=True)
        
        if os.path.exists(keys_path):
            for key_file in os.listdir(keys_path):
                if key_file.endswith('.key'):
                    try:
                        with open(os.path.join(keys_path, key_file), 'rb') as f:
                            key_data = f.read()
                            agent_id = key_file.replace('.key', '')
                            keys[agent_id] = key_data
                    except Exception as e:
                        print(f"❌ Ошибка загрузки ключа {key_file}: {e}")
        
        return keys
    
    def log_event(self, message, level="INFO", agent_id=None):
        """Логирование событий"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agent_str = f"[{agent_id}] " if agent_id else ""
        log_msg = f"[{timestamp}] [{level}] {agent_str}{message}"
        
        # Вывод в консоль
        print(log_msg)
        
        # Сохранение в файл
        log_file = f"{self.logs_path}/server_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
        except Exception as e:
            print(f"❌ Ошибка записи лога: {e}")
    
    def handle_monitoring_data(self, client_socket, client_ip, data):
        """Обработка данных мониторинга"""
        agent_id = None
        
        try:
            # Пытаемся расшифровать данные
            decrypted_data = None
            
            if data.startswith(b"ENCRYPTED::"):
                # Пробуем все ключи
                for key_agent_id, key_data in self.encryption_keys.items():
                    try:
                        cipher = Fernet(key_data)
                        decrypted = cipher.decrypt(data[10:])
                        decrypted_json = json.loads(decrypted.decode('utf-8'))
                        
                        # Проверяем agent_id в данных
                        if 'summary' in decrypted_json and 'agent_id' in decrypted_json['summary']:
                            if decrypted_json['summary']['agent_id'] == key_agent_id:
                                decrypted_data = decrypted_json
                                agent_id = key_agent_id
                                break
                    except (InvalidToken, json.JSONDecodeError):
                        continue
            
            if not decrypted_data:
                # Пробуем как незашифрованные данные
                try:
                    decrypted_data = json.loads(data.decode('utf-8'))
                    if 'summary' in decrypted_data and 'agent_id' in decrypted_data['summary']:
                        agent_id = decrypted_data['summary']['agent_id']
                except:
                    pass
            
            if not decrypted_data or not agent_id:
                self.log_event(f"❌ Не удалось расшифровать данные от {client_ip}", "ERROR")
                client_socket.send(json.dumps({"status": "error", "message": "Decryption failed"}).encode('utf-8'))
                return
            
            # Обрабатываем данные мониторинга
            self._process_monitoring_data(agent_id, client_ip, decrypted_data)
            
            # Отправляем подтверждение
            response = {
                "status": "success",
                "message": f"Monitoring data received from {agent_id}",
                "timestamp": datetime.now().isoformat()
            }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
            self.log_event(f"📊 Получены данные мониторинга от {agent_id}", agent_id=agent_id)
            
        except Exception as e:
            error_msg = f"❌ Ошибка обработки данных мониторинга: {e}"
            self.log_event(error_msg, "ERROR", agent_id)
            
            try:
                client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            except:
                pass
    
    def _process_monitoring_data(self, agent_id, client_ip, data):
        """Обработка и сохранение данных мониторинга"""
        try:
            summary = data.get('summary', {})
            system_info = summary.get('system_info', {})
            current_stats = summary.get('current_stats', {})
            
            # Обновляем информацию об агенте
            self._update_agent_info(agent_id, client_ip, system_info, summary.get('monitoring_status', {}))
            
            # Сохраняем текущие метрики
            timestamp = datetime.now()
            
            # CPU данные
            if 'cpu_percent' in current_stats:
                self.db_cursor.execute('''
                    INSERT INTO cpu_monitoring (agent_id, timestamp, cpu_percent)
                    VALUES (?, ?, ?)
                ''', (agent_id, timestamp, current_stats['cpu_percent']))
            
            # Memory данные
            if 'memory_percent' in current_stats:
                self.db_cursor.execute('''
                    INSERT INTO memory_monitoring (agent_id, timestamp, ram_percent)
                    VALUES (?, ?, ?)
                ''', (agent_id, timestamp, current_stats['memory_percent']))
            
            # Disk данные
            if 'disk_percent' in current_stats:
                self.db_cursor.execute('''
                    INSERT INTO disk_monitoring (agent_id, timestamp, mountpoint, disk_percent)
                    VALUES (?, ?, ?, ?)
                ''', (agent_id, timestamp, '/', current_stats['disk_percent']))
            
            # Полные данные мониторинга
            if 'cpu_history' in data:
                for cpu_data in data['cpu_history'][-10:]:  # Последние 10 записей
                    try:
                        self.db_cursor.execute('''
                            INSERT INTO cpu_monitoring 
                            (agent_id, timestamp, cpu_percent, cpu_freq, user_percent, system_percent)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            agent_id,
                            datetime.fromisoformat(cpu_data.get('timestamp', '')),
                            cpu_data.get('percent_total', 0),
                            cpu_data.get('frequency_current', 0),
                            cpu_data.get('times', {}).get('user', 0),
                            cpu_data.get('times', {}).get('system', 0)
                        ))
                    except:
                        continue
            
            if 'memory_history' in data:
                for mem_data in data['memory_history'][-10:]:
                    try:
                        ram = mem_data.get('ram', {})
                        self.db_cursor.execute('''
                            INSERT INTO memory_monitoring 
                            (agent_id, timestamp, ram_percent, ram_used_gb, ram_total_gb, swap_percent)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            agent_id,
                            datetime.fromisoformat(mem_data.get('timestamp', '')),
                            ram.get('percent', 0),
                            ram.get('used', 0) / (1024**3),
                            ram.get('total', 0) / (1024**3),
                            mem_data.get('swap', {}).get('percent', 0)
                        ))
                    except:
                        continue
            
            if 'processes' in data:
                for proc in data['processes'][:20]:  # Первые 20 процессов
                    try:
                        self.db_cursor.execute('''
                            INSERT INTO processes 
                            (agent_id, timestamp, process_name, pid, cpu_percent, memory_percent, username, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            agent_id,
                            timestamp,
                            proc.get('name', ''),
                            proc.get('pid', 0),
                            proc.get('cpu_percent', 0),
                            proc.get('memory_percent', 0),
                            proc.get('username', ''),
                            proc.get('status', '')
                        ))
                    except:
                        continue
            
            self.db_conn.commit()
            
            # Добавляем событие
            self.db_cursor.execute('''
                INSERT INTO events (agent_id, timestamp, event_type, event_message, severity)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                agent_id,
                timestamp,
                'MONITORING_DATA',
                f'Received monitoring data: CPU {current_stats.get("cpu_percent", 0):.1f}%, RAM {current_stats.get("memory_percent", 0):.1f}%',
                'INFO'
            ))
            
            self.db_conn.commit()
            
        except Exception as e:
            self.log_event(f"❌ Ошибка обработки данных: {e}", "ERROR", agent_id)
    
    def _update_agent_info(self, agent_id, client_ip, system_info, monitoring_status):
        """Обновление информации об агенте"""
        try:
            timestamp = datetime.now()
            
            # Проверяем существует ли агент
            self.db_cursor.execute('SELECT agent_id FROM agents WHERE agent_id = ?', (agent_id,))
            agent_exists = self.db_cursor.fetchone()
            
            if agent_exists:
                # Обновляем существующего агента
                self.db_cursor.execute('''
                    UPDATE agents 
                    SET last_seen = ?, status = ?, ip_address = ?
                    WHERE agent_id = ?
                ''', (timestamp, 'ONLINE', client_ip, agent_id))
            else:
                # Добавляем нового агента
                cpu_info = system_info.get('cpu', {}).get('brand_raw', 'Unknown')
                memory_gb = system_info.get('memory', {}).get('total_gb', 0)
                
                self.db_cursor.execute('''
                    INSERT INTO agents 
                    (agent_id, hostname, os, cpu_info, memory_gb, first_seen, last_seen, status, ip_address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    agent_id,
                    system_info.get('hostname', 'Unknown'),
                    f"{system_info.get('os', 'Unknown')} {system_info.get('platform', '')}",
                    cpu_info,
                    memory_gb,
                    timestamp,
                    timestamp,
                    'ONLINE',
                    client_ip
                ))
            
            # Обновляем список активных агентов
            self.active_agents[agent_id] = {
                'ip': client_ip,
                'last_seen': timestamp,
                'status': 'ONLINE',
                'monitoring_active': monitoring_status.get('active', False)
            }
            
        except Exception as e:
            self.log_event(f"❌ Ошибка обновления информации об агенте: {e}", "ERROR", agent_id)
    
    def get_agents_summary(self):
        """Получение сводки по агентам"""
        try:
            # Получаем список агентов из БД
            self.db_cursor.execute('''
                SELECT 
                    agent_id,
                    hostname,
                    os,
                    status,
                    ip_address,
                    last_seen,
                    (SELECT cpu_percent FROM cpu_monitoring 
                     WHERE agent_id = agents.agent_id 
                     ORDER BY timestamp DESC LIMIT 1) as last_cpu,
                    (SELECT ram_percent FROM memory_monitoring 
                     WHERE agent_id = agents.agent_id 
                     ORDER BY timestamp DESC LIMIT 1) as last_ram
                FROM agents
                ORDER BY last_seen DESC
            ''')
            
            agents = []
            for row in self.db_cursor.fetchall():
                agent_id, hostname, os, status, ip, last_seen, last_cpu, last_ram = row
                
                # Проверяем активность (если не было связи больше 5 минут = OFFLINE)
                last_seen_dt = datetime.fromisoformat(last_seen) if isinstance(last_seen, str) else last_seen
                time_diff = (datetime.now() - last_seen_dt).total_seconds()
                
                if time_diff > 300:  # 5 минут
                    status = 'OFFLINE'
                
                agents.append({
                    'agent_id': agent_id,
                    'hostname': hostname,
                    'os': os,
                    'status': status,
                    'ip_address': ip,
                    'last_seen': last_seen,
                    'last_cpu': last_cpu,
                    'last_ram': last_ram,
                    'active_seconds_ago': int(time_diff)
                })
            
            # Общая статистика
            self.db_cursor.execute('SELECT COUNT(*) FROM agents')
            total_agents = self.db_cursor.fetchone()[0]
            
            self.db_cursor.execute('SELECT COUNT(*) FROM agents WHERE status = "ONLINE"')
            online_agents = self.db_cursor.fetchone()[0]
            
            summary = {
                'total_agents': total_agents,
                'online_agents': online_agents,
                'offline_agents': total_agents - online_agents,
                'agents': agents,
                'timestamp': datetime.now().isoformat()
            }
            
            return summary
            
        except Exception as e:
            self.log_event(f"❌ Ошибка получения сводки: {e}", "ERROR")
            return {}
    
    def get_agent_details(self, agent_id):
        """Получение детальной информации об агенте"""
        try:
            # Информация об агенте
            self.db_cursor.execute('SELECT * FROM agents WHERE agent_id = ?', (agent_id,))
            agent_row = self.db_cursor.fetchone()
            
            if not agent_row:
                return None
            
            # Колонки таблицы agents
            columns = ['agent_id', 'hostname', 'os', 'cpu_info', 'memory_gb', 
                      'first_seen', 'last_seen', 'status', 'ip_address']
            
            agent_info = dict(zip(columns, agent_row))
            
            # Последние метрики CPU (24 часа)
            self.db_cursor.execute('''
                SELECT timestamp, cpu_percent, cpu_freq 
                FROM cpu_monitoring 
                WHERE agent_id = ? AND timestamp > datetime('now', '-1 day')
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (agent_id,))
            
            cpu_history = []
            for row in self.db_cursor.fetchall():
                cpu_history.append({
                    'timestamp': row[0],
                    'cpu_percent': row[1],
                    'cpu_freq': row[2]
                })
            
            # Последние метрики памяти
            self.db_cursor.execute('''
                SELECT timestamp, ram_percent, ram_used_gb, ram_total_gb
                FROM memory_monitoring 
                WHERE agent_id = ? AND timestamp > datetime('now', '-1 day')
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (agent_id,))
            
            memory_history = []
            for row in self.db_cursor.fetchall():
                memory_history.append({
                    'timestamp': row[0],
                    'ram_percent': row[1],
                    'ram_used_gb': row[2],
                    'ram_total_gb': row[3]
                })
            
            # Последние процессы
            self.db_cursor.execute('''
                SELECT timestamp, process_name, pid, cpu_percent, memory_percent, username, status
                FROM processes 
                WHERE agent_id = ? 
                ORDER BY timestamp DESC
                LIMIT 50
            ''', (agent_id,))
            
            processes = []
            for row in self.db_cursor.fetchall():
                processes.append({
                    'timestamp': row[0],
                    'name': row[1],
                    'pid': row[2],
                    'cpu_percent': row[3],
                    'memory_percent': row[4],
                    'username': row[5],
                    'status': row[6]
                })
            
            # События
            self.db_cursor.execute('''
                SELECT timestamp, event_type, event_message, severity
                FROM events 
                WHERE agent_id = ? 
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (agent_id,))
            
            events = []
            for row in self.db_cursor.fetchall():
                events.append({
                    'timestamp': row[0],
                    'type': row[1],
                    'message': row[2],
                    'severity': row[3]
                })
            
            return {
                'agent_info': agent_info,
                'cpu_history': cpu_history,
                'memory_history': memory_history,
                'processes': processes,
                'events': events,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.log_event(f"❌ Ошибка получения деталей агента: {e}", "ERROR", agent_id)
            return None
    
    def handle_client(self, client_socket, address):
        """Обработка подключения от агента"""
        client_ip = address[0]
        
        try:
            # Получаем заголовок (первые 10 байт)
            header = client_socket.recv(10).decode('utf-8').strip()
            
            if header == "MONITORING":
                # Получаем размер данных
                size_data = client_socket.recv(20).decode('utf-8').strip()
                data_size = int(size_data)
                
                # Получаем данные
                data = b""
                while len(data) < data_size:
                    chunk = client_socket.recv(min(4096, data_size - len(data)))
                    if not chunk:
                        break
                    data += chunk
                
                if data:
                    self.handle_monitoring_data(client_socket, client_ip, data)
                else:
                    self.log_event(f"⚠️  Пустые данные от {client_ip}", "WARNING")
                    
            elif header == "SECURE_FILE":
                self._handle_secure_file(client_socket, client_ip)
            elif header == "TELEGRAM":
                self._handle_legacy_telegram(client_socket, client_ip)
            else:
                self.log_event(f"⚠️ Неизвестный заголовок: {header}", "WARNING", client_ip)
                
        except Exception as e:
            self.log_event(f"❌ Ошибка обработки клиента: {e}", "ERROR", client_ip)
        finally:
            client_socket.close()
    
    def _handle_secure_file(self, client_socket, client_ip):
        """Обработка защищенных файлов"""
        try:
            # Получаем размер пакета
            size_data = client_socket.recv(20).decode('utf-8').strip()
            packet_size = int(size_data)
            
            # Получаем пакет
            packet_json = b""
            while len(packet_json) < packet_size:
                chunk = client_socket.recv(min(4096, packet_size - len(packet_json)))
                if not chunk:
                    break
                packet_json += chunk
            
            # Парсим пакет
            packet = json.loads(packet_json.decode('utf-8'))
            metadata = packet.get('metadata', {})
            encrypted_data_b64 = packet.get('data', '')
            
            agent_id = metadata.get('agent_id', client_ip)
            filename = metadata.get('filename', 'unknown')
            
            # Декодируем и сохраняем данные
            encrypted_data = base64.b64decode(encrypted_data_b64)
            
            # Создаем папку для агента
            agent_folder = f"{self.agents_storage}/{agent_id}"
            os.makedirs(agent_folder, exist_ok=True)
            
            # Сохраняем файл
            filepath = f"{agent_folder}/{filename}"
            with open(filepath, 'wb') as f:
                f.write(encrypted_data)
            
            self.log_event(f"💾 Получен файл от {agent_id}: {filename}", agent_id=agent_id)
            
            response = {
                "status": "success",
                "message": f"File received: {filename}",
                "verified": True
            }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            error_msg = f"❌ Ошибка обработки файла: {e}"
            self.log_event(error_msg, "ERROR", client_ip)
            client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
    
    def _handle_legacy_telegram(self, client_socket, client_ip):
        """Обработка старых файлов"""
        try:
            size_data = client_socket.recv(20).decode('utf-8').strip()
            data_size = int(size_data)
            
            filename_data = client_socket.recv(100).decode('utf-8').strip()
            
            # Получаем данные
            data = b""
            while len(data) < data_size:
                chunk = client_socket.recv(min(4096, data_size - len(data)))
                if not chunk:
                    break
                data += chunk
            
            # Сохраняем
            legacy_path = f"{self.base_storage}/legacy"
            os.makedirs(legacy_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_filename = f"legacy_{client_ip}_{timestamp}_{filename_data}"
            save_path = f"{legacy_path}/{save_filename}"
            
            with open(save_path, "wb") as f:
                f.write(data)
            
            self.log_event(f"📝 Получен legacy файл: {save_filename}")
            
            response = json.dumps({
                "status": "success",
                "message": f"Legacy file saved: {save_filename}"
            })
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            error_msg = f"❌ Ошибка приема legacy файла: {e}"
            self.log_event(error_msg, "ERROR", client_ip)
            client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
    
    def start(self):
        """Запуск сервера"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            self.log_event(f"✅ Сервер запущен на {self.host}:{self.port}")
            
            while self.running:
                try:
                    server_socket.settimeout(1)
                    client_socket, address = server_socket.accept()
                    
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_event(f"❌ Ошибка accept: {e}", "ERROR")
                    
        except Exception as e:
            self.log_event(f"❌ Критическая ошибка сервера: {e}", "ERROR")
        finally:
            server_socket.close()
            self.db_conn.close()
            self.log_event("🔴 Сервер остановлен")

if __name__ == "__main__":
    server = MonitoringServer(port=9090)
    server.start()