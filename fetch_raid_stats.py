"""
fetch_raid_stats.py — Deus Vult / FreedomUA
Збирає додаткову статистику рейдів:
- Тривалість кожного рейду (Custom Slice)
- Рейдовий DPS на Deathbringer Saurfang 25H (Total рядок)

Результат: data/raid-stats.json
{
    "totalRaids": 143,
    "totalTimeSeconds": 123456,
    "totalTimeHours": 34.3,
    "totalTimeDays": 1.4,
    "maxSaurfangDps": 391943.3,
    "avgSaurfangDpsS1": 350000.0,
    "saurfangKills": [
        {"logId": "...", "date": "2026-03-01", "dps": 391943.3}
    ]
}
"""

import json, os, re, time, requests
from datetime import date, datetime, timezone
from bs4 import BeautifulSoup
from log_queue import LogQueue

BASE_URL = "https://uwu-logs.xyz"
OUTPUT   = "data/raid-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}
DELAY    = 4.0

SEASONS_FILE = "seasons.json"


def safe_get(url):
    time.sleep(DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            print("  ⚠ 429, чекаємо 10с...", end=" ", flush=True)
            time.sleep(10)
            r2 = requests.get(url, headers=HEADERS, timeout=15)
            if r2.status_code == 200:
                return r2
            print(f"  ✗ retry={r2.status_code}", end=" ", flush=True)
        else:
            print(f"  ✗ {r.status_code}", end=" ", flush=True)
        return None
    except Exception as e:
        print(f"  ✗ {e}", end=" ", flush=True)
        return None


def parse_duration_seconds(time_str):
    """'3:18:12.270' або '18:12.270' -> секунди"""
    try:
        parts = time_str.strip().split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except Exception:
        pass
    return 0


def parse_log(log_id):
    """
    Повертає dict:
    - duration_seconds: тривалість рейду
    - saurfang_dps: рейдовий DPS на Saurfang 25H (або None)
    """
    url = f"{BASE_URL}/reports/{log_id}/"
    r = safe_get(url)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # Тривалість — шукаємо "Custom Slice" в заголовках секцій
    duration_seconds = 0
    for tag in soup.find_all(["h1", "h2", "h3", "div", "span"]):
        text = tag.get_text(strip=True)
        m = re.match(r"^(\d+:\d+:\d+\.\d+|\d+:\d+\.\d+)\s*Custom Slice", text)
        if m:
            duration_seconds = parse_duration_seconds(m.group(1))
            break

    # Saurfang DPS — шукаємо kill-link для saurfang 25H
    saurfang_dps = None
    for a in soup.find_all("a", class_="kill-link"):
        href = a.get("href", "")
        if "boss=deathbringer-saurfang" in href and "mode=25H" in href:
            # Беремо першу спробу (attempt=0 або найменший attempt)
            boss_url = f"{BASE_URL}/reports/{log_id}/{href}"
            rb = safe_get(boss_url)
            if rb:
                soup_b = BeautifulSoup(rb.text, "html.parser")
                # Шукаємо рядок Total в таблиці
                for tr in soup_b.find_all("tr"):
                    pc = tr.find("td", class_="player-cell")
                    if not pc:
                        continue
                    if pc.get_text(strip=True) != "Total":
                        continue
                    # Шукаємо useful DPS (per-sec-cell поряд з useful)
                    tds = tr.find_all("td")
                    for td in tds:
                        classes = td.get("class", [])
                        if "useful" in classes and "per-sec-cell" in classes:
                            val = td.get_text(strip=True).replace(" ", "").replace(",", ".")
                            try:
                                saurfang_dps = float(val)
                            except Exception:
                                pass
                            break
                    break
            break

    return {
        "duration_seconds": duration_seconds,
        "saurfang_dps": saurfang_dps,
    }


def load_seasons():
    if not os.path.exists(SEASONS_FILE):
        return []
    with open(SEASONS_FILE, encoding="utf-8") as f:
        return json.load(f).get("seasons", [])


def load_cache():
    cache = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache):
        return {}
    with open(cache, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache):
    path = OUTPUT.replace(".json", "_cache.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def log_id_to_date(log_id):
    parts = log_id.split("--")
    yy, mm, dd = parts[0].split("-")
    return date(int("20" + yy), int(mm), int(dd))


def build_output(cache, seasons):
    total_seconds = 0
    saurfang_kills = []

    for log_id, data in cache.items():
        total_seconds += data.get("duration_seconds", 0)
        dps = data.get("saurfang_dps")
        if dps:
            try:
                rdate = log_id_to_date(log_id)
            except Exception:
                continue
            saurfang_kills.append({
                "logId": log_id,
                "date": str(rdate),
                "dps": dps,
            })

    saurfang_kills.sort(key=lambda x: x["date"])

    max_dps = max((k["dps"] for k in saurfang_kills), default=0)

    # AVG per season
    today = date.today()
    current_season_avg = 0
    for s in seasons:
        s_start = date.fromisoformat(s["start"])
        s_end = date.fromisoformat(s["end"])
        if s_start <= today <= s_end:
            in_season = [k["dps"] for k in saurfang_kills
                         if s_start <= date.fromisoformat(k["date"]) <= s_end]
            if in_season:
                current_season_avg = round(sum(in_season) / len(in_season), 1)
            break

    total_hours = round(total_seconds / 3600, 1)
    total_days = round(total_seconds / 86400, 1)

    return {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "totalRaids": len(cache),
        "totalTimeSeconds": round(total_seconds),
        "totalTimeHours": total_hours,
        "totalTimeDays": total_days,
        "maxSaurfangDps": max_dps,
        "avgSaurfangDpsCurrentSeason": current_season_avg,
        "saurfangKills": saurfang_kills,
    }


if __name__ == "__main__":
    print("=== Збирач статистики рейдів Deus Vult ===\n")

    # Беремо логи з черги total_damage (там вже є всі наші логи)
    queue = LogQueue("data/pending_total_damage.json")
    all_done = list(queue.done)
    print(f"Логів для обробки: {len(all_done)}")

    seasons = load_seasons()
    cache = load_cache()
    print(f"Вже в кеші: {len(cache)}")

    # Окрема черга для цього скрипту
    my_queue = LogQueue("data/pending_raid_stats.json")
    my_queue.add_logs(all_done)

    pending = my_queue.iter_pending()
    total_pending = len(pending)
    print(f"Залишилось обробити: {total_pending}\n")

    processed = 0
    skipped = 0

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total_pending}] {log_id}...", end=" ", flush=True)
        result = parse_log(log_id)
        if not result:
            print("пропущено (лишається в черзі)")
            skipped += 1
            continue

        cache[log_id] = result
        my_queue.mark_done(log_id)
        save_cache(cache)
        processed += 1

        dur = result["duration_seconds"]
        dps = result.get("saurfang_dps")
        h = int(dur // 3600)
        m = int((dur % 3600) // 60)
        print(f"✓ {h}г {m}хв | Saurfang DPS: {dps or '—'}")

    # Будуємо фінальний JSON
    data = build_output(cache, seasons)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n=== Результат ===")
    print(f"  Оброблено цього разу: {processed}")
    print(f"  Залишилось в черзі:   {my_queue.pending_count}")
    print(f"  Всього рейдів:        {len(cache)}")
    print(f"  Загальний час:        {data['totalTimeHours']} год ({data['totalTimeDays']} днів)")
    print(f"  MAX Saurfang DPS:     {data['maxSaurfangDps']}")
    print(f"  AVG Saurfang DPS S1:  {data['avgSaurfangDpsCurrentSeason']}")
    print(f"\n✓ Збережено: {OUTPUT}")
