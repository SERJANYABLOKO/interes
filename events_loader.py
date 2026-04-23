# 📁 events_loader.py (с фильтрацией прошедших событий)
# Модуль для загрузки событий из API KudaGo (Москва)
import random
import aiohttp
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

EVENTS_CACHE_FILE = "events.json"
CACHE_EXPIRY_HOURS = 6

# Добавь эту константу в начало файла (после импортов)
YEAR_2026_START = datetime(2026, 1, 1).timestamp()

def is_event_upcoming(event: Dict) -> bool:
    """
    Проверяет, является ли событие актуальным (после 2026 года).
    Возвращает True, если событие начинается 1 января 2026 или позже.
    """
    dates = event.get("dates", [])
    if not dates:
        return False
    
    # Берем первую дату в списке (обычно основная дата события)
    first_date = dates[0]
    start_timestamp = first_date.get("start", 0)
    
    # Если дата начала указана и она больше или равна 01.01.2026
    if start_timestamp and start_timestamp >= YEAR_2026_START:
        return True
        
    return False

def get_event_date_str(event: Dict) -> str:
    """Возвращает читаемую дату события для отладки"""
    dates = event.get("dates", [])
    if dates:
        first_date = dates[0]
        start = first_date.get("start", 0)
        if start:
            dt = datetime.fromtimestamp(start)
            return dt.strftime("%Y-%m-%d %H:%M")
    return "Дата неизвестна"

async def fetch_events_from_api(categories: List[str] = None) -> List[Dict]:
    """
    Загружает события из API KudaGo для Москвы.
    categories: список категорий (например, ['concert', 'exhibition', 'theater'])
    Документация API: https://kudago.com/public-api/
    """
    url = "https://kudago.com/public-api/v1/events/"
    params = {
        "location": "msk",  # Москва
        "page_size": 100,   # Загружаем до 100 событий за раз
        "actual_since": datetime.now().strftime("%Y-%m-%d"),
        "fields": "id,title,place,description,dates,images,categories,price,site_url,age_restriction"
    }
    
    if categories:
        params["categories"] = ",".join(categories)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    
                    # Фильтруем только будущие события
                    upcoming_events = []
                    skipped_count = 0
                    
                    for event in results:
                        if is_event_upcoming(event):
                            upcoming_events.append(event)
                        else:
                            skipped_count += 1
                            # Логируем пропущенные события для отладки
                            title = event.get("title", "Без названия")
                            date_str = get_event_date_str(event)
                            logger.debug(f"Пропущено прошедшее событие: {title} ({date_str})")
                    
                    logger.info(f"Загружено {len(results)} событий из API KudaGo, из них актуальных: {len(upcoming_events)}, пропущено прошедших: {skipped_count}")
                    return upcoming_events
                else:
                    logger.error(f"Ошибка API KudaGo: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return []

def format_event_message(event: Dict) -> str:
    """Форматирует событие в красивое сообщение для Telegram"""
    title = event.get("title", "Без названия")
    
    # Дата и время
    dates = event.get("dates", [])
    if dates:
        first_date = dates[0]
        start_date = first_date.get("start", 0)
        end_date = first_date.get("end", 0)
        
        if start_date:
            dt_start = datetime.fromtimestamp(start_date)
            date_str = dt_start.strftime("%d.%m.%Y, %H:%M")
            
            # Добавляем информацию об окончании, если есть
            if end_date:
                dt_end = datetime.fromtimestamp(end_date)
                date_str += f" — {dt_end.strftime('%H:%M')}"
        else:
            date_str = "Дата уточняется"
    else:
        date_str = "Дата уточняется"
    
    # Место проведения
    place = event.get("place", {})
    place_name = place.get("title", "Место не указано") if place else "Место не указано"
    
    # Цена
    price = event.get("price", "")
    price_str = f"💰 {price} руб." if price else "💰 Цена не указана"
    
    # Описание (обрезаем до 200 символов)
    description = event.get("description", "")
    if description:
        if len(description) > 200:
            description = description[:200] + "..."
    else:
        description = "Описание отсутствует"
    
    # Категория
    categories = event.get("categories", [])
    if categories and isinstance(categories, list):
        category_names = []
        for cat in categories:
            if isinstance(cat, dict):
                category_names.append(cat.get("name", ""))
            elif isinstance(cat, str):
                category_names.append(cat)
        category_str = " / ".join([c for c in category_names if c]) if category_names else "Событие"
    else:
        category_str = "Событие"
    
    # Возрастное ограничение
    age_restriction = event.get("age_restriction", "")
    age_str = f"🔞 {age_restriction}+" if age_restriction else ""
    
    # Ссылка
    site_url = event.get("site_url", "")
    
    # Формируем сообщение
    message_parts = [
        f"🎉 *{title}*",
        f"📅 {date_str}",
        f"📍 {place_name}",
        f"{price_str}"
    ]
    
    if age_str:
        message_parts.append(age_str)
    
    message_parts.append(f"\n📝 {description}")
    
    if site_url:
        message_parts.append(f"\n🔗 [Подробнее]({site_url})")
    
    return "\n".join(message_parts)

def get_random_event(events: List[Dict]) -> Optional[Dict]:
    """Возвращает случайное событие из списка"""
    if not events:
        return None
    return random.choice(events)

async def load_events(categories: List[str] = None) -> List[Dict]:
    """
    Загружает события из кеша или API
    """
    # Проверяем актуальность кеша
    try:
        with open(EVENTS_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
            cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            # Если кеш свежее чем CACHE_EXPIRY_HOURS, используем его
            if datetime.now() - cache_time < timedelta(hours=CACHE_EXPIRY_HOURS):
                cached_events = cache.get("events", [])
                # Дополнительно фильтруем кешированные события (на случай, если они устарели)
                upcoming_cached = [e for e in cached_events if is_event_upcoming(e)]
                logger.info(f"Используем кешированные события: {len(cached_events)} всего, {len(upcoming_cached)} актуальных")
                return upcoming_cached
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("Кеш не найден или поврежден")
    
    # Загружаем свежие события
    events = await fetch_events_from_api(categories)
    
    # Сохраняем в кеш (только актуальные события)
    if events:
        try:
            with open(EVENTS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "events": events
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"Кеш сохранен: {len(events)} актуальных событий")
        except Exception as e:
            logger.error(f"Не удалось сохранить кеш: {e}")
    
    return events
