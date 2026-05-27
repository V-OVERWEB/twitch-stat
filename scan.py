#!/usr/bin/env python3
"""
Сбор Just Chatting каналов с онлайном 500+
Метод: Apify + StreamElements API
Режим: автозапуск каждые 30 минут. Время — московское.
"""

import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError
from apify_client import ApifyClient

# ============================================================================
# КОНФИГУРАЦИЯ
# ============================================================================

APIFY_TOKEN = "apify_api_WNSlSSolLPZO9stfLxfGF6uLMpvqTo08f4Ao"
ACTOR_ID = "automation-lab/twitch-scraper"
GAME_NAME = "Just Chatting"
MIN_VIEWERS = 500
OUTPUT_FILE = "channels_to_monitor.json"
INTERVAL_MINUTES = 30

MOSCOW_TZ = timezone(timedelta(hours=3))

def moscow_now_iso():
    return datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S') + ' МСК'

def moscow_now_display():
    return datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S (МСК)')

def to_moscow_time(utc_string):
    if not utc_string:
        return ""
    try:
        if utc_string.endswith("Z"):
            utc_string = utc_string.replace("Z", "+00:00")
        utc_time = datetime.fromisoformat(utc_string)
        return utc_time.astimezone(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M:%S') + ' МСК'
    except:
        return utc_string

# ============================================================================
# STREAMELEMENTS API
# ============================================================================

def fetch_se_stats(login: str) -> dict:
    url = f"https://api.streamelements.com/kappa/v2/chatstats/{login}/stats"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "total_messages": data.get("totalMessages", 0),
            "unique_chatters": data.get("uniqueChatters", 0),
        }
    except:
        return {}

# ============================================================================
# APIFY
# ============================================================================

def fetch_streams():
    client = ApifyClient(APIFY_TOKEN)
    
    run = client.actor(ACTOR_ID).call(run_input={
        "mode": "gameStreams",
        "gameName": GAME_NAME,
        "maxResults": 30
    })
    
    dataset_id = run.default_dataset_id
    items = list(client.dataset(dataset_id).iterate_items())
    
    return items

# ============================================================================
# ОБРАБОТКА
# ============================================================================

def process_streams(raw_items, history: dict):
    best = {}
    for item in raw_items:
        uid = item.get("id", "")
        viewers = item.get("viewersCount", 0)
        if viewers < MIN_VIEWERS:
            continue
        if uid not in best or viewers > best[uid].get("viewersCount", 0):
            best[uid] = item
    
    channels = []
    scraped_at = moscow_now_iso()
    total = len(best)
    
    for idx, (uid, item) in enumerate(best.items(), 1):
        login = item.get("broadcasterLogin", "")
        started_at_msk = to_moscow_time(item.get("startedAt", ""))
        duration_hours = 0
        if started_at_msk:
            try:
                start_str = started_at_msk.replace(" МСК", "")
                start = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                start = start.replace(tzinfo=MOSCOW_TZ)
                now = datetime.now(MOSCOW_TZ)
                duration_hours = round((now - start).total_seconds() / 3600, 1)
            except:
                pass
        
        # StreamElements
        print(f"  [{idx}/{total}] SE: {login}...", end=" ")
        se = fetch_se_stats(login)
        if se:
            print("OK")
        else:
            print("нет данных")
        
        # Предыдущий снапшот
        prev = None
        if login.lower() in history.get("channels", {}):
            snaps = history["channels"][login.lower()].get("snapshots", [])
            if snaps:
                prev = snaps[-1]
        
        current = {
            "scraped_at_msk": scraped_at,
            "viewer_count": item.get("viewersCount", 0),
            "follower_count": item.get("broadcasterFollowers", 0),
            "stream_title": item.get("title", ""),
            "started_at_msk": started_at_msk,
            "duration_hours": duration_hours,
            "total_messages": se.get("total_messages", 0),
            "unique_chatters": se.get("unique_chatters", 0),
            "ratio": round(item.get("viewersCount", 0) / max(item.get("broadcasterFollowers", 1), 1) * 100, 2),
        }
        
        # Приросты
        if prev:
            current["growth"] = {
                "viewers_change": current["viewer_count"] - prev.get("viewer_count", 0),
                "followers_change": current["follower_count"] - prev.get("follower_count", 0),
                "messages_change": current["total_messages"] - prev.get("total_messages", 0) if current["total_messages"] > 0 and prev.get("total_messages", 0) > 0 else 0,
                "chatters_change": current["unique_chatters"] - prev.get("unique_chatters", 0) if current["unique_chatters"] > 0 and prev.get("unique_chatters", 0) > 0 else 0,
            }
        else:
            current["growth"] = None
        
        channels.append({
            "user_id": uid,
            "login": login,
            "display_name": item.get("broadcasterDisplayName", ""),
            "url": item.get("url", ""),
            "snapshot": current,
        })
    
    return channels

def load_history():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return {"channels": {}}
    return {"channels": {}}

def update_history(history: dict, new_streams: list):
    now = moscow_now_iso()
    for stream in new_streams:
        login = stream["login"].lower()
        snap = stream["snapshot"]
        
        if login not in history["channels"]:
            history["channels"][login] = {
                "user_id": stream["user_id"],
                "login": stream["login"],
                "display_name": stream["display_name"],
                "url": stream["url"],
                "first_seen_msk": snap["scraped_at_msk"],
                "last_seen_msk": snap["scraped_at_msk"],
                "snapshots": []
            }
        else:
            history["channels"][login]["last_seen_msk"] = snap["scraped_at_msk"]
        
        history["channels"][login]["snapshots"].append(snap)
    
    history["last_updated_msk"] = now
    return history

def compute_aggregates(history: dict):
    for data in history["channels"].values():
        snapshots = data["snapshots"]
        if not snapshots:
            continue
        
        viewers = [s["viewer_count"] for s in snapshots]
        data["peak_viewers"] = max(viewers)
        data["avg_viewers"] = round(sum(viewers) / len(viewers), 1)
        data["total_snapshots"] = len(snapshots)
        
        if len(snapshots) >= 2:
            f = snapshots[0]
            l = snapshots[-1]
            data["total_growth"] = {
                "viewers_change": l["viewer_count"] - f["viewer_count"],
                "followers_change": l["follower_count"] - f["follower_count"],
                "messages_change": l.get("total_messages", 0) - f.get("total_messages", 0) if l.get("total_messages", 0) > 0 and f.get("total_messages", 0) > 0 else 0,
                "chatters_change": l.get("unique_chatters", 0) - f.get("unique_chatters", 0) if l.get("unique_chatters", 0) > 0 and f.get("unique_chatters", 0) > 0 else 0,
            }
        
        ratios = [s["ratio"] for s in snapshots]
        data["avg_viewer_to_follower_ratio"] = round(sum(ratios) / len(ratios), 2)
        
        msgs = [s.get("total_messages", 0) for s in snapshots if s.get("total_messages", 0) > 0]
        chatters = [s.get("unique_chatters", 0) for s in snapshots if s.get("unique_chatters", 0) > 0]
        if msgs:
            data["avg_total_messages"] = round(sum(msgs) / len(msgs), 0)
        if chatters:
            data["avg_unique_chatters"] = round(sum(chatters) / len(chatters), 0)

def print_top(history: dict):
    channels = history.get("channels", {})
    by_ratio = sorted(channels.values(), key=lambda x: x.get("avg_viewer_to_follower_ratio", 0), reverse=True)
    
    print(f"\n{'='*70}")
    print(f"ТОП-15 ПО RATIO — всего {len(channels)} каналов")
    print(f"{'='*70}")
    print(f"{'Логин':<22} {'Пик':>5} {'Сред':>5} {'Ratio%':>7} {'Сообщ':>10} {'Уник':>6} {'Снэпов':>6}")
    print("-" * 70)
    
    for ch in by_ratio[:15]:
        login = ch["login"][:21]
        peak = ch.get("peak_viewers", 0)
        avg = ch.get("avg_viewers", 0)
        ratio = ch.get("avg_viewer_to_follower_ratio", 0)
        msgs = ch.get("avg_total_messages", 0)
        uniq = ch.get("avg_unique_chatters", 0)
        snaps = ch.get("total_snapshots", 0)
        print(f"{login:<22} {peak:>5} {avg:>5} {ratio:>6.2f}% {msgs:>10,.0f} {uniq:>6,.0f} {snaps:>6}")

# ============================================================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================================================

def run_once():
    print(f"\n{'='*70}")
    print(f"СКАНИРОВАНИЕ — {moscow_now_display()}")
    print(f"{'='*70}")
    
    history = load_history()
    print(f"[ИСТОРИЯ] Каналов в базе: {len(history.get('channels', {}))}")
    
    raw = fetch_streams()
    if not raw:
        print("[ОШИБКА] Нет данных, пропускаю.")
        return history
    
    streams = process_streams(raw, history)
    print(f"[СТРИМЫ] Подходит (≥{MIN_VIEWERS}): {len(streams)}")
    
    history = update_history(history, streams)
    compute_aggregates(history)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    
    print(f"[СОХРАНЕНО] → {OUTPUT_FILE}")
    print_top(history)
    
    return history

def main():
    print("=" * 70)
    print("АВТО-СКАНЕР JUST CHATTING")
    print(f"Интервал: каждые {INTERVAL_MINUTES} минут")
    print(f"Запуск: {moscow_now_display()}")
    print("Нажмите Ctrl+C для остановки")
    print("=" * 70)
    
    cycle = 0
    
    try:
        while True:
            cycle += 1
            print(f"\n{'#'*70}")
            print(f"ЦИКЛ #{cycle} — {moscow_now_display()}")
            print(f"{'#'*70}")
            
            run_once()
            
            print(f"\n⏳ Следующий цикл через {INTERVAL_MINUTES} минут...")
            time.sleep(INTERVAL_MINUTES * 60)
    
    except KeyboardInterrupt:
        print(f"\n\n{'='*70}")
        print(f"ОСТАНОВЛЕНО. Всего циклов: {cycle}")
        print(f"Время: {moscow_now_display()}")
        print(f"Данные: {OUTPUT_FILE}")
        print(f"{'='*70}")

if __name__ == "__main__":
    if "--worker" not in sys.argv:
        main()