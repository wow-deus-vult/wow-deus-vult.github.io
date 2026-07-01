"""
fetch_guild_stats.py -- Deus Vult / FreedomUA
Збирає статистику рейдів гільдії.
Результат: data/guild-stats.json

Черга незавантажених логів: data/pending_logs.json
"""

import json, re, time, requests
from datetime import datetime, timezone, date as date_cls
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue
from dedup_helper import load_duplicate_map, is_duplicate_log

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/guild-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0"}
DELAY    = 4.0

GUILD_UPLOADERS = [
    "Denmark", "Bonem", "Sweden", "Norway", "Калабаня", "Лісовиця",
    "Пірофобія", "Содахарчова", "Чіпічапа", "Капуста", "Зорекрила",
    "Сількамяна", "Тайтус", "Закарпайтус", "Шатайтус",
]

EXTRA_LOGS = json.load(open("extra_logs.json", encoding="utf-8"))["extra_logs"]

ICC_BOSSES = {
    "lord-marrowgar", "lady-deathwhisper", "deathbringer-saurfang",
    "festergut", "rotface", "professor-putricide", "blood-prince-council",
    "blood-queen-lanathel", "sindragosa", "the-lich-king", "valithria-dreamwalker",
    "gunship-battle",
}
RS_BOSSES = {
    "halion", "saviana-ragefire", "general-zarithrian", "baltharus-the-warborn",
}
LICH_KING_BOSS = "the-lich-king"
MIN_GUILD_PLAYERS = 12


def safe_get(url):
    time.sleep(DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            print("  ! 429, чекаємо 10с...", end=" ", flush=True)
            time.sleep(10)
            r2 = requests.get(url, headers=HEADERS, timeout=15)
            if r2.status_code == 200:
                return r2
        return None
    except Exception:
        return None


def get_all_log_ids():
    print("Збираємо список логів FreedomUA...")
    r = requests.get(f"{BASE_URL}/logs_list", headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    log_ids = []
    for a in soup.find_all("a", href=True):
        if SERVER in a.get_text() and "/reports/" in a["href"]:
            log_id = a["href"].strip("/").replace("reports/", "")
            if log_id and any(u in log_id for u in GUILD_UPLOADERS):
                log_ids.append(log_id)
    for log_id in EXTRA_LOGS:
        if log_id not in log_ids:
            log_ids.append(log_id)
    log_ids.sort(reverse=True)
    print(f"  Знайдено: {len(log_ids)} логів")
    return log_ids


def parse_log(log_id, members):
    url = f"{BASE_URL}/reports/{log_id}/"
    r = safe_get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    guild_players = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/player/" in href:
            parts = href.strip("/").split("/")
            if len(parts) >= 3:
                name = parts[-1]
                if name in members:
                    guild_players.add(name)
    icc_kills, rs_kills = [], []
    has_lich_king_kill = False
    for a in soup.find_all("a", class_="kill-link"):
        href = a.get("href", "")
        boss_match = re.search(r"boss=([^&]+)", href)
        mode_match = re.search(r"mode=([^&]+)", href)
        if not boss_match:
            continue
        boss = boss_match.group(1).lower()
        mode = mode_match.group(1) if mode_match else ""
        if "25" not in mode:
            continue
        if boss in ICC_BOSSES:
            if boss not in icc_kills:
                icc_kills.append(boss)
            if boss == LICH_KING_BOSS:
                has_lich_king_kill = True
        elif boss in RS_BOSSES:
            if boss not in rs_kills:
                rs_kills.append(boss)
    return {
        "guild_players": list(guild_players),
        "icc_kills": icc_kills,
        "rs_kills": rs_kills,
        "has_lich_king_kill": has_lich_king_kill,
    }


def log_id_to_date_str(log_id):
    parts = log_id.split("--")
    yy, mm, dd = parts[0].split("-")
    return f"20{yy}-{mm}-{dd}"


def is_duplicate_raid(log_id, guild_players, counted_raids):
    """Перевіряє чи цей лог -- частина вже врахованого рейду (12+ спільних гравців, дата ±1 день)."""
    try:
        d = date_cls.fromisoformat(log_id_to_date_str(log_id))
    except Exception:
        return False
    players_set = set(guild_players)
    for cr in counted_raids:
        try:
            cr_date = date_cls.fromisoformat(cr["date"])
        except Exception:
            continue
        if abs((cr_date - d).days) > 1:
            continue
        overlap = len(players_set & set(cr["players"]))
        if overlap >= 12:
            return True
    return False


def load_stats_cache():
    cache = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache):
        return {"icc_raids": 0, "rs_raids": 0, "lich_king_kills": 0,
                "lich_kills_per_player": {}, "counted_raids": []}
    with open(cache, encoding="utf-8") as f:
        data = json.load(f)
        data.setdefault("counted_raids", [])
        return data


def save_stats_cache(stats):
    import os
    cache = OUTPUT.replace(".json", "_cache.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)


def save_output(stats):
    import os
    data = {
        "icc_raids": stats["icc_raids"],
        "rs_raids": stats["rs_raids"],
        "lich_king_kills": stats.get("lich_king_kills", 0),
        "lich_kills_per_player": stats["lich_kills_per_player"],
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import os
    print("=== Збирач статистики рейдів Deus Vult ===\n")
    members = parse_epgp_members()

    queue = LogQueue("data/pending_guild_stats.json")
    all_ids = get_all_log_ids()
    queue.add_logs(all_ids)

    stats = load_stats_cache()
    print(f"  Кеш: ЦЛК={stats['icc_raids']} РС={stats['rs_raids']} Ліч={len(stats['lich_kills_per_player'])}")

    pending = queue.iter_pending()
    total_pending = len(pending)
    print(f"\nОбробляємо {total_pending} логів з черги...\n")

    processed = 0
    skipped = 0

    dup_map = load_duplicate_map()
    if dup_map:
        print(f"  Завантажено {len(dup_map)} відомих дублікатів логів (з total_damage)")

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total_pending}] {log_id}...", end=" ", flush=True)

        if is_duplicate_log(log_id, dup_map):
            print("дублікат (пропущено)")
            queue.mark_done(log_id)
            continue

        result = parse_log(log_id, members)
        if not result:
            print("пропущено (лишається в черзі)")
            skipped += 1
            continue

        guild_count = len(result["guild_players"])
        is_dup = guild_count >= MIN_GUILD_PLAYERS and \
                 is_duplicate_raid(log_id, result["guild_players"], stats["counted_raids"])

        print(f"{guild_count} наших | ЦЛК: {len(result['icc_kills'])} | РС: {len(result['rs_kills'])}" +
              (" | ДУБЛЬ" if is_dup else ""))

        if guild_count >= MIN_GUILD_PLAYERS and not is_dup:
            if result["icc_kills"]:
                stats["icc_raids"] += 1
            if result["rs_kills"]:
                stats["rs_raids"] += 1
            if result["has_lich_king_kill"]:
                stats["lich_king_kills"] = stats.get("lich_king_kills", 0) + 1
                for name in result["guild_players"]:
                    stats["lich_kills_per_player"][name] = \
                        stats["lich_kills_per_player"].get(name, 0) + 1
            stats["counted_raids"].append({
                "date": log_id_to_date_str(log_id),
                "players": result["guild_players"],
            })

        queue.mark_done(log_id)
        save_stats_cache(stats)
        save_output(stats)
        processed += 1

    print(f"\n=== Результат ===")
    print(f"  Оброблено цього разу: {processed}")
    print(f"  Залишилось в черзі:   {queue.pending_count}")
    print(f"  Рейдів ЦЛК 25хм:     {stats['icc_raids']}")
    print(f"  Рейдів РС 25хм:      {stats['rs_raids']}")
    print(f"  Гравців з Лічем:     {len(stats['lich_kills_per_player'])}")
    if stats["lich_kills_per_player"]:
        top = sorted(stats["lich_kills_per_player"].items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"  Топ-5 по Лічу: {top}")
    print(f"\nOK Збережено: {OUTPUT}")
