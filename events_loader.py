# 📁 events_loader.py
# Модуль для загрузки событий из API KudaGo (Москва)
import random  # добавь эту строку в начало файла
import aiohttp
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

EVENTS_CACHE_FILE = "events.json"
CACHE_EXPIRY_HOURS = 6

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
        "fields": "id,title,place,description,dates,images,categories,price,site_url"
    }
    
    if categories:
        params["categories"] = ",".join(categories)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    logger.info(f"Загружено {len(results)} событий из API KudaGo")
                    return results
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
        if start_date:
            dt = datetime.fromtimestamp(start_date)
            date_str = dt.strftime("%d.%m.%Y, %H:%M")
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
    if len(description) > 200:
        description = description[:200] + "..."
    
    # Категория
    categories = event.get("categories", [])
    category_names = [cat.get("name", "") for cat in categories if cat.get("name")]
    category_str = " / ".join(category_names) if category_names else "Событие"
    
    # Ссылка
    site_url = event.get("site_url", "")
    
    message = (
        f"🎉 *{title}*\n\n"
        f"📅 {date_str}\n"
        f"📍 {place_name}\n"
        f"{price_str}\n\n"
        f"📝 {description}\n\n"
        f"🔗 [Подробнее]({site_url})"
    )
    return message

def get_random_event(events: List[Dict]) -> Optional[Dict]:
    """Возвращает случайное событие из списка"""
    if not events:
        return None
    import random  # уже будет в начале файла
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
            if datetime.now() - cache_time < timedelta(hours=CACHE_EXPIRY_HOURS):
                logger.info("Используем кешированные события")
                return cache.get("events", [])
    except (FileNotFoundError, json.JSONDecodeError):
        logger.info("Кеш не найден или поврежден")
    
    # Загружаем свежие события
    events = await fetch_events_from_api(categories)
    
    # Сохраняем в кеш
    try:
        with open(EVENTS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "events": events
            }, f, ensure_ascii=False, indent=2)
        logger.info("Кеш сохранен")
    except Exception as e:
        logger.error(f"Не удалось сохранить кеш: {e}")
    
    return events
