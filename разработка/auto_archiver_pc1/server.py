"""
Главный сервер системы на ПК1
Принимает архивы Telegram от агентов (ПК2, ПК3...)
"""
import socket
import json
import os
import time
from datetime import datetime
import threading

class MasterServer:
    def __init__(self, host='0.0.0.0', port=9090):
        """
        Инициализация сервера
        
        Args:
            host (str): IP адрес для прослушивания (0.0.0.0 = все интерфейсы)
            port (int): Порт для прослушивания
        """
        self.host = host
        self.port = port
        self.clients = {}  # Словарь подключенных клиентов: {ip: время_подключения}
        self.running = True
        
        # Пути для хранения
        self.base_storage = "./storage"
        self.telegram_storage = f"{self.base_storage}/telegram"
        self.logs_path = f"{self.base_storage}/logs"
        
        # Создаем структуру папок
        self._create_folders()
        
        print("=" * 60)
        print("🚀 АВТОНОМНАЯ СИСТЕМА УПРАВЛЕНИЯ - ГЛАВНЫЙ СЕРВЕР")
        print("=" * 60)
        print(f"📡 Сервер запускается на {self.host}:{self.port}")
        print(f"💾 Хранилище: {os.path.abspath(self.base_storage)}")
        print("=" * 60)
    
    def _create_folders(self):
        """Создание структуры папок"""
        folders = [self.base_storage, self.telegram_storage, self.logs_path]
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
            print(f"📁 Создана папка: {folder}")
    
    def log_event(self, message, level="INFO"):
        """
        Логирование событий в консоль и файл
        
        Args:
            message (str): Сообщение для логирования
            level (str): Уровень логирования (INFO, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        
        # Вывод в консоль
        print(log_msg)
        
        # Сохранение в файл
        log_file = f"{self.logs_path}/server_{datetime.now().strftime('%Y%m%d')}.log"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
        except Exception as e:
            print(f"❌ Ошибка записи лога: {e}")
    
    def handle_client(self, client_socket, address):
        """
        Обработка подключения от агента
        
        Args:
            client_socket: Сокет клиента
            address: Адрес клиента (ip, port)
        """
        client_ip = address[0]
        client_port = address[1]
        
        self.clients[client_ip] = datetime.now().strftime("%H:%M:%S")
        self.log_event(f"🔗 Новое подключение от {client_ip}:{client_port}")
        
        try:
            # Получаем тип данных (первые 10 байт - заголовок)
            header = client_socket.recv(10).decode('utf-8').strip()
            
            if header == "TELEGRAM":
                self.log_event(f"📱 Принимаю Telegram архив от {client_ip}")
                self._receive_telegram_archive(client_socket, client_ip)
            elif header == "METRICS":
                self.log_event(f"📊 Принимаю метрики от {client_ip}")
                self._receive_metrics(client_socket, client_ip)
            elif header == "COMMAND_R":
                self.log_event(f"📝 Принимаю результат команды от {client_ip}")
                self._receive_command_result(client_socket, client_ip)
            else:
                self.log_event(f"⚠️ Неизвестный тип данных от {client_ip}: {header}", "WARNING")
                
        except Exception as e:
            self.log_event(f"❌ Ошибка обработки клиента {client_ip}: {e}", "ERROR")
        finally:
            # Закрываем соединение
            client_socket.close()
            if client_ip in self.clients:
                del self.clients[client_ip]
            self.log_event(f"🔌 Отключен клиент {client_ip}")
    
    def _receive_telegram_archive(self, client_socket, client_ip):
        """
        Прием Telegram архива
        
        Args:
            client_socket: Сокет клиента
            client_ip: IP клиента
        """
        try:
            # Получаем размер данных (следующие 20 байт)
            size_data = client_socket.recv(20).decode('utf-8').strip()
            data_size = int(size_data)
            
            self.log_event(f"📦 Размер архива: {data_size} байт")
            
            # Получаем имя файла (следующие 100 байт)
            filename_data = client_socket.recv(100).decode('utf-8').strip()
            original_filename = filename_data
            
            # Генерируем уникальное имя файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_filename = f"{client_ip}_{timestamp}_{original_filename}"
            save_path = f"{self.telegram_storage}/{save_filename}"
            
            # Получаем сами данные
            received = 0
            with open(save_path, "wb") as f:
                while received < data_size:
                    chunk = client_socket.recv(min(4096, data_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            self.log_event(f"✅ Архив сохранен: {save_filename} ({received} байт)")
            
            # Отправляем подтверждение
            response = json.dumps({
                "status": "success",
                "message": f"Архив получен и сохранен как {save_filename}",
                "size": received,
                "timestamp": timestamp
            })
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            error_msg = f"❌ Ошибка приема архива от {client_ip}: {e}"
            self.log_event(error_msg, "ERROR")
            client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
    
    def _receive_metrics(self, client_socket, client_ip):
        """Прием метрик системы от агента"""
        try:
            # Получаем JSON с метриками
            metrics_json = client_socket.recv(4096).decode('utf-8')
            metrics = json.loads(metrics_json)
            
            # Сохраняем метрики
            metrics_file = f"{self.base_storage}/metrics_{client_ip}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(metrics_file, "a", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "ip": client_ip,
                    "metrics": metrics
                }, f)
                f.write("\n")
            
            self.log_event(f"📊 Получены метрики от {client_ip}: CPU={metrics.get('cpu_percent', 0)}%, RAM={metrics.get('memory_percent', 0)}%")
            
        except Exception as e:
            self.log_event(f"❌ Ошибка приема метрик: {e}", "ERROR")
    
    def _receive_command_result(self, client_socket, client_ip):
        """Прием результата выполнения команды"""
        try:
            result_json = client_socket.recv(8192).decode('utf-8')
            result = json.loads(result_json)
            
            self.log_event(f"📝 Результат команды от {client_ip}: {result.get('command', 'unknown')}")
            
            # Сохраняем результат
            result_file = f"{self.logs_path}/commands_{datetime.now().strftime('%Y%m%d')}.log"
            with open(result_file, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {client_ip}: {result}\n")
                
        except Exception as e:
            self.log_event(f"❌ Ошибка приема результата: {e}", "ERROR")
    
    def show_dashboard(self):
        """Показать простую консольную панель управления"""
        while self.running:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("=" * 60)
            print("          🖥 ПАНЕЛЬ УПРАВЛЕНИЯ СЕРВЕРОМ")
            print("=" * 60)
            print(f"Статус: {'🟢 ЗАПУЩЕН' if self.running else '🔴 ОСТАНОВЛЕН'}")
            print(f"Порт: {self.port}")
            print(f"Клиентов онлайн: {len(self.clients)}")
            print("-" * 60)
            
            if self.clients:
                print("📡 Подключенные агенты:")
                for ip, connect_time in self.clients.items():
                    print(f"  • {ip} (подключен в {connect_time})")
            else:
                print("📡 Нет подключенных агентов")
            
            print("-" * 60)
            print("📂 Хранилище:")
            if os.path.exists(self.telegram_storage):
                files = os.listdir(self.telegram_storage)
                print(f"  • Telegram архивов: {len(files)}")
                if files:
                    print(f"  • Последний: {files[-1][:30]}...")
            
            print("-" * 60)
            print("Команды: [S] Статус | [L] Логи | [C] Очистка экрана | [Q] Выход")
            print("=" * 60)
            
            # Ждем ввод команды
            cmd = input("> ").lower()
            
            if cmd == 'q':
                self.running = False
                print("🛑 Останавливаю сервер...")
                break
            elif cmd == 'l':
                self._show_logs()
            elif cmd == 's':
                self._show_status()
            elif cmd == 'c':
                continue
    
    def _show_logs(self):
        """Показать последние логи"""
        log_file = f"{self.logs_path}/server_{datetime.now().strftime('%Y%m%d')}.log"
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()[-20:]  # Последние 20 строк
            print("\n" + "=" * 60)
            print("📋 ПОСЛЕДНИЕ ЛОГИ:")
            for line in lines:
                print(line.strip())
            input("\nНажми Enter чтобы продолжить...")
        else:
            print("📋 Логи еще не созданы")
            time.sleep(2)
    
    def _show_status(self):
        """Показать подробный статус"""
        print("\n" + "=" * 60)
        print("📊 СТАТУС СИСТЕМЫ:")
        
        # Размер хранилища
        total_size = 0
        if os.path.exists(self.telegram_storage):
            for file in os.listdir(self.telegram_storage):
                filepath = os.path.join(self.telegram_storage, file)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        
        print(f"  • Размер Telegram архивов: {total_size / (1024*1024):.2f} MB")
        print(f"  • Всего файлов: {len(os.listdir(self.telegram_storage)) if os.path.exists(self.telegram_storage) else 0}")
        print(f"  • Папка логов: {len(os.listdir(self.logs_path)) if os.path.exists(self.logs_path) else 0} файлов")
        
        input("\nНажми Enter чтобы продолжить...")
    
    def start(self):
        """Запуск сервера"""
        # Запускаем сервер в отдельном потоке
        server_thread = threading.Thread(target=self._run_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Запускаем панель управления в основном потоке
        self.show_dashboard()
    
    def _run_server(self):
        """Запуск TCP сервера"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)  # Максимум 5 подключений в очереди
            self.log_event(f"✅ Сервер запущен на {self.host}:{self.port}")
            
            while self.running:
                try:
                    # Ждем подключения (с таймаутом для проверки running)
                    server_socket.settimeout(1)
                    client_socket, address = server_socket.accept()
                    
                    # Обрабатываем клиента в отдельном потоке
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket, address))
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue  # Таймаут для проверки флага running
                except Exception as e:
                    self.log_event(f"❌ Ошибка accept: {e}", "ERROR")
                    
        except Exception as e:
            self.log_event(f"❌ Критическая ошибка сервера: {e}", "ERROR")
        finally:
            server_socket.close()
            self.log_event("🔴 Сервер остановлен")

if __name__ == "__main__":
    # Создаем и запускаем сервер
    server = MasterServer(port=9090)
    server.start()