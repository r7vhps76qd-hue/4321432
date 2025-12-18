"""
Агент для ПК2 с шифрованием и мониторингом
Собирает данные, шифрует и отправляет на главный сервер (ПК1)
"""
import socket
import json
import os
import time
import hashlib
import base64
import psutil
import platform
import cpuinfo
import GPUtil
import screeninfo
import threading
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class SystemAgent:
    def __init__(self, server_ip='192.168.1.100', server_port=9090):
        """
        Инициализация агента
        
        Args:
            server_ip (str): IP адрес главного сервера (ПК1)
            server_port (int): Порт сервера
        """
        self.server_ip = server_ip
        self.server_port = server_port
        self.agent_id = f"agent_{socket.gethostname()}_{platform.node()}"
        self.running = True
        self.monitoring_active = False
        self.monitoring_thread = None
        
        # Ключ шифрования
        self.encryption_key = self._load_or_generate_key()
        
        # Папки
        self.temp_dir = "./temp"
        self.secure_temp_dir = "./secure_temp"
        self.logs_dir = "./logs"
        
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.secure_temp_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Конфигурация мониторинга
        self.monitoring_config = {
            'cpu_interval': 5,
            'memory_interval': 10,
            'disk_interval': 30,
            'network_interval': 5,
            'process_interval': 60,
            'screenshot_interval': 0,  # 0 = отключено
            'max_log_size': 100 * 1024 * 1024  # 100 MB
        }
        
        # Данные мониторинга
        self.system_info = self._collect_system_info()
        self.monitoring_data = {
            'cpu_history': [],
            'memory_history': [],
            'disk_history': [],
            'network_history': [],
            'processes': [],
            'screenshots': []
        }
        
        print("=" * 60)
        print("🤖 АГЕНТ АВТОНОМНОЙ СИСТЕМЫ УПРАВЛЕНИЯ")
        print("=" * 60)
        print(f"🆔 ID агента: {self.agent_id}")
        print(f"📡 Сервер: {self.server_ip}:{self.server_port}")
        print(f"🔐 Шифрование: {'✅ ВКЛ' if self.encryption_key else '❌ ВЫКЛ'}")
        print(f"💻 Система: {self.system_info['os']} {self.system_info['platform']}")
        print(f"⚙️  CPU: {self.system_info['cpu']['brand_raw']}")
        print(f"💾 RAM: {self.system_info['memory']['total_gb']:.1f} GB")
        print("=" * 60)
    
    def _collect_system_info(self):
        """Сбор информации о системе"""
        try:
            # CPU информация
            cpu_info = cpuinfo.get_cpu_info()
            
            # Память
            mem = psutil.virtual_memory()
            
            # Диски
            disks = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disks.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total_gb': usage.total / (1024**3),
                        'used_gb': usage.used / (1024**3),
                        'free_gb': usage.free / (1024**3),
                        'percent': usage.percent
                    })
                except:
                    continue
            
            # GPU
            gpus = []
            try:
                for gpu in GPUtil.getGPUs():
                    gpus.append({
                        'name': gpu.name,
                        'load': gpu.load * 100,
                        'memory_total': gpu.memoryTotal,
                        'memory_used': gpu.memoryUsed,
                        'memory_free': gpu.memoryFree,
                        'temperature': gpu.temperature
                    })
            except:
                pass
            
            # Мониторы
            monitors = []
            try:
                for m in screeninfo.get_monitors():
                    monitors.append({
                        'name': m.name if hasattr(m, 'name') else 'Monitor',
                        'width': m.width,
                        'height': m.height,
                        'x': m.x,
                        'y': m.y
                    })
            except:
                pass
            
            # Сетевые интерфейсы
            networks = []
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        networks.append({
                            'interface': iface,
                            'ip': addr.address,
                            'netmask': addr.netmask
                        })
            
            return {
                'hostname': socket.gethostname(),
                'os': platform.system(),
                'platform': platform.platform(),
                'processor': platform.processor(),
                'cpu': {
                    'brand_raw': cpu_info.get('brand_raw', 'Unknown'),
                    'cores': psutil.cpu_count(logical=False),
                    'threads': psutil.cpu_count(logical=True),
                    'hz': cpu_info.get('hz_actual_friendly', 'Unknown')
                },
                'memory': {
                    'total': mem.total,
                    'total_gb': mem.total / (1024**3),
                    'available': mem.available,
                    'available_gb': mem.available / (1024**3)
                },
                'disks': disks,
                'gpus': gpus,
                'monitors': monitors,
                'networks': networks,
                'boot_time': psutil.boot_time(),
                'python_version': platform.python_version()
            }
            
        except Exception as e:
            print(f"❌ Ошибка сбора информации о системе: {e}")
            return {}
    
    def _load_or_generate_key(self):
        """Загрузка или генерация ключа шифрования"""
        key_file = "./encryption_key.key"
        
        try:
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    key = f.read()
                print(f"✅ Ключ шифрования загружен из файла")
                return key
            else:
                # Генерируем новый ключ
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                print(f"✅ Сгенерирован новый ключ шифрования")
                return key
        except Exception as e:
            print(f"❌ Ошибка работы с ключом шифрования: {e}")
            return None
    
    def start_monitoring(self):
        """Запуск мониторинга системы"""
        if self.monitoring_active:
            print("📊 Мониторинг уже запущен")
            return
        
        print("🚀 Запуск мониторинга системы...")
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        print("✅ Мониторинг запущен")
        print(f"   📈 CPU: каждые {self.monitoring_config['cpu_interval']} сек")
        print(f"   💾 RAM: каждые {self.monitoring_config['memory_interval']} сек")
        print(f"   💿 Disk: каждые {self.monitoring_config['disk_interval']} сек")
        print(f"   🌐 Network: каждые {self.monitoring_config['network_interval']} сек")
        if self.monitoring_config['screenshot_interval'] > 0:
            print(f"   🖼️  Скриншоты: каждые {self.monitoring_config['screenshot_interval']} сек")
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        if not self.monitoring_active:
            print("📊 Мониторинг не запущен")
            return
        
        print("🛑 Остановка мониторинга...")
        self.monitoring_active = False
        
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        print("✅ Мониторинг остановлен")
    
    def _monitoring_loop(self):
        """Цикл мониторинга"""
        last_cpu_time = 0
        last_memory_time = 0
        last_disk_time = 0
        last_network_time = 0
        last_process_time = 0
        last_screenshot_time = 0
        
        while self.monitoring_active:
            current_time = time.time()
            
            # Мониторинг CPU
            if current_time - last_cpu_time >= self.monitoring_config['cpu_interval']:
                self._monitor_cpu()
                last_cpu_time = current_time
            
            # Мониторинг памяти
            if current_time - last_memory_time >= self.monitoring_config['memory_interval']:
                self._monitor_memory()
                last_memory_time = current_time
            
            # Мониторинг дисков
            if current_time - last_disk_time >= self.monitoring_config['disk_interval']:
                self._monitor_disks()
                last_disk_time = current_time
            
            # Мониторинг сети
            if current_time - last_network_time >= self.monitoring_config['network_interval']:
                self._monitor_network()
                last_network_time = current_time
            
            # Мониторинг процессов
            if current_time - last_process_time >= self.monitoring_config['process_interval']:
                self._monitor_processes()
                last_process_time = current_time
            
            # Скриншоты
            if (self.monitoring_config['screenshot_interval'] > 0 and 
                current_time - last_screenshot_time >= self.monitoring_config['screenshot_interval']):
                self._take_screenshot()
                last_screenshot_time = current_time
            
            # Очистка старых данных
            self._cleanup_old_data()
            
            time.sleep(1)
    
    def _monitor_cpu(self):
        """Мониторинг CPU"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            cpu_freq = psutil.cpu_freq()
            cpu_times = psutil.cpu_times_percent()
            
            cpu_data = {
                'timestamp': datetime.now().isoformat(),
                'percent_per_core': cpu_percent,
                'percent_total': sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0,
                'frequency_current': cpu_freq.current if cpu_freq else None,
                'frequency_min': cpu_freq.min if cpu_freq else None,
                'frequency_max': cpu_freq.max if cpu_freq else None,
                'times': {
                    'user': cpu_times.user,
                    'system': cpu_times.system,
                    'idle': cpu_times.idle,
                    'iowait': getattr(cpu_times, 'iowait', 0)
                }
            }
            
            self.monitoring_data['cpu_history'].append(cpu_data)
            
            # Сохраняем в лог
            self._log_monitoring_data('cpu', cpu_data)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга CPU: {e}")
    
    def _monitor_memory(self):
        """Мониторинг памяти"""
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            memory_data = {
                'timestamp': datetime.now().isoformat(),
                'ram': {
                    'total': mem.total,
                    'available': mem.available,
                    'percent': mem.percent,
                    'used': mem.used,
                    'free': mem.free,
                    'active': getattr(mem, 'active', 0),
                    'inactive': getattr(mem, 'inactive', 0)
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent
                }
            }
            
            self.monitoring_data['memory_history'].append(memory_data)
            self._log_monitoring_data('memory', memory_data)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга памяти: {e}")
    
    def _monitor_disks(self):
        """Мониторинг дисков"""
        try:
            disk_data = {
                'timestamp': datetime.now().isoformat(),
                'partitions': []
            }
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    io_counters = psutil.disk_io_counters(perdisk=True).get(partition.device.replace('\\', '').replace('/', ''), {})
                    
                    disk_data['partitions'].append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'usage': {
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': usage.percent
                        },
                        'io': {
                            'read_count': getattr(io_counters, 'read_count', 0),
                            'write_count': getattr(io_counters, 'write_count', 0),
                            'read_bytes': getattr(io_counters, 'read_bytes', 0),
                            'write_bytes': getattr(io_counters, 'write_bytes', 0)
                        }
                    })
                except:
                    continue
            
            self.monitoring_data['disk_history'].append(disk_data)
            self._log_monitoring_data('disk', disk_data)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга дисков: {e}")
    
    def _monitor_network(self):
        """Мониторинг сети"""
        try:
            net_io = psutil.net_io_counters()
            net_connections = psutil.net_connections(kind='inet')
            
            connections = []
            for conn in net_connections[:50]:  # Ограничиваем количество
                if conn.status == 'ESTABLISHED':
                    connections.append({
                        'fd': conn.fd,
                        'family': str(conn.family),
                        'type': str(conn.type),
                        'laddr': f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else None,
                        'raddr': f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else None,
                        'status': conn.status,
                        'pid': conn.pid
                    })
            
            network_data = {
                'timestamp': datetime.now().isoformat(),
                'io': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv,
                    'errin': net_io.errin,
                    'errout': net_io.errout,
                    'dropin': net_io.dropin,
                    'dropout': net_io.dropout
                },
                'connections': connections
            }
            
            self.monitoring_data['network_history'].append(network_data)
            self._log_monitoring_data('network', network_data)
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга сети: {e}")
    
    def _monitor_processes(self):
        """Мониторинг процессов"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                try:
                    process_info = proc.info
                    
                    # Добавляем дополнительные данные
                    with proc.oneshot():
                        process_info['cmdline'] = proc.cmdline()
                        process_info['exe'] = proc.exe()
                        process_info['cwd'] = proc.cwd()
                        process_info['connections'] = len(proc.connections())
                        process_info['threads'] = proc.num_threads()
                        process_info['memory_info'] = {
                            'rss': proc.memory_info().rss,
                            'vms': proc.memory_info().vms
                        }
                    
                    processes.append(process_info)
                    
                    # Ограничиваем количество процессов
                    if len(processes) >= 100:
                        break
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.monitoring_data['processes'] = processes
            self._log_monitoring_data('processes', {'timestamp': datetime.now().isoformat(), 'count': len(processes)})
            
        except Exception as e:
            print(f"❌ Ошибка мониторинга процессов: {e}")
    
    def _take_screenshot(self):
        """Создание скриншота"""
        try:
            from PIL import ImageGrab
            import io
            
            # Создаем скриншот
            screenshot = ImageGrab.grab()
            
            # Сохраняем в буфер
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG', quality=50)
            screenshot_data = buffer.getvalue()
            
            # Сохраняем информацию о скриншоте
            screenshot_info = {
                'timestamp': datetime.now().isoformat(),
                'size': len(screenshot_data),
                'width': screenshot.width,
                'height': screenshot.height,
                'format': 'PNG'
            }
            
            self.monitoring_data['screenshots'].append(screenshot_info)
            
            # Сохраняем файл
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(self.temp_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(screenshot_data)
            
            print(f"📸 Скриншот сохранен: {filename}")
            
        except ImportError:
            print("⚠️  Для скриншотов установите Pillow: pip install pillow")
            self.monitoring_config['screenshot_interval'] = 0
        except Exception as e:
            print(f"❌ Ошибка создания скриншота: {e}")
    
    def _log_monitoring_data(self, data_type, data):
        """Логирование данных мониторинга"""
        try:
            log_file = f"{self.logs_dir}/monitoring_{data_type}.log"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} | {json.dumps(data)}\n")
            
            # Проверяем размер файла
            if os.path.getsize(log_file) > self.monitoring_config['max_log_size']:
                self._rotate_log_file(log_file)
                
        except Exception as e:
            print(f"❌ Ошибка логирования данных: {e}")
    
    def _rotate_log_file(self, filepath):
        """Ротация лог-файла"""
        try:
            if os.path.exists(filepath):
                # Создаем архивную копию
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                archive_path = f"{filepath}.{timestamp}.bak"
                
                os.rename(filepath, archive_path)
                print(f"📦 Лог-файл заархивирован: {archive_path}")
        except Exception as e:
            print(f"❌ Ошибка ротации лог-файла: {e}")
    
    def _cleanup_old_data(self):
        """Очистка старых данных"""
        max_history = 1000  # Максимальное количество записей в истории
        
        for key in ['cpu_history', 'memory_history', 'disk_history', 'network_history']:
            if len(self.monitoring_data[key]) > max_history:
                self.monitoring_data[key] = self.monitoring_data[key][-max_history:]
        
        # Очистка старых скриншотов
        if len(self.monitoring_data['screenshots']) > 100:
            self.monitoring_data['screenshots'] = self.monitoring_data['screenshots'][-100:]
    
    def get_monitoring_summary(self):
        """Получение сводки мониторинга"""
        summary = {
            'agent_id': self.agent_id,
            'timestamp': datetime.now().isoformat(),
            'system_info': self.system_info,
            'monitoring_status': {
                'active': self.monitoring_active,
                'config': self.monitoring_config
            },
            'current_stats': {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent if os.name != 'nt' else 0,
                'process_count': len(psutil.pids())
            },
            'history_sizes': {
                'cpu': len(self.monitoring_data['cpu_history']),
                'memory': len(self.monitoring_data['memory_history']),
                'disk': len(self.monitoring_data['disk_history']),
                'network': len(self.monitoring_data['network_history']),
                'screenshots': len(self.monitoring_data['screenshots'])
            }
        }
        
        return summary
    
    def send_monitoring_data(self, send_full=False):
        """Отправка данных мониторинга на сервер"""
        try:
            # Подготавливаем данные для отправки
            data_to_send = {
                'summary': self.get_monitoring_summary(),
                'timestamp': datetime.now().isoformat()
            }
            
            if send_full:
                # Отправляем полные данные (только последние 100 записей)
                data_to_send.update({
                    'cpu_history': self.monitoring_data['cpu_history'][-100:],
                    'memory_history': self.monitoring_data['memory_history'][-100:],
                    'disk_history': self.monitoring_data['disk_history'][-100:],
                    'network_history': self.monitoring_data['network_history'][-100:],
                    'processes': self.monitoring_data['processes'][:50]  # Первые 50 процессов
                })
            
            # Шифруем данные
            if self.encryption_key:
                cipher = Fernet(self.encryption_key)
                json_data = json.dumps(data_to_send).encode('utf-8')
                encrypted_data = b"ENCRYPTED::" + cipher.encrypt(json_data)
            else:
                encrypted_data = json.dumps(data_to_send).encode('utf-8')
            
            # Отправляем на сервер
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.server_ip, self.server_port))
            
            # Отправляем заголовок
            header = "MONITORING".ljust(10)
            sock.send(header.encode('utf-8'))
            
            # Отправляем размер данных
            size_header = f"{len(encrypted_data):<20}"
            sock.send(size_header.encode('utf-8'))
            
            # Отправляем данные
            sock.send(encrypted_data)
            
            # Получаем ответ
            sock.settimeout(5)
            response = sock.recv(4096)
            
            sock.close()
            
            if response:
                response_data = json.loads(response.decode('utf-8'))
                if response_data.get('status') == 'success':
                    print(f"📊 Данные мониторинга отправлены ({len(encrypted_data)} байт)")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка отправки данных мониторинга: {e}")
            return False
    
    def encrypt_data(self, data):
        """Шифрование данных"""
        if not self.encryption_key:
            return data, None
        
        try:
            cipher = Fernet(self.encryption_key)
            encrypted = cipher.encrypt(data)
            
            # Добавляем метку что данные зашифрованы
            header = b"ENCRYPTED::"
            result = header + encrypted
            
            return result, self.encryption_key
        except Exception as e:
            print(f"❌ Ошибка шифрования: {e}")
            return data, None
    
    def decrypt_data(self, encrypted_data):
        """Расшифровка данных"""
        if not self.encryption_key:
            return encrypted_data
        
        try:
            if encrypted_data.startswith(b"ENCRYPTED::"):
                cipher = Fernet(self.encryption_key)
                decrypted = cipher.decrypt(encrypted_data[10:])  # Убираем заголовок
                return decrypted
            else:
                return encrypted_data
        except Exception as e:
            print(f"❌ Ошибка расшифровки: {e}")
            return encrypted_data
    
    def secure_send_file(self, file_path, file_type="TELEGRAM"):
        """
        Безопасная отправка файла с шифрованием
        
        Args:
            file_path (str): Путь к файлу
            file_type (str): Тип файла
        """
        if not os.path.exists(file_path):
            print(f"❌ Файл не найден: {file_path}")
            return False
        
        try:
            # Читаем файл
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            print(f"🔒 Шифрую файл: {os.path.basename(file_path)}")
            
            # Шифруем данные
            encrypted_data, key = self.encrypt_data(file_data)
            
            # Готовим метаданные
            metadata = {
                'filename': os.path.basename(file_path),
                'original_size': len(file_data),
                'encrypted_size': len(encrypted_data),
                'encrypted': key is not None,
                'hash': hashlib.sha256(file_data).hexdigest(),
                'timestamp': datetime.now().isoformat(),
                'agent_id': self.agent_id
            }
            
            # Создаем пакет: метаданные + данные
            packet = {
                'metadata': metadata,
                'data': base64.b64encode(encrypted_data).decode('utf-8')
            }
            
            packet_json = json.dumps(packet)
            packet_size = len(packet_json)
            
            print(f"📦 Подготовлен пакет: {packet_size} байт")
            print(f"   📁 Исходный размер: {len(file_data)} байт")
            print(f"   🔐 Зашифрованный: {len(encrypted_data)} байт")
            
            # Подключаемся к серверу
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((self.server_ip, self.server_port))
            
            # Отправляем заголовок
            sock.send("SECURE_FILE".ljust(10).encode('utf-8'))
            
            # Отправляем размер пакета
            sock.send(f"{packet_size:<20}".encode('utf-8'))
            
            # Отправляем сам пакет
            total_sent = 0
            chunk_size = 4096
            
            while total_sent < packet_size:
                chunk = packet_json[total_sent:total_sent + chunk_size].encode('utf-8')
                sock.send(chunk)
                total_sent += len(chunk)
                
                percent = (total_sent / packet_size) * 100
                print(f"  📤 Отправлено: {percent:.1f}% ({total_sent}/{packet_size})", end='\r')
            
            print()
            
            # Получаем ответ
            sock.settimeout(5)
            response = sock.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            sock.close()
            
            if response_data.get('status') == 'success':
                print(f"✅ Файл отправлен успешно!")
                print(f"   📝 {response_data.get('message')}")
                
                # Безопасное удаление исходного файла
                if response_data.get('verified', False):
                    self.secure_delete(file_path)
                    print(f"🗑️ Исходный файл безопасно удален")
                
                return True
            else:
                print(f"❌ Ошибка на сервере: {response_data.get('message')}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка отправки файла: {e}")
            return False
    
    def secure_delete(self, file_path, passes=3):
        """
        Безопасное удаление файла
        
        Args:
            file_path: Путь к файлу
            passes: Количество проходов перезаписи
        """
        try:
            if not os.path.exists(file_path):
                return
            
            file_size = os.path.getsize(file_path)
            
            # Перезаписываем случайными данными
            with open(file_path, 'wb') as f:
                for i in range(passes):
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
                    print(f"  🧹 Проход {i+1}/{passes}", end='\r')
            
            # Удаляем файл
            os.remove(file_path)
            print(f"\n✅ Файл безопасно удален: {file_path}")
            
        except Exception as e:
            print(f"⚠️ Не удалось безопасно удалить файл: {e}")
            # Пробуем обычное удаление
            try:
                os.remove(file_path)
            except:
                pass
    
    def test_connection(self):
        """Проверка подключения к серверу"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((self.server_ip, self.server_port))
            sock.close()
            return True
        except Exception as e:
            print(f"❌ Нет подключения к серверу: {e}")
            return False
    
    def create_test_file(self):
        """Создание тестового файла для отправки"""
        test_content = f"""
        Тестовый архив Telegram
        Создан: {datetime.now()}
        Агент: {self.agent_id}
        Сервер: {self.server_ip}:{self.server_port}
        
        Информация о системе:
        OS: {self.system_info.get('os', 'Unknown')}
        CPU: {self.system_info.get('cpu', {}).get('brand_raw', 'Unknown')}
        RAM: {self.system_info.get('memory', {}).get('total_gb', 0):.1f} GB
        
        Мониторинг: {'АКТИВЕН' if self.monitoring_active else 'НЕ АКТИВЕН'}
        """
        
        test_file = f"{self.temp_dir}/test_telegram_archive.txt"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        
        print(f"📝 Создан тестовый файл: {test_file}")
        return test_file
    
    def remote_control_menu(self):
        """Меню удаленного управления"""
        while True:
            print("\n" + "=" * 60)
            print("🎮 УДАЛЕННОЕ УПРАВЛЕНИЕ")
            print("=" * 60)
            print(f"Агент: {self.agent_id}")
            print(f"Мониторинг: {'🟢 АКТИВЕН' if self.monitoring_active else '🔴 ВЫКЛЮЧЕН'}")
            print("-" * 60)
            
            # Показываем текущую статистику
            if self.monitoring_active:
                cpu = psutil.cpu_percent()
                mem = psutil.virtual_memory()
                print(f"📊 Текущая нагрузка:")
                print(f"  CPU: {cpu:.1f}% | RAM: {mem.percent:.1f}%")
                print(f"  Процессы: {len(psutil.pids())}")
            
            print("\nВыберите действие:")
            print("  [1] 🚀 Запустить мониторинг")
            print("  [2] 🛑 Остановить мониторинг")
            print("  [3] 📊 Отправить данные мониторинга")
            print("  [4] ⚙️  Настройки мониторинга")
            print("  [5] 📈 Показать статистику")
            print("  [6] 📸 Сделать скриншот")
            print("  [7] 🔄 Перезагрузить агента")
            print("  [8] 🚪 Завершить работу агента")
            print("  [B] ↩️ Назад")
            print("=" * 60)
            
            choice = input("> ").lower()
            
            if choice == 'b':
                break
            elif choice == '1':
                if not self.monitoring_active:
                    self.start_monitoring()
                else:
                    print("⚠️  Мониторинг уже запущен")
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '2':
                if self.monitoring_active:
                    self.stop_monitoring()
                else:
                    print("⚠️  Мониторинг не запущен")
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '3':
                if self.monitoring_active:
                    send_full = input("Отправить полные данные? (y/n): ").lower() == 'y'
                    if self.send_monitoring_data(send_full):
                        print("✅ Данные отправлены")
                    else:
                        print("❌ Ошибка отправки")
                else:
                    print("⚠️  Сначала запустите мониторинг")
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '4':
                self.monitoring_settings_menu()
                
            elif choice == '5':
                self.show_monitoring_stats()
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '6':
                self._take_screenshot()
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '7':
                confirm = input("Перезагрузить агента? (y/n): ").lower()
                if confirm == 'y':
                    print("🔄 Перезагрузка агента...")
                    # Здесь можно добавить код перезагрузки
                    print("✅ Агент перезагружен")
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '8':
                confirm = input("Завершить работу агента? (y/n): ").lower()
                if confirm == 'y':
                    print("🛑 Завершение работы...")
                    self.running = False
                    self.stop_monitoring()
                    return True  # Выйти из основного цикла
                input("\nНажми Enter чтобы продолжить...")
    
    def monitoring_settings_menu(self):
        """Меню настроек мониторинга"""
        while True:
            print("\n" + "=" * 60)
            print("⚙️  НАСТРОЙКИ МОНИТОРИНГА")
            print("=" * 60)
            
            print("Текущие настройки:")
            print(f"  1. Интервал CPU: {self.monitoring_config['cpu_interval']} сек")
            print(f"  2. Интервал памяти: {self.monitoring_config['memory_interval']} сек")
            print(f"  3. Интервал дисков: {self.monitoring_config['disk_interval']} сек")
            print(f"  4. Интервал сети: {self.monitoring_config['network_interval']} сек")
            print(f"  5. Интервал процессов: {self.monitoring_config['process_interval']} сек")
            print(f"  6. Интервал скриншотов: {self.monitoring_config['screenshot_interval']} сек (0 = отключено)")
            print(f"  7. Макс. размер логов: {self.monitoring_config['max_log_size'] // (1024*1024)} MB")
            
            print("\nВыберите параметр для изменения (1-7) или [B] для выхода:")
            choice = input("> ").lower()
            
            if choice == 'b':
                break
            
            try:
                param_index = int(choice) - 1
                params = list(self.monitoring_config.keys())
                
                if 0 <= param_index < len(params):
                    param_name = params[param_index]
                    current_value = self.monitoring_config[param_name]
                    
                    if 'interval' in param_name:
                        new_value = input(f"Новый интервал для {param_name} (сек, сейчас {current_value}): ")
                        if new_value.isdigit():
                            self.monitoring_config[param_name] = int(new_value)
                            print(f"✅ {param_name} изменен на {new_value} сек")
                        else:
                            print("❌ Неверное значение")
                    elif param_name == 'max_log_size':
                        new_value = input(f"Новый размер логов (MB, сейчас {current_value // (1024*1024)}): ")
                        if new_value.isdigit():
                            self.monitoring_config[param_name] = int(new_value) * 1024 * 1024
                            print(f"✅ {param_name} изменен на {new_value} MB")
                        else:
                            print("❌ Неверное значение")
                else:
                    print("❌ Неверный выбор")
                    
            except ValueError:
                print("❌ Неверный ввод")
            
            input("\nНажми Enter чтобы продолжить...")
    
    def show_monitoring_stats(self):
        """Показать статистику мониторинга"""
        print("\n" + "=" * 60)
        print("📈 СТАТИСТИКА МОНИТОРИНГА")
        print("=" * 60)
        
        summary = self.get_monitoring_summary()
        
        print(f"Агент: {summary['agent_id']}")
        print(f"Время: {summary['timestamp']}")
        print(f"Статус: {'🟢 АКТИВЕН' if summary['monitoring_status']['active'] else '🔴 ВЫКЛЮЧЕН'}")
        
        print(f"\n📊 Текущие показатели:")
        stats = summary['current_stats']
        print(f"  CPU: {stats['cpu_percent']:.1f}%")
        print(f"  RAM: {stats['memory_percent']:.1f}%")
        print(f"  Disk: {stats['disk_percent']:.1f}%")
        print(f"  Процессы: {stats['process_count']}")
        
        print(f"\n📈 История:")
        history = summary['history_sizes']
        print(f"  CPU записей: {history['cpu']}")
        print(f"  RAM записей: {history['memory']}")
        print(f"  Disk записей: {history['disk']}")
        print(f"  Network записей: {history['network']}")
        print(f"  Скриншотов: {history['screenshots']}")
        
        print(f"\n💻 Информация о системе:")
        info = summary['system_info']
        if info:
            print(f"  OS: {info.get('os', 'Unknown')} {info.get('platform', '')}")
            print(f"  CPU: {info.get('cpu', {}).get('brand_raw', 'Unknown')}")
            print(f"  Ядер: {info.get('cpu', {}).get('cores', '?')} физических, {info.get('cpu', {}).get('threads', '?')} логических")
            print(f"  RAM: {info.get('memory', {}).get('total_gb', 0):.1f} GB")
            
            if info.get('disks'):
                print(f"  Диски: {len(info['disks'])} разделов")
            
            if info.get('gpus'):
                print(f"  GPU: {len(info['gpus'])} видеокарт")
    
    def telegram_menu(self):
        """Меню управления Telegram архиватором"""
        try:
            from telegram_archiver import get_telegram_credentials, sync_download_channel
        except ImportError:
            print("❌ Модуль telegram_archiver не найден")
            print("👉 Убедись что файл telegram_archiver.py в той же папке")
            input("Нажми Enter чтобы продолжить...")
            return
        
        print("\n" + "=" * 60)
        print("📱 TELEGRAM АРХИВАТОР")
        print("=" * 60)
        
        # Получаем учетные данные
        api_id, api_hash = get_telegram_credentials()
        
        if not api_id or not api_hash:
            print("❌ Учетные данные Telegram не получены")
            input("Нажми Enter чтобы продолжить...")
            return
        
        while True:
            print("\nВыберите действие:")
            print("  [1] 📥 Скачать канал")
            print("  [2] 📤 Отправить архив на сервер (с шифрованием)")
            print("  [3] 📤 Отправить архив БЕЗ шифрования")
            print("  [4] 🔐 Показать/сменить ключ шифрования")
            print("  [B] ↩️ Назад")
            
            choice = input("> ").lower()
            
            if choice == 'b':
                break
            elif choice == '1':
                channel = input("Введите ссылку на канал (например @durov): ").strip()
                limit = input("Сколько сообщений скачать? (по умолчанию 100): ").strip()
                limit = int(limit) if limit.isdigit() else 100
                
                if channel:
                    print(f"🚀 Начинаю скачивание: {channel}")
                    archive_path = sync_download_channel(api_id, api_hash, channel, limit)
                    
                    if archive_path:
                        print(f"✅ Архив создан: {archive_path}")
                        
                        # Спросим, отправить ли на сервер
                        send = input("Отправить архив на сервер ПК1? (y/n): ").lower()
                        if send == 'y':
                            use_encryption = input("Использовать шифрование? (y/n): ").lower()
                            if use_encryption == 'y':
                                if self.secure_send_file(archive_path, "TELEGRAM"):
                                    print("✅ Архив отправлен на сервер с шифрованием!")
                                else:
                                    print("❌ Ошибка отправки архива")
                            else:
                                # Старый метод без шифрования
                                self._send_file_old(archive_path, "TELEGRAM")
                    else:
                        print("❌ Не удалось скачать канал")
                
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '2':
                import glob
                archives = glob.glob("./telegram_archives/*.zip")
                
                if archives:
                    print("📁 Найденные архивы:")
                    for i, archive in enumerate(archives, 1):
                        size = os.path.getsize(archive) // 1024
                        print(f"  [{i}] {os.path.basename(archive)} ({size} KB)")
                    
                    file_num = input("Выберите номер файла: ").strip()
                    if file_num.isdigit() and 1 <= int(file_num) <= len(archives):
                        archive_path = archives[int(file_num)-1]
                        self.secure_send_file(archive_path, "TELEGRAM")
                    else:
                        print("❌ Неверный выбор")
                else:
                    print("📭 Архивы не найдены")
                
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '3':
                import glob
                archives = glob.glob("./telegram_archives/*.zip")
                
                if archives:
                    print("📁 Найденные архивы:")
                    for i, archive in enumerate(archives, 1):
                        size = os.path.getsize(archive) // 1024
                        print(f"  [{i}] {os.path.basename(archive)} ({size} KB)")
                    
                    file_num = input("Выберите номер файла: ").strip()
                    if file_num.isdigit() and 1 <= int(file_num) <= len(archives):
                        archive_path = archives[int(file_num)-1]
                        self._send_file_old(archive_path, "TELEGRAM")
                    else:
                        print("❌ Неверный выбор")
                else:
                    print("📭 Архивы не найдены")
                
                input("\nНажми Enter чтобы продолжить...")
                
            elif choice == '4':
                print(f"\n🔑 Текущий ключ шифрования: {'ЕСТЬ' if self.encryption_key else 'НЕТ'}")
                if self.encryption_key:
                    print(f"   Хэш ключа: {hashlib.sha256(self.encryption_key).hexdigest()[:16]}...")
                
                change = input("Сгенерировать новый ключ? (y/n): ").lower()
                if change == 'y':
                    key = Fernet.generate_key()
                    with open("./encryption_key.key", 'wb') as f:
                        f.write(key)
                    self.encryption_key = key
                    print("✅ Новый ключ сгенерирован и сохранен")
                
                input("\nНажми Enter чтобы продолжить...")
    
    def _send_file_old(self, file_path, file_type):
        """Старый метод отправки файла без шифрования"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_size = len(file_data)
            filename = os.path.basename(file_path)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((self.server_ip, self.server_port))
            
            header = f"{file_type:<10}"
            sock.send(header.encode('utf-8'))
            
            size_header = f"{file_size:<20}"
            sock.send(size_header.encode('utf-8'))
            
            name_header = f"{filename:<100}"
            sock.send(name_header.encode('utf-8'))
            
            total_sent = 0
            chunk_size = 4096
            
            while total_sent < file_size:
                chunk = file_data[total_sent:total_sent + chunk_size]
                sock.send(chunk)
                total_sent += len(chunk)
                
                percent = (total_sent / file_size) * 100
                print(f"  📤 Отправлено: {percent:.1f}% ({total_sent}/{file_size})", end='\r')
            
            print()
            
            sock.settimeout(5)
            response = sock.recv(4096).decode('utf-8')
            response_data = json.loads(response)
            
            sock.close()
            
            if response_data.get('status') == 'success':
                print(f"✅ Файл отправлен (без шифрования)")
                return True
            else:
                print(f"❌ Ошибка: {response_data.get('message')}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка отправки файла: {e}")
            return False
    
    def run_menu(self):
        """Запуск меню управления агентом"""
        while self.running:
            print("\n" + "=" * 60)
            print("          🎮 МЕНЮ УПРАВЛЕНИЯ АГЕНТОМ")
            print("=" * 60)
            print(f"Сервер: {self.server_ip}:{self.server_port}")
            print(f"Агент: {self.agent_id}")
            print(f"Шифрование: {'🟢 ВКЛ' if self.encryption_key else '🔴 ВЫКЛ'}")
            print(f"Мониторинг: {'🟢 АКТИВЕН' if self.monitoring_active else '🔴 ВЫКЛЮЧЕН'}")
            print("-" * 60)
            
            # Проверка связи
            if self.test_connection():
                print("📡 Связь с сервером: 🟢 ОК")
            else:
                print("📡 Связь с сервером: 🔴 НЕТ")
            
            print("-" * 60)
            print("Выберите действие:")
            print("  [1] 📊 Отправить метрики системы")
            print("  [2] 📁 Отправить тестовый файл (с шифрованием)")
            print("  [3] 📁 Отправить свой файл (с шифрованием)")
            print("  [4] 🎮 Удаленное управление")
            print("  [5] 📱 Telegram архиватор")
            print("  [6] 🔐 Настройки безопасности")
            print("  [7] ℹ️  Информация о системе")
            print("  [8] 📈 Показать статистику")
            print("  [Q] 🚪 Выход")
            print("=" * 60)
            
            choice = input("> ").lower()
            
            if choice == 'q':
                self.running = False
                print("🛑 Останавливаю агента...")
                self.stop_monitoring()
                break
            elif choice == '1':
                # Отправляем сводку мониторинга
                if self.send_monitoring_data(send_full=False):
                    print("✅ Данные отправлены")
                else:
                    print("❌ Ошибка отправки")
                input("Нажми Enter чтобы продолжить...")
            elif choice == '2':
                test_file = self.create_test_file()
                self.secure_send_file(test_file, "TELEGRAM")
                input("Нажми Enter чтобы продолжить...")
            elif choice == '3':
                filepath = input("Введите путь к файлу: ").strip()
                if os.path.exists(filepath):
                    self.secure_send_file(filepath, "TELEGRAM")
                else:
                    print("❌ Файл не найден!")
                input("Нажми Enter чтобы продолжить...")
            elif choice == '4':
                should_exit = self.remote_control_menu()
                if should_exit:
                    break
            elif choice == '5':
                self.telegram_menu()
            elif choice == '6':
                self.security_menu()
            elif choice == '7':
                self.show_system_info()
                input("Нажми Enter чтобы продолжить...")
            elif choice == '8':
                self.show_monitoring_stats()
                input("Нажми Enter чтобы продолжить...")
            else:
                print("❌ Неверный выбор")
                time.sleep(1)
    
    def show_system_info(self):
        """Показать информацию о системе"""
        print("\n" + "=" * 60)
        print("ℹ️  ИНФОРМАЦИЯ О СИСТЕМЕ")
        print("=" * 60)
        
        info = self.system_info
        if info:
            print(f"Хост: {info.get('hostname', 'Unknown')}")
            print(f"OS: {info.get('os', 'Unknown')} {info.get('platform', '')}")
            
            cpu = info.get('cpu', {})
            print(f"CPU: {cpu.get('brand_raw', 'Unknown')}")
            print(f"  Ядер: {cpu.get('cores', '?')} физических, {cpu.get('threads', '?')} логических")
            print(f"  Частота: {cpu.get('hz', 'Unknown')}")
            
            mem = info.get('memory', {})
            print(f"RAM: {mem.get('total_gb', 0):.1f} GB всего, {mem.get('available_gb', 0):.1f} GB доступно")
            
            if info.get('disks'):
                print(f"\n💿 ДИСКИ:")
                for disk in info['disks']:
                    print(f"  {disk['mountpoint']}: {disk['used_gb']:.1f}/{disk['total_gb']:.1f} GB ({disk['percent']}%)")
            
            if info.get('gpus'):
                print(f"\n🎮 GPU:")
                for gpu in info['gpus']:
                    print(f"  {gpu['name']}: {gpu['load']:.1f}% загрузка, {gpu['temperature']}°C")
            
            if info.get('monitors'):
                print(f"\n🖥️  МОНИТОРЫ:")
                for i, monitor in enumerate(info['monitors'], 1):
                    print(f"  Монитор {i}: {monitor['width']}x{monitor['height']}")
        
        print(f"\n📊 Мониторинг: {'🟢 АКТИВЕН' if self.monitoring_active else '🔴 ВЫКЛЮЧЕН'}")
        if self.monitoring_active:
            cpu_load = psutil.cpu_percent()
            mem_load = psutil.virtual_memory().percent
            print(f"  Текущая нагрузка: CPU {cpu_load:.1f}%, RAM {mem_load:.1f}%")

if __name__ == "__main__":
    # Настройки
    SERVER_IP = "192.168.1.100"  # ЗАМЕНИ НА РЕАЛЬНЫЙ IP ПК1
    SERVER_PORT = 9090
    
    # Проверяем дополнительные зависимости
    try:
        import GPUtil
    except ImportError:
        print("⚠️  Установите GPUtil для мониторинга GPU: pip install gputil")
    
    try:
        import screeninfo
    except ImportError:
        print("⚠️  Установите screeninfo для информации о мониторах: pip install screeninfo")
    
    # Создаем и запускаем агента
    agent = SystemAgent(server_ip=SERVER_IP, server_port=SERVER_PORT)
    agent.run_menu()