"""
fetch_guild_stats.py — Deus Vult / FreedomUA
Збирає статистику рейдів гільдії:
- Кількість рейдів ЦЛК 25хм (12+ наших гравців)
- Кількість рейдів РС 25хм (12+ наших гравців)
- Кількість вбивств Ліча по гравцях

Запуск: python fetch_guild_stats.py
Результат: data/guild-stats.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/guild-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0"}

# Боси ЦЛК (якщо є хоч один — це ЦЛК рейд)
ICC_BOSSES = {
    "lord-marrowgar", "lady-deathwhisper", "deathbringer-saurfang",
    "festergut", "rotface", "professor-putricide", "blood-prince-council",
    "blood-queen-lanathel", "sindragosa", "the-lich-king", "valithria-dreamwalker",
    "gunship-battle",
}

# Боси РС
RS_BOSSES = {
    "halion", "saviana-ragefire", "general-zarithrian", "baltharus-the-warborn",
}

LICH_KING_BOSS = "the-lich-king"

# Мінімум наших гравців в рейді щоб вважати його рейдом гільдії
MIN_GUILD_PLAYERS = 12


def parse_epgp_members():
    with open('EPGP.lua', encoding='utf-8') as f:
        content = f.read()
    pattern = re.compile(
        r'\["time"\]\s*=\s*(\d+).*?\["roster_info"\]\s*=\s*\{(.*?)\},\s*\n\s*\}',
        re.DOTALL
    )
    snapshots = list(pattern.finditer(content))
    latest = max(snapshots, key=lambda m: int(m.group(1)))
    names = set(re.findall(r'"([^"]+)",\s*--\s*\[1\]', latest.group(2)))
    print(f"  EPGP: {len(names)} гравців")
    return names


def get_all_freedom_logs():
    print("Збираємо список логів FreedomUA...")
    log_ids = []
    visited = set()
    empty_months = 0
    url = f"{BASE_URL}/logs_list"

    while empty_months < 3:
        if url in visited:
            break
        visited.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, 'html.parser')
            found = 0
            for a in soup.find_all("a", href=True):
                if SERVER in a.get_text() and "/reports/" in a["href"]:
                    log_id = a["href"].strip("/").replace("reports/", "")
                    if log_id and log_id not in log_ids:
                        log_ids.append(log_id)
                        found += 1
            empty_months = 0 if found else empty_months + 1
            print(f"  {url} | +{found} | всього: {len(log_ids)}")
            prev = soup.find("a", string=re.compile(r"<<"))
            if not prev or not prev.get("href"):
                break
            href = prev["href"]
            url = BASE_URL + href if href.startswith("/") else BASE_URL + "/" + href
            time.sleep(0.3)
        except Exception as e:
            print(f"  Помилка: {e}")
            break

    print(f"Всього логів: {len(log_ids)}")
    return log_ids


def parse_log(log_id, members):
    """
    Парсить головну сторінку логу.
    Повертає dict з:
    - guild_players: список наших гравців в рейді
    - icc_kills: список кіл-босів ЦЛК
    - rs_kills: список кіл-босів РС
    - has_lich_king_kill: чи є кіл Ліча
    """
    url = f"{BASE_URL}/reports/{log_id}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return None

    # Знаходимо всіх гравців рейду (посилання на /player/)
    guild_players = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/player/" in href:
            # /reports/log_id/player/PlayerName/
            parts = href.strip("/").split("/")
            if len(parts) >= 3:
                name = parts[-1]
                if name in members:
                    guild_players.add(name)

    # Знаходимо kill-link боси
    icc_kills = []
    rs_kills = []
    has_lich_king_kill = False

    for a in soup.find_all("a", class_="kill-link"):
        href = a.get("href", "")
        # ?boss=the-lich-king&mode=25H&...
        boss_match = re.search(r"boss=([^&]+)", href)
        mode_match = re.search(r"mode=([^&]+)", href)
        if not boss_match:
            continue
        boss = boss_match.group(1).lower()
        mode = mode_match.group(1) if mode_match else ""

        if "25" not in mode:
            continue

        if boss in ICC_BOSSES:
            icc_kills.append(boss)
            if boss == LICH_KING_BOSS:
                has_lich_king_kill = True
        elif boss in RS_BOSSES:
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
    log_ids = get_all_freedom_logs()

    # ТЕСТ: тільки 10 логів
    log_ids = log_ids[:10]
    print(f"\nТестуємо на {len(log_ids)} логах...\n")

    icc_raids = 0
    rs_raids = 0
    lich_kills_per_player = {}  # name → count

    for i, log_id in enumerate(log_ids):
        print(f"[{i+1}/{len(log_ids)}] {log_id}...", end=" ", flush=True)
        result = parse_log(log_id, members)

        if not result:
            print("404")
            continue

        guild_count = len(result["guild_players"])
        print(f"{guild_count} наших | ЦЛК кіли: {result['icc_kills']} | РС: {result['rs_kills']}")

        if guild_count >= MIN_GUILD_PLAYERS:
            if result["icc_kills"]:
                icc_raids += 1
            if result["rs_kills"]:
                rs_raids += 1

            if result["has_lich_king_kill"]:
                for name in result["guild_players"]:
                    lich_kills_per_player[name] = lich_kills_per_player.get(name, 0) + 1

        time.sleep(0.3)

    print(f"\n=== Результат (тест 10 логів) ===")
    print(f"Рейдів ЦЛК 25хм: {icc_raids}")
    print(f"Рейдів РС 25хм: {rs_raids}")
    print(f"Гравців з вбивствами Ліча: {len(lich_kills_per_player)}")
    if lich_kills_per_player:
        top = sorted(lich_kills_per_player.items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"Топ-5 по вбивствах Ліча: {top}")
