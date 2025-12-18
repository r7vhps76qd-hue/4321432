"""
AI-анализатор для обработки Telegram архивов
"""
import os
import json
import re
from datetime import datetime
from collections import Counter
import zipfile
import tempfile
import shutil

class AIAnalyzer:
    def __init__(self, storage_path="./secure_storage"):
        """
        Инициализация AI анализатора
        
        Args:
            storage_path: Путь к хранилищу данных
        """
        self.storage_path = storage_path
        self.decrypted_storage = f"{storage_path}/decrypted"
        self.ai_results_path = f"{storage_path}/ai_results"
        
        # Создаем папки
        os.makedirs(self.ai_results_path, exist_ok=True)
        os.makedirs(f"{self.ai_results_path}/reports", exist_ok=True)
        os.makedirs(f"{self.ai_results_path}/stats", exist_ok=True)
        
        print("🤖 AI-анализатор инициализирован")
    
    def analyze_telegram_archive(self, archive_path):
        """
        Анализ Telegram архива
        
        Args:
            archive_path: Путь к архиву .zip
        
        Returns:
            dict: Результаты анализа
        """
        print(f"🔍 Анализирую архив: {os.path.basename(archive_path)}")
        
        results = {
            "archive_name": os.path.basename(archive_path),
            "analysis_date": datetime.now().isoformat(),
            "basic_stats": {},
            "sentiment_analysis": {},
            "content_analysis": {},
            "user_analysis": {},
            "anomalies": [],
            "summary": ""
        }
        
        try:
            # Создаем временную папку для распаковки
            temp_dir = tempfile.mkdtemp()
            
            # Распаковываем архив
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Ищем файлы метаданных
            metadata_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file == 'metadata.json' or file.endswith('.json'):
                        metadata_files.append(os.path.join(root, file))
            
            if not metadata_files:
                results["summary"] = "⚠️ В архиве не найдены метаданные"
                return results
            
            # Анализируем каждый файл метаданных
            all_messages = []
            all_users = set()
            
            for metadata_file in metadata_files:
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    # Базовый анализ
                    if 'messages' in metadata:
                        messages = metadata['messages']
                        all_messages.extend(messages)
                        
                        # Собираем пользователей
                        for msg in messages:
                            if 'sender_id' in msg:
                                all_users.add(str(msg['sender_id']))
                
                except Exception as e:
                    print(f"⚠️ Ошибка чтения {metadata_file}: {e}")
            
            if not all_messages:
                results["summary"] = "📭 В архиве нет сообщений для анализа"
                return results
            
            # Выполняем анализ
            results["basic_stats"] = self._analyze_basic_stats(all_messages, all_users)
            results["sentiment_analysis"] = self._analyze_sentiment(all_messages)
            results["content_analysis"] = self._analyze_content(all_messages)
            results["user_analysis"] = self._analyze_users(all_messages)
            results["anomalies"] = self._detect_anomalies(all_messages)
            results["summary"] = self._generate_summary(results)
            
            # Сохраняем результаты
            self._save_results(results, archive_path)
            
            # Очищаем временную папку
            shutil.rmtree(temp_dir)
            
            print(f"✅ Анализ завершен: {len(all_messages)} сообщений, {len(all_users)} пользователей")
            return results
            
        except Exception as e:
            print(f"❌ Ошибка анализа архива: {e}")
            results["summary"] = f"❌ Ошибка анализа: {str(e)}"
            return results
    
    def _analyze_basic_stats(self, messages, users):
        """Базовая статистика"""
        stats = {
            "total_messages": len(messages),
            "unique_users": len(users),
            "time_period": {},
            "media_count": 0,
            "avg_message_length": 0
        }
        
        # Временной период
        dates = []
        total_length = 0
        
        for msg in messages:
            # Дата сообщения
            if 'date' in msg and msg['date']:
                try:
                    date_str = msg['date'].split('T')[0] if 'T' in msg['date'] else msg['date']
                    dates.append(date_str)
                except:
                    pass
            
            # Длина сообщения
            if 'text' in msg and msg['text']:
                total_length += len(str(msg['text']))
            
            # Медиа
            if 'media_type' in msg and msg['media_type']:
                stats["media_count"] += 1
        
        if dates:
            stats["time_period"] = {
                "first_date": min(dates),
                "last_date": max(dates),
                "days_span": (datetime.fromisoformat(max(dates)) - datetime.fromisoformat(min(dates))).days
            }
        
        if messages:
            stats["avg_message_length"] = total_length / len(messages)
        
        return stats
    
    def _analyze_sentiment(self, messages):
        """Анализ тональности (упрощенный)"""
        sentiment = {
            "positive_words": 0,
            "negative_words": 0,
            "neutral_words": 0,
            "sentiment_score": 0,
            "dominant_emotion": "neutral"
        }
        
        # Списки слов для анализа
        positive_words = {
            'хорошо', 'отлично', 'прекрасно', 'замечательно', 'супер', 'класс', 'отличный',
            'хороший', 'прекрасный', 'замечательный', 'великолепно', 'превосходно',
            'спасибо', 'благодарю', 'рад', 'доволен', 'счастлив', 'успех', 'победа',
            'любовь', 'нравится', 'восхитительно', 'потрясающе', 'здорово'
        }
        
        negative_words = {
            'плохо', 'ужасно', 'отвратительно', 'кошмар', 'проблема', 'ошибка',
            'неправильно', 'нельзя', 'запрещено', 'опасно', 'страшно', 'грустно',
            'печально', 'разочарован', 'злой', 'сердитый', 'ненавижу', 'не люблю',
            'проигрыш', 'поражение', 'провал', 'катастрофа', 'беда'
        }
        
        total_words = 0
        
        for msg in messages:
            if 'text' in msg and msg['text']:
                text = str(msg['text']).lower()
                words = re.findall(r'\b[а-яa-z]+\b', text)
                
                for word in words:
                    total_words += 1
                    if word in positive_words:
                        sentiment["positive_words"] += 1
                    elif word in negative_words:
                        sentiment["negative_words"] += 1
                    else:
                        sentiment["neutral_words"] += 1
        
        # Рассчитываем score
        if total_words > 0:
            positive_ratio = sentiment["positive_words"] / total_words
            negative_ratio = sentiment["negative_words"] / total_words
            sentiment["sentiment_score"] = positive_ratio - negative_ratio
            
            if sentiment["sentiment_score"] > 0.1:
                sentiment["dominant_emotion"] = "positive"
            elif sentiment["sentiment_score"] < -0.1:
                sentiment["dominant_emotion"] = "negative"
            else:
                sentiment["dominant_emotion"] = "neutral"
        
        return sentiment
    
    def _analyze_content(self, messages):
        """Анализ контента"""
        content = {
            "common_words": [],
            "message_frequency": {},
            "urls_count": 0,
            "hashtags_count": 0,
            "mentions_count": 0
        }
        
        # Счетчик слов
        word_counter = Counter()
        stop_words = {'и', 'в', 'не', 'на', 'что', 'это', 'как', 'но', 'а', 'или', 'у', 'за', 'к', 'до', 'по', 'из', 'от', 'же', 'бы', 'для', 'то', 'вы', 'он', 'она', 'они', 'мы', 'вас', 'ваш', 'их', 'те', 'та', 'тот', 'этот', 'такой', 'такие', 'свой'}
        
        for msg in messages:
            if 'text' in msg and msg['text']:
                text = str(msg['text']).lower()
                
                # Считаем слова
                words = re.findall(r'\b[а-яa-z]{3,}\b', text)
                for word in words:
                    if word not in stop_words:
                        word_counter[word] += 1
                
                # Считаем URL
                content["urls_count"] += len(re.findall(r'https?://\S+', text))
                
                # Считаем хэштеги
                content["hashtags_count"] += len(re.findall(r'#\w+', text))
                
                # Считаем упоминания
                content["mentions_count"] += len(re.findall(r'@\w+', text))
        
        # Самые частые слова
        content["common_words"] = word_counter.most_common(20)
        
        return content
    
    def _analyze_users(self, messages):
        """Анализ пользователей"""
        user_analysis = {
            "top_posters": [],
            "user_activity": {},
            "avg_messages_per_user": 0
        }
        
        # Считаем сообщения по пользователям
        user_counter = Counter()
        
        for msg in messages:
            if 'sender_id' in msg:
                user_counter[str(msg['sender_id'])] += 1
        
        # Топ пользователей
        user_analysis["top_posters"] = user_counter.most_common(10)
        
        # Активность по времени
        time_counter = Counter()
        for msg in messages:
            if 'date' in msg and msg['date']:
                try:
                    hour = datetime.fromisoformat(msg['date'].replace('Z', '+00:00')).hour
                    time_counter[hour] += 1
                except:
                    pass
        
        # Конвертируем в словарь
        user_analysis["user_activity"] = dict(time_counter)
        
        # Среднее количество сообщений
        if user_counter:
            user_analysis["avg_messages_per_user"] = len(messages) / len(user_counter)
        
        return user_analysis
    
    def _detect_anomalies(self, messages):
        """Обнаружение аномалий"""
        anomalies = []
        
        if not messages:
            return anomalies
        
        # Проверяем на спам (много сообщений от одного пользователя за короткое время)
        user_messages = {}
        for msg in messages:
            if 'sender_id' in msg and 'date' in msg:
                user_id = msg['sender_id']
                if user_id not in user_messages:
                    user_messages[user_id] = []
                user_messages[user_id].append(msg['date'])
        
        for user_id, dates in user_messages.items():
            if len(dates) > 50:  # Много сообщений
                try:
                    # Проверяем временной интервал
                    sorted_dates = sorted([datetime.fromisoformat(d.replace('Z', '+00:00')) for d in dates])
                    time_span = (sorted_dates[-1] - sorted_dates[0]).total_seconds()
                    
                    if time_span < 3600 and len(dates) > 20:  # 20+ сообщений за час
                        anomalies.append({
                            "type": "possible_spam",
                            "user_id": user_id,
                            "messages_count": len(dates),
                            "time_span_seconds": time_span
                        })
                except:
                    pass
        
        # Проверяем на очень длинные сообщения
        for msg in messages:
            if 'text' in msg and msg['text']:
                text_len = len(str(msg['text']))
                if text_len > 1000:
                    anomalies.append({
                        "type": "very_long_message",
                        "message_id": msg.get('id', 'unknown'),
                        "length": text_len
                    })
        
        return anomalies
    
    def _generate_summary(self, analysis_results):
        """Генерация текстового резюме"""
        stats = analysis_results["basic_stats"]
        sentiment = analysis_results["sentiment_analysis"]
        content = analysis_results["content_analysis"]
        
        summary_lines = []
        
        summary_lines.append(f"📊 ОБЩАЯ СТАТИСТИКА:")
        summary_lines.append(f"• Сообщений: {stats['total_messages']}")
        summary_lines.append(f"• Уникальных пользователей: {stats['unique_users']}")
        
        if 'time_period' in stats and stats['time_period']:
            tp = stats['time_period']
            summary_lines.append(f"• Период: {tp.get('first_date', '?')} - {tp.get('last_date', '?')}")
            summary_lines.append(f"• Дней активности: {tp.get('days_span', '?')}")
        
        summary_lines.append(f"• Медиафайлов: {stats.get('media_count', 0)}")
        summary_lines.append(f"• Средняя длина сообщения: {stats.get('avg_message_length', 0):.0f} симв.")
        
        summary_lines.append(f"\n🎭 ТОНАЛЬНОСТЬ:")
        summary_lines.append(f"• Преобладающая эмоция: {sentiment.get('dominant_emotion', 'neutral').upper()}")
        summary_lines.append(f"• Оценка: {sentiment.get('sentiment_score', 0):.2f}")
        summary_lines.append(f"• Позитивных слов: {sentiment.get('positive_words', 0)}")
        summary_lines.append(f"• Негативных слов: {sentiment.get('negative_words', 0)}")
        
        summary_lines.append(f"\n🔍 КОНТЕНТ:")
        summary_lines.append(f"• URL: {content.get('urls_count', 0)}")
        summary_lines.append(f"• Хэштегов: {content.get('hashtags_count', 0)}")
        summary_lines.append(f"• Упоминаний: {content.get('mentions_count', 0)}")
        
        if content.get('common_words'):
            top_words = ", ".join([f"{word}({count})" for word, count in content['common_words'][:5]])
            summary_lines.append(f"• Частые слова: {top_words}")
        
        if analysis_results.get('anomalies'):
            summary_lines.append(f"\n⚠️  АНОМАЛИИ:")
            for anomaly in analysis_results['anomalies'][:3]:
                summary_lines.append(f"• {anomaly.get('type', 'unknown')}")
        
        return "\n".join(summary_lines)
    
    def _save_results(self, results, archive_path):
        """Сохранение результатов анализа"""
        archive_name = os.path.basename(archive_path).replace('.zip', '').replace('.enc', '')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON с полными результатами
        json_file = f"{self.ai_results_path}/stats/{archive_name}_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        # Текстовый отчет
        report_file = f"{self.ai_results_path}/reports/{archive_name}_{timestamp}_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"📊 AI АНАЛИЗ ТЕЛЕГРАМ АРХИВА\n")
            f.write(f"=" * 50 + "\n\n")
            f.write(f"📁 Архив: {results['archive_name']}\n")
            f.write(f"📅 Дата анализа: {results['analysis_date']}\n")
            f.write(f"=" * 50 + "\n\n")
            f.write(results['summary'])
        
        print(f"💾 Результаты сохранены:")
        print(f"   📊 JSON: {json_file}")
        print(f"   📝 Отчет: {report_file}")
    
    def analyze_all_archives(self):
        """Анализ всех архивов в хранилище"""
        archives_path = self.decrypted_storage
        
        if not os.path.exists(archives_path):
            print(f"❌ Папка с архивами не найдена: {archives_path}")
            return []
        
        # Ищем .zip файлы
        archives = []
        for file in os.listdir(archives_path):
            if file.endswith('.zip'):
                archives.append(os.path.join(archives_path, file))
        
        print(f"📁 Найдено архивов для анализа: {len(archives)}")
        
        results = []
        for archive in archives:
            result = self.analyze_telegram_archive(archive)
            results.append(result)
        
        # Создаем общий отчет
        if results:
            self._create_global_report(results)
        
        return results
    
    def _create_global_report(self, all_results):
        """Создание общего отчета по всем архивам"""
        if not all_results:
            return
        
        total_messages = sum(r['basic_stats'].get('total_messages', 0) for r in all_results)
        total_users = sum(r['basic_stats'].get('unique_users', 0) for r in all_results)
        
        # Анализ тональности
        sentiment_scores = [r['sentiment_analysis'].get('sentiment_score', 0) for r in all_results]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        report = f"""
🌐 ОБЩИЙ ОТЧЕТ ПО АРХИВАМ
{"=" * 50}

📊 ОБЩАЯ СТАТИСТИКА:
• Проанализировано архивов: {len(all_results)}
• Всего сообщений: {total_messages}
• Всего уникальных пользователей: {total_users}

🎭 СРЕДНЯЯ ТОНАЛЬНОСТЬ:
• Оценка: {avg_sentiment:.2f}
• Общий настрой: {'ПОЗИТИВНЫЙ' if avg_sentiment > 0.1 else 'НЕГАТИВНЫЙ' if avg_sentiment < -0.1 else 'НЕЙТРАЛЬНЫЙ'}

📈 ТОП АРХИВОВ ПО АКТИВНОСТИ:
"""
        
        # Сортируем по количеству сообщений
        sorted_results = sorted(all_results, key=lambda x: x['basic_stats'].get('total_messages', 0), reverse=True)
        
        for i, result in enumerate(sorted_results[:5], 1):
            stats = result['basic_stats']
            report += f"{i}. {result['archive_name']}: {stats.get('total_messages', 0)} сообщений, {stats.get('unique_users', 0)} пользователей\n"
        
        report += f"\n⚠️  ВСЕГО АНОМАЛИЙ: {sum(len(r['anomalies']) for r in all_results)}"
        
        # Сохраняем общий отчет
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"{self.ai_results_path}/reports/GLOBAL_REPORT_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"🌐 Общий отчет создан: {report_file}")

# Утилиты для работы с архивами
class ArchiveManager:
    def __init__(self, storage_path="./secure_storage"):
        self.storage_path = storage_path
        self.decrypted_storage = f"{storage_path}/decrypted"
    
    def list_archives(self):
        """Список доступных архивов"""
        archives = []
        
        if os.path.exists(self.decrypted_storage):
            for file in os.listdir(self.decrypted_storage):
                if file.endswith('.zip'):
                    filepath = os.path.join(self.decrypted_storage, file)
                    size = os.path.getsize(filepath) // 1024  # KB
                    archives.append({
                        'name': file,
                        'path': filepath,
                        'size_kb': size,
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M')
                    })
        
        return sorted(archives, key=lambda x: x['modified'], reverse=True)
    
    def cleanup_old_archives(self, days_old=30):
        """Очистка старых архивов"""
        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
        cleaned = 0
        
        for archive in self.list_archives():
            if os.path.getmtime(archive['path']) < cutoff_date:
                try:
                    os.remove(archive['path'])
                    cleaned += 1
                    print(f"🗑️ Удален старый архив: {archive['name']}")
                except Exception as e:
                    print(f"❌ Ошибка удаления {archive['name']}: {e}")
        
        return cleaned

if __name__ == "__main__":
    # Тестовый запуск
    print("🧪 Тестирование AI-анализатора...")
    
    analyzer = AIAnalyzer()
    manager = ArchiveManager()
    
    archives = manager.list_archives()
    print(f"📁 Найдено архивов: {len(archives)}")
    
    if archives:
        print("🔍 Анализирую первый архив...")
        result = analyzer.analyze_telegram_archive(archives[0]['path'])
        print("\n" + result['summary'])
    else:
        print("📭 Архивы не найдены. Сначала отправьте архивы с ПК2.")
    
    # Очистка старых архивов
    cleaned = manager.cleanup_old_archives(days_old=7)
    print(f"🧹 Очищено старых архивов: {cleaned}")