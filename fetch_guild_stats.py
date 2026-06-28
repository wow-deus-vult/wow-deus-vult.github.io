"""
fetch_guild_stats.py — Deus Vult / FreedomUA
Збирає статистику рейдів гільдії:
- Кількість рейдів ЦЛК 25хм (12+ наших гравців)
- Кількість рейдів РС 25хм (12+ наших гравців)
- Кількість вбивств Ліча по гравцях
Результат: data/guild-stats.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/guild-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0"}

GUILD_UPLOADERS = [
    "Denmark", "Bonem", "Sweden", "Norway", "Калабаня", "Лісовиця",
    "Пірофобія", "Содахарчова", "Чіпічапа", "Капуста", "Зорекрила",
    "Сількамяна", "Тайтус", "Закарпайтус", "Шатайтус",
]

EXTRA_LOGS = [
    "26-03-23--19-25--Bonem--FreedomUA",
    "26-04-05--19-36--Bonem--FreedomUA",
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


def get_guild_logs():
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
    print(f"Логів для обробки: {len(log_ids)}")
    return log_ids


def parse_log(log_id, members):
    url = f"{BASE_URL}/reports/{log_id}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None

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


if __name__ == "__main__":
    print("=== Збирач статистики рейдів Deus Vult ===\n")

    members = parse_epgp_members()
    log_ids = get_guild_logs()

    print(f"\nОбробляємо {len(log_ids)} логів...\n")

    icc_raids = 0
    rs_raids = 0
    lich_kills_per_player = {}

    for i, log_id in enumerate(log_ids):
        print(f"[{i+1}/{len(log_ids)}] {log_id}...", end=" ", flush=True)
        result = parse_log(log_id, members)

        if not result:
            print("пропущено")
            continue

        guild_count = len(result["guild_players"])
        print(f"{guild_count} наших | ЦЛК: {len(result['icc_kills'])} | РС: {len(result['rs_kills'])}")

        if guild_count >= MIN_GUILD_PLAYERS:
            if result["icc_kills"]:
                icc_raids += 1
            if result["rs_kills"]:
                rs_raids += 1
            if result["has_lich_king_kill"]:
                for name in result["guild_players"]:
                    lich_kills_per_player[name] = lich_kills_per_player.get(name, 0) + 1

        time.sleep(2.0)

    stats = {
        "icc_raids": icc_raids,
        "rs_raids": rs_raids,
        "lich_king_kills": len(lich_kills_per_player),
        "lich_kills_per_player": lich_kills_per_player,
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"\n=== Результат ===")
    print(f"Рейдів ЦЛК 25хм: {icc_raids}")
    print(f"Рейдів РС 25хм: {rs_raids}")
    print(f"Гравців з вбивствами Ліча: {len(lich_kills_per_player)}")
    if lich_kills_per_player:
        top = sorted(lich_kills_per_player.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"Топ-5 по вбивствах Ліча: {top}")
    print(f"Збережено: {OUTPUT}")
