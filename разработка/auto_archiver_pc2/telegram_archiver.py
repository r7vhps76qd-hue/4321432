"""
Telegram архиватор для ПК2
Скачивает каналы и чаты через Telethon
"""
import asyncio
import json
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument

class TelegramArchiver:
    def __init__(self, api_id=None, api_hash=None, session_name='telegram_session'):
        """
        Инициализация Telegram клиента
        
        Args:
            api_id: API ID из my.telegram.org
            api_hash: API Hash из my.telegram.org
            session_name: Имя сессии
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None
        self.download_path = "./telegram_archives"
        
        # Создаем папки
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(f"{self.download_path}/chats", exist_ok=True)
        os.makedirs(f"{self.download_path}/media", exist_ok=True)
        
    async def connect(self):
        """Подключение к Telegram"""
        if not self.api_id or not self.api_hash:
            print("❌ Не указаны API ID и Hash")
            print("👉 Получи на https://my.telegram.org")
            return False
            
        try:
            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start()
            
            # Проверяем авторизацию
            me = await self.client.get_me()
            print(f"✅ Подключен как: {me.first_name} (@{me.username})")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подключения к Telegram: {e}")
            return False
    
    async def download_channel(self, channel_link, limit=100):
        """
        Скачивание канала
        
        Args:
            channel_link: Ссылка на канал (@username или https://t.me/...)
            limit: Максимальное количество сообщений
        """
        if not self.client:
            print("❌ Клиент не инициализирован")
            return None
        
        try:
            print(f"📥 Скачиваю канал: {channel_link}")
            
            # Получаем entity (канал/чат)
            entity = await self.client.get_entity(channel_link)
            channel_name = getattr(entity, 'title', getattr(entity, 'username', 'unknown'))
            
            # Создаем папку для канала
            safe_name = "".join(c for c in channel_name if c.isalnum() or c in (' ', '_')).rstrip()
            channel_folder = f"{self.download_path}/chats/{safe_name}"
            os.makedirs(channel_folder, exist_ok=True)
            
            # Собираем сообщения
            messages_data = []
            media_count = 0
            
            async for message in self.client.iter_messages(entity, limit=limit):
                msg_data = {
                    'id': message.id,
                    'date': message.date.isoformat() if message.date else None,
                    'sender_id': message.sender_id,
                    'text': message.text,
                    'media_type': None,
                    'media_path': None
                }
                
                # Скачиваем медиа если есть
                if message.media:
                    media_count += 1
                    media_filename = f"media_{message.id}_{media_count}"
                    
                    if isinstance(message.media, MessageMediaPhoto):
                        msg_data['media_type'] = 'photo'
                        media_path = f"{self.download_path}/media/{media_filename}.jpg"
                    elif isinstance(message.media, MessageMediaDocument):
                        msg_data['media_type'] = 'document'
                        # Получаем расширение файла
                        doc = message.media.document
                        mime_type = doc.mime_type if doc.mime_type else 'bin'
                        ext = mime_type.split('/')[-1]
                        media_path = f"{self.download_path}/media/{media_filename}.{ext}"
                    else:
                        media_path = f"{self.download_path}/media/{media_filename}.bin"
                    
                    # Скачиваем медиа
                    try:
                        await self.client.download_media(message.media, file=media_path)
                        msg_data['media_path'] = media_path
                        print(f"  📷 Скачано медиа: {media_path}")
                    except Exception as e:
                        print(f"  ⚠️ Ошибка скачивания медиа: {e}")
                
                messages_data.append(msg_data)
                
                # Прогресс
                if len(messages_data) % 10 == 0:
                    print(f"  📝 Обработано сообщений: {len(messages_data)}/{limit}")
            
            # Сохраняем метаданные
            metadata = {
                'channel_name': channel_name,
                'channel_link': channel_link,
                'total_messages': len(messages_data),
                'media_count': media_count,
                'download_date': datetime.now().isoformat(),
                'messages': messages_data
            }
            
            metadata_file = f"{channel_folder}/metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # Создаем текстовый дамп
            text_dump_file = f"{channel_folder}/messages.txt"
            with open(text_dump_file, 'w', encoding='utf-8') as f:
                f.write(f"Канал: {channel_name}\n")
                f.write(f"Ссылка: {channel_link}\n")
                f.write(f"Сообщений: {len(messages_data)}\n")
                f.write(f"Медиа: {media_count}\n")
                f.write(f"Дата архивации: {datetime.now()}\n")
                f.write("="*50 + "\n\n")
                
                for msg in messages_data:
                    f.write(f"[{msg['date']}] ID:{msg['id']}\n")
                    if msg['text']:
                        f.write(f"{msg['text']}\n")
                    if msg['media_type']:
                        f.write(f"[{msg['media_type'].upper()}: {msg['media_path']}]\n")
                    f.write("-"*30 + "\n")
            
            print(f"✅ Канал скачан: {channel_name}")
            print(f"   📊 Сообщений: {len(messages_data)}")
            print(f"   📷 Медиафайлов: {media_count}")
            print(f"   💾 Файлы сохранены в: {channel_folder}")
            
            # Создаем архив для отправки
            archive_path = self._create_archive(channel_folder, channel_name)
            return archive_path
            
        except Exception as e:
            print(f"❌ Ошибка скачивания канала: {e}")
            return None
    
    def _create_archive(self, folder_path, channel_name):
        """
        Создание архива из папки
        
        Args:
            folder_path: Путь к папке с данными
            channel_name: Имя канала
        
        Returns:
            str: Путь к созданному архиву
        """
        import zipfile
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{channel_name}_{timestamp}.zip".replace(' ', '_')
        archive_path = f"{self.download_path}/{archive_name}"
        
        print(f"📦 Создаю архив: {archive_name}")
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                    zipf.write(file_path, arcname)
                    print(f"  📎 Добавлен файл: {file}")
        
        print(f"✅ Архив создан: {archive_path} ({os.path.getsize(archive_path)//1024} KB)")
        return archive_path
    
    async def get_available_chats(self):
        """Получение списка доступных чатов/каналов"""
        if not self.client:
            print("❌ Клиент не инициализирован")
            return []
        
        try:
            dialogs = []
            async for dialog in self.client.iter_dialogs(limit=50):
                dialogs.append({
                    'name': dialog.name,
                    'id': dialog.id,
                    'entity': dialog.entity,
                    'unread_count': dialog.unread_count
                })
            
            return dialogs
        except Exception as e:
            print(f"❌ Ошибка получения чатов: {e}")
            return []
    
    async def close(self):
        """Закрытие соединения"""
        if self.client:
            await self.client.disconnect()
            print("🔌 Соединение с Telegram закрыто")

def sync_download_channel(api_id, api_hash, channel_link, limit=100):
    """
    Синхронная версия скачивания канала
    (для использования из обычного кода)
    """
    archiver = TelegramArchiver(api_id, api_hash)
    
    # Запускаем асинхронную функцию
    async def run():
        if await archiver.connect():
            archive_path = await archiver.download_channel(channel_link, limit)
            await archiver.close()
            return archive_path
        return None
    
    return asyncio.run(run())

def get_telegram_credentials():
    """
    Получение или запрос учетных данных Telegram
    """
    creds_file = "./telegram_credentials.json"
    
    # Пробуем загрузить из файла
    if os.path.exists(creds_file):
        try:
            with open(creds_file, 'r') as f:
                creds = json.load(f)
                print("✅ Учетные данные загружены из файла")
                return creds.get('api_id'), creds.get('api_hash')
        except:
            pass
    
    # Запрашиваем у пользователя
    print("=" * 60)
    print("📱 НАСТРОЙКА TELEGRAM АРХИВАТОРА")
    print("=" * 60)
    print("1. Перейди на https://my.telegram.org")
    print("2. Войди в свой аккаунт Telegram")
    print("3. Перейди в 'API Development Tools'")
    print("4. Создай приложение и получи:")
    print("   - api_id")
    print("   - api_hash")
    print("=" * 60)
    
    api_id = input("Введи api_id: ").strip()
    api_hash = input("Введи api_hash: ").strip()
    
    # Сохраняем в файл
    try:
        with open(creds_file, 'w') as f:
            json.dump({'api_id': api_id, 'api_hash': api_hash}, f)
        print("✅ Учетные данные сохранены в файл")
    except:
        print("⚠️ Не удалось сохранить учетные данные")
    
    return api_id, api_hash

if __name__ == "__main__":
    # Тестовый запуск
    print("🧪 Тестирование Telegram архиватора...")
    
    # Получаем учетные данные
    api_id, api_hash = get_telegram_credentials()
    
    if api_id and api_hash:
        # Пример использования
        channel = input("Введи ссылку на канал (например @durov): ").strip()
        
        if channel:
            print(f"🚀 Начинаю скачивание канала: {channel}")
            archive_path = sync_download_channel(api_id, api_hash, channel, limit=50)
            
            if archive_path:
                print(f"✅ Архив готов: {archive_path}")
                print(f"📦 Размер: {os.path.getsize(archive_path) // 1024} KB")
            else:
                print("❌ Не удалось скачать канал")
    else:
        print("❌ Учетные данные не получены")