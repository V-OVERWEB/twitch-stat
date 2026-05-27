#!/usr/bin/env python3
"""
Тест StreamElements API — получаем все данные по одному каналу.
"""

import json
from urllib.request import Request, urlopen
from urllib.error import URLError

CHANNEL = "goodoq"

def fetch_all_stats(login: str):
    """Получает полную статистику через API StreamElements."""
    url = f"https://api.streamelements.com/kappa/v2/chatstats/{login}/stats"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    
    print(f"URL: {url}")
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print(f"Ошибка: {e}")
        return
    
    print(f"\n{'='*60}")
    print(f"ПОЛНАЯ СТАТИСТИКА КАНАЛА: {login}")
    print(f"{'='*60}")
    
    # ВСЕ ключи и их значения
    print(f"\n{'─'*40}")
    print("ВСЕ КЛЮЧИ В ОТВЕТЕ API:")
    print(f"{'─'*40}")
    for key in sorted(data.keys()):
        val = data[key]
        if isinstance(val, list):
            print(f"  {key}: список из {len(val)} элементов")
        elif isinstance(val, (int, float)):
            print(f"  {key}: {val:,}")
        elif isinstance(val, str):
            print(f"  {key}: {val}")
        else:
            print(f"  {key}: {type(val).__name__}")
    
    # Основные метрики
    print(f"\n{'─'*40}")
    print("ОСНОВНЫЕ МЕТРИКИ:")
    print(f"{'─'*40}")
    print(f"  Всего сообщений:       {data.get('totalMessages', 0):,}")
    print(f"  Уникальных чаттеров:    {data.get('uniqueChatters', 0):,}")
    print(f"  Сообщений в секунду:    {data.get('messagesPerSecond', 0)}")
    print(f"  Канал:                  {data.get('channel', '')}")
    
    # Если messagesPerSecond нет — ищем похожие ключи
    mps_keys = [k for k in data.keys() if 'second' in k.lower() or 'mps' in k.lower() or 'rate' in k.lower()]
    if mps_keys:
        print(f"\n  Похожие ключи (сообщения/сек):")
        for k in mps_keys:
            print(f"    {k}: {data[k]}")

if __name__ == "__main__":
    fetch_all_stats(CHANNEL)