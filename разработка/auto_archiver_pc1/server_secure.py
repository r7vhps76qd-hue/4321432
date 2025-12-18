"""
Главный сервер системы на ПК1 с поддержкой шифрования
"""
import socket
import json
import os
import base64
import hashlib
import hashlib
from datetime import datetime
import threading
from cryptography.fernet import Fernet, InvalidToken

class SecureMasterServer:
    def __init__(self, host='0.0.0.0', port=9090):
        self.host = host
        self.port = port
        self.clients = {}
        self.running = True
        
        # Хранилище
        self.base_storage = "./secure_storage"
        self.telegram_storage = f"{self.base_storage}/telegram"
        self.decrypted_storage = f"{self.base_storage}/decrypted"
        self.logs_path = f"{self.base_storage}/logs"
        self.keys_path = f"{self.base_storage}/keys"
        
        # Создаем структуру папок
        self._create_folders()
        
        # Загружаем ключи шифрования
        self.encryption_keys = self._load_encryption_keys()
        
        print("=" * 60)
        print("🚀 АВТОНОМНАЯ СИСТЕМА УПРАВЛЕНИЯ - ЗАЩИЩЕННЫЙ СЕРВЕР")
        print("=" * 60)
        print(f"📡 Сервер запускается на {self.host}:{self.port}")
        print(f"🔐 Загружено ключей: {len(self.encryption_keys)}")
        print(f"💾 Хранилище: {os.path.abspath(self.base_storage)}")
        print("=" * 60)
    
    def _create_folders(self):
        """Создание структуры папок"""
        folders = [
            self.base_storage,
            self.telegram_storage,
            self.decrypted_storage,
            self.logs_path,
            self.keys_path,
            f"{self.logs_path}/decrypted",
            f"{self.logs_path}/encrypted"
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
            print(f"📁 Создана папка: {folder}")
    
    def _load_encryption_keys(self):
        """Загрузка ключей шифрования из файлов"""
        keys = {}
        
        if os.path.exists(self.keys_path):
            for key_file in os.listdir(self.keys_path):
                if key_file.endswith('.key'):
                    try:
                        with open(os.path.join(self.keys_path, key_file), 'rb') as f:
                            key_data = f.read()
                            agent_id = key_file.replace('.key', '')
                            keys[agent_id] = key_data
                            print(f"🔑 Загружен ключ для агента: {agent_id}")
                    except Exception as e:
                        print(f"❌ Ошибка загрузки ключа {key_file}: {e}")
        
        return keys
    
    def _save_encryption_key(self, agent_id, key_data):
        """Сохранение ключа шифрования"""
        try:
            key_file = f"{self.keys_path}/{agent_id}.key"
            with open(key_file, 'wb') as f:
                f.write(key_data)
            
            self.encryption_keys[agent_id] = key_data
            print(f"💾 Сохранен ключ для агента: {agent_id}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения ключа: {e}")
            return False
    
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
    
    def handle_secure_file(self, client_socket, client_ip):
        """Обработка защищенных файлов"""
        try:
            # Получаем размер пакета
            size_data = client_socket.recv(20).decode('utf-8').strip()
            packet_size = int(size_data)
            
            self.log_event(f"📦 Размер пакета: {packet_size} байт", agent_id=client_ip)
            
            # Получаем сам пакет
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
            is_encrypted = metadata.get('encrypted', False)
            original_hash = metadata.get('hash', '')
            
            self.log_event(f"📁 Получен файл: {filename}", agent_id=agent_id)
            self.log_event(f"🔐 Зашифрован: {'✅ ДА' if is_encrypted else '❌ НЕТ'}", agent_id=agent_id)
            
            # Декодируем данные
            encrypted_data = base64.b64decode(encrypted_data_b64)
            
            # Сохраняем зашифрованную версию
            encrypted_filename = f"{agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}.enc"
            encrypted_path = f"{self.telegram_storage}/{encrypted_filename}"
            
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)
            
            self.log_event(f"💾 Сохранен зашифрованный файл: {encrypted_filename}", agent_id=agent_id)
            
            # Пытаемся расшифровать
            decrypted_data = None
            decryption_success = False
            
            if is_encrypted:
                # Пробуем расшифровать
                for key_agent_id, key_data in self.encryption_keys.items():
                    try:
                        cipher = Fernet(key_data)
                        
                        if encrypted_data.startswith(b"ENCRYPTED::"):
                            decrypted = cipher.decrypt(encrypted_data[10:])
                        else:
                            decrypted = cipher.decrypt(encrypted_data)
                        
                        # Проверяем хэш
                        computed_hash = hashlib.sha256(decrypted).hexdigest()
                        if computed_hash == original_hash:
                            decrypted_data = decrypted
                            decryption_success = True
                            self.log_event(f"✅ Успешно расшифровано ключом от {key_agent_id}", agent_id=agent_id)
                            break
                        else:
                            self.log_event(f"⚠️  Хэши не совпадают для ключа {key_agent_id}", "WARNING", agent_id)
                    except InvalidToken:
                        continue
                    except Exception as e:
                        self.log_event(f"⚠️  Ошибка расшифровки ключом {key_agent_id}: {e}", "WARNING", agent_id)
                
                if not decryption_success:
                    self.log_event("❌ Не удалось расшифровать файл", "ERROR", agent_id)
            else:
                # Файл не зашифрован
                decrypted_data = encrypted_data
                decryption_success = True
                self.log_event("📝 Файл не зашифрован", agent_id=agent_id)
            
            # Сохраняем расшифрованную версию
            if decryption_success and decrypted_data:
                decrypted_filename = f"{agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                decrypted_path = f"{self.decrypted_storage}/{decrypted_filename}"
                
                with open(decrypted_path, 'wb') as f:
                    f.write(decrypted_data)
                
                # Проверяем размер
                actual_size = len(decrypted_data)
                expected_size = metadata.get('original_size', 0)
                
                self.log_event(f"💾 Сохранен расшифрованный файл: {decrypted_filename}", agent_id=agent_id)
                self.log_event(f"📊 Размер: {actual_size} байт (ожидалось: {expected_size})", agent_id=agent_id)
                
                # Проверяем целостность
                if actual_size == expected_size:
                    self.log_event("✅ Целостность данных проверена", agent_id=agent_id)
                else:
                    self.log_event("⚠️  Размеры не совпадают!", "WARNING", agent_id)
            
            # Отправляем ответ
            response = {
                "status": "success",
                "message": f"Файл получен: {encrypted_filename}",
                "encrypted_file": encrypted_filename,
                "decrypted": decryption_success,
                "verified": decryption_success and decrypted_data is not None
            }
            
            client_socket.send(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            error_msg = f"❌ Ошибка обработки защищенного файла: {e}"
            self.log_event(error_msg, "ERROR", client_ip)
            
            try:
                client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
            except:
                pass
    
    def handle_client(self, client_socket, address):
        """Обработка подключения от агента"""
        client_ip = address[0]
        
        try:
            # Получаем заголовок (первые 10 байт)
            header = client_socket.recv(10).decode('utf-8').strip()
            
            if header == "SECURE_FILE":
                self.log_event(f"🔐 Принимаю защищенный файл от {client_ip}")
                self.handle_secure_file(client_socket, client_ip)
            elif header == "TELEGRAM":
                self._handle_legacy_telegram(client_socket, client_ip)
            elif header == "METRICS":
                self._handle_metrics(client_socket, client_ip)
            else:
                self.log_event(f"⚠️ Неизвестный заголовок: {header}", "WARNING", client_ip)
                
        except Exception as e:
            self.log_event(f"❌ Ошибка обработки клиента: {e}", "ERROR", client_ip)
        finally:
            client_socket.close()
            self.log_event(f"🔌 Отключен клиент {client_ip}")
    
    def _handle_legacy_telegram(self, client_socket, client_ip):
        """Обработка старых (незашифрованных) Telegram архивов"""
        try:
            size_data = client_socket.recv(20).decode('utf-8').strip()
            data_size = int(size_data)
            
            filename_data = client_socket.recv(100).decode('utf-8').strip()
            
            # Сохраняем в папку legacy
            legacy_path = f"{self.base_storage}/legacy"
            os.makedirs(legacy_path, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_filename = f"legacy_{client_ip}_{timestamp}_{filename_data}"
            save_path = f"{legacy_path}/{save_filename}"
            
            received = 0
            with open(save_path, "wb") as f:
                while received < data_size:
                    chunk = client_socket.recv(min(4096, data_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            
            self.log_event(f"📝 Получен legacy файл: {save_filename} ({received} байт)", agent_id=client_ip)
            
            response = json.dumps({
                "status": "success",
                "message": f"Legacy файл сохранен: {save_filename}",
                "warning": "Файл не был зашифрован!"
            })
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            error_msg = f"❌ Ошибка приема legacy файла: {e}"
            self.log_event(error_msg, "ERROR", client_ip)
            client_socket.send(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
    
    def _handle_metrics(self, client_socket, client_ip):
        """Обработка метрик"""
        try:
            metrics_json = client_socket.recv(4096).decode('utf-8')
            metrics = json.loads(metrics_json)
            
            # Сохраняем метрики
            metrics_file = f"{self.logs_path}/metrics_{client_ip}_{datetime.now().strftime('%Y%m%d')}.json"
            with open(metrics_file, "a", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "ip": client_ip,
                    "metrics": metrics
                }, f)
                f.write("\n")
            
            self.log_event(f"📊 Получены метрики от {client_ip}", agent_id=client_ip)
            
        except Exception as e:
            self.log_event(f"❌ Ошибка приема метрик: {e}", "ERROR", client_ip)
    
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
            self.log_event("🔴 Сервер остановлен")

if __name__ == "__main__":
    server = SecureMasterServer(port=9090)
    server.start()