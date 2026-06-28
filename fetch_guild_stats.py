"""
fetch_guild_stats.py — Deus Vult / FreedomUA
Збирає статистику рейдів гільдії.
Результат: data/guild-stats.json

Черга незавантажених логів: data/pending_logs.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue

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

EXTRA_LOGS = [
    "25-12-03--19-10--Bonem--FreedomUA",
    "25-12-03--20-44--Bonem--FreedomUA",
    "25-12-07--19-21--Norway--FreedomUA",
    "25-12-08--19-13--Norway--FreedomUA",
    "25-12-08--20-09--Denmark--FreedomUA",
    "26-03-15--19-30--Denmark--FreedomUA",
    "26-03-15--22-56--Denmark--FreedomUA",
    "26-03-16--19-37--Norway--FreedomUA",
    "26-03-16--21-44--Norway--FreedomUA",
    "26-03-17--19-27--Norway--FreedomUA",
    "26-03-17--20-28--Bonem--FreedomUA",
    "26-03-17--21-06--Sweden--FreedomUA",
    "26-03-18--19-30--Bonem--FreedomUA",
    "26-03-19--19-24--Bonem--FreedomUA",
    "26-03-22--19-36--Norway--FreedomUA",
    "26-03-22--22-05--Norway--FreedomUA",
    "26-03-23--19-25--Bonem--FreedomUA",
    "26-03-24--19-31--Denmark--FreedomUA",
    "26-03-25--19-30--Norway--FreedomUA",
    "26-03-25--20-26--Denmark--FreedomUA",
    "26-03-26--19-05--Sweden--FreedomUA",
    "26-03-29--19-34--Bonem--FreedomUA",
    "26-03-29--22-33--Bonem--FreedomUA",
    "26-03-30--19-27--Калабаня--FreedomUA",
    "26-03-30--19-29--Denmark--FreedomUA",
    "26-03-31--19-30--Norway--FreedomUA",
    "26-03-31--22-06--Norway--FreedomUA",
    "26-04-02--19-21--Sweden--FreedomUA",
    "26-04-05--19-36--Bonem--FreedomUA",
    "26-04-05--22-25--Bonem--FreedomUA",
    "26-04-06--19-26--Denmark--FreedomUA",
    "26-04-06--19-26--Калабаня--FreedomUA",
    "26-04-07--19-32--Norway--FreedomUA",
    "26-04-07--22-36--Norway--FreedomUA",
    "26-04-08--19-25--Norway--FreedomUA",
    "26-04-12--19-35--Зорекрила--FreedomUA",
    "26-04-12--22-46--Bonem--FreedomUA",
    "26-04-13--19-20--Denmark--FreedomUA",
    "26-04-13--21-48--Denmark--FreedomUA",
    "26-04-14--19-17--Norway--FreedomUA",
    "26-04-15--19-31--Norway--FreedomUA",
    "26-04-15--22-24--Norway--FreedomUA",
    "26-04-19--19-31--Bonem--FreedomUA",
    "26-04-19--22-25--Bonem--FreedomUA",
    "26-04-20--19-26--Denmark--FreedomUA",
    "26-04-20--23-03--Denmark--FreedomUA",
    "26-04-22--19-35--Norway--FreedomUA",
    "26-04-26--19-33--Зорекрила--FreedomUA",
    "26-04-27--19-37--Калабаня--FreedomUA",
    "26-04-27--21-24--Denmark--FreedomUA",
    "26-04-28--19-21--Norway--FreedomUA",
    "26-04-29--19-49--Norway--FreedomUA",
    "26-04-29--22-34--Norway--FreedomUA",
    "26-05-03--19-39--Denmark--FreedomUA",
    "26-05-03--23-04--Denmark--FreedomUA",
    "26-05-04--19-57--Bonem--FreedomUA",
    "26-05-06--20-06--Norway--FreedomUA",
    "26-05-10--19-27--Bonem--FreedomUA",
    "26-05-11--19-48--Содахарчова--FreedomUA",
    "26-05-12--19-53--Denmark--FreedomUA",
    "26-05-13--19-59--Чіпічапа--FreedomUA",
    "26-05-14--19-54--Sweden--FreedomUA",
    "26-05-14--21-23--Sweden--FreedomUA",
    "26-05-17--19-23--Denmark--FreedomUA",
    "26-05-17--21-38--Denmark--FreedomUA",
    "26-05-17--22-17--Norway--FreedomUA",
    "26-05-18--19-53--Sweden--FreedomUA",
    "26-05-18--22-17--Sweden--FreedomUA",
    "26-05-19--19-57--Капуста--FreedomUA",
    "26-05-20--19-51--Чіпічапа--FreedomUA",
    "26-05-24--19-00--Norway--FreedomUA",
    "26-05-24--21-56--Norway--FreedomUA",
    "26-05-25--20-03--Bonem--FreedomUA",
    "26-05-25--22-32--Bonem--FreedomUA",
    "26-05-25--22-51--Bonem--FreedomUA",
    "26-05-26--19-49--Sweden--FreedomUA",
    "26-05-26--20-57--Denmark--FreedomUA",
    "26-05-28--21-07--Sweden--FreedomUA",
    "26-05-31--19-23--Bonem--FreedomUA",
    "26-05-31--23-06--Bonem--FreedomUA",
    "26-06-01--20-06--Denmark--FreedomUA",
    "26-06-01--23-07--Denmark--FreedomUA",
    "26-06-02--19-52--Чіпічапа--FreedomUA",
    "26-06-02--20-27--Содахарчова--FreedomUA",
    "26-06-03--20-01--Sweden--FreedomUA",
    "26-06-03--22-27--Sweden--FreedomUA",
    "26-06-07--19-19--Bonem--FreedomUA",
    "26-06-07--22-49--Bonem--FreedomUA",
    "26-06-08--22-00--Norway--FreedomUA",
    "26-06-09--19-40--Пірофобія--FreedomUA",
    "26-06-10--20-04--Пірофобія--FreedomUA",
    "26-06-10--23-37--Пірофобія--FreedomUA",
    "26-06-14--19-40--Norway--FreedomUA",
    "26-06-14--22-02--Norway--FreedomUA",
    "26-06-15--19-44--Denmark--FreedomUA",
    "26-06-15--22-31--Лісовиця--FreedomUA",
    "26-06-16--19-40--Sweden--FreedomUA",
    "26-06-17--19-18--Sweden--FreedomUA",
    "26-06-17--19-49--Sweden--FreedomUA",
    "26-06-21--19-37--Denmark--FreedomUA",
    "26-06-21--22-00--Denmark--FreedomUA",
    "26-06-22--20-29--Bonem--FreedomUA",
    "26-06-22--23-10--Калабаня--FreedomUA",
    "26-06-23--21-41--Sweden--FreedomUA",
]

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
            print("  ⚠ 429, чекаємо 10с...", end=" ", flush=True)
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


def load_stats_cache():
    cache = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache):
        return {"icc_raids": 0, "rs_raids": 0, "lich_king_kills": 0, "lich_kills_per_player": {}}
    with open(cache, encoding="utf-8") as f:
        return json.load(f)


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

    queue = LogQueue()
    all_ids = get_all_log_ids()
    queue.add_logs(all_ids)

    stats = load_stats_cache()
    print(f"  Кеш: ЦЛК={stats['icc_raids']} РС={stats['rs_raids']} Ліч={len(stats['lich_kills_per_player'])}")

    pending = queue.iter_pending()
    total_pending = len(pending)
    print(f"\nОбробляємо {total_pending} логів з черги...\n")

    processed = 0
    skipped = 0

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total_pending}] {log_id}...", end=" ", flush=True)
        result = parse_log(log_id, members)
        if not result:
            print("пропущено (лишається в черзі)")
            skipped += 1
            continue

        guild_count = len(result["guild_players"])
        print(f"{guild_count} наших | ЦЛК: {len(result['icc_kills'])} | РС: {len(result['rs_kills'])}")

        if guild_count >= MIN_GUILD_PLAYERS:
            if result["icc_kills"]:
                stats["icc_raids"] += 1
            if result["rs_kills"]:
                stats["rs_raids"] += 1
            if result["has_lich_king_kill"]:
                stats["lich_king_kills"] = stats.get("lich_king_kills", 0) + 1
                for name in result["guild_players"]:
                    stats["lich_kills_per_player"][name] = \
                        stats["lich_kills_per_player"].get(name, 0) + 1

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
    print(f"\n✓ Збережено: {OUTPUT}")
