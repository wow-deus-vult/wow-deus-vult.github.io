"""
fetch_potion_data.py — Deus Vult / FreedomUA
Збирає статистику потів з /consumables/ сторінок uwu-logs
Результат: data/potion-stats.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/potion-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}

GUILD_UPLOADERS = [
    "Denmark", "Bonem", "Sweden", "Norway", "Калабаня", "Лісовиця",
    "Пірофобія", "Содахарчова", "Чіпічапа", "Капуста", "Зорекрила",
    "Сількамяна", "Тайтус", "Закарпайтус", "Шатайтус",
]

EXTRA_LOGS = [
    "26-03-23--19-25--Bonem--FreedomUA",
    "26-04-05--19-36--Bonem--FreedomUA",
]

POTION_COLUMNS = {
    "Potion of Speed":        "potionOfSpeed",
    "Potion of Wild Magic":   "potionOfWildMagic",
    "Insane Strength Potion": "insaneStrength",
    "Flame Cap":              "flameCap",
    "Indestructible Potion":  "indestructiblePotion",
}


def check_connection():
    try:
        r = requests.get(f"{BASE_URL}/logs_list", headers=HEADERS, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def wait_for_connection():
    if check_connection():
        return True
    print("  ⚠ Сайт недоступний, чекаємо 2с...")
    time.sleep(2)
    if check_connection():
        return True
    print("  ✗ Сайт так і не відповів, пропускаємо")
    return False


def safe_get(url):
    if not wait_for_connection():
        return None
    time.sleep(4)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r
        return None
    except Exception:
        return None


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


def parse_consumables(log_id, members):
    url = f"{BASE_URL}/reports/{log_id}/consumables/"
    r = safe_get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    tbody = soup.find("tbody", id="potions-table-body")
    thead = soup.find("thead")
    if not tbody or not thead:
        return None

    col_indices = {}
    for i, th in enumerate(thead.find_all("th")):
        title = th.get("title", "")
        if title in POTION_COLUMNS:
            col_indices[title] = i

    players = []
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        pc = tr.find("td", class_="player-cell")
        if not pc:
            continue
        a = pc.find("a")
        if not a:
            continue
        name = a.get_text(strip=True)
        if name not in members:
            continue
        try:
            total = int(tds[1].get_text(strip=True)) if len(tds) > 1 else 0
        except Exception:
            total = 0
        row = {"name": name, "total": total}
        for potion_name, key in POTION_COLUMNS.items():
            idx = col_indices.get(potion_name)
            try:
                row[key] = int(tds[idx].get_text(strip=True)) if idx is not None and idx < len(tds) else 0
            except Exception:
                row[key] = 0
        players.append(row)

    if not players:
        return None

    parts = log_id.split("--")
    date_parts = parts[0].split("-")
    date_str = f"20{date_parts[0]}-{date_parts[1]}-{date_parts[2]}"
    uploader = parts[-2] if len(parts) >= 2 else ""

    return {
        "raidUrl": f"{BASE_URL}/reports/{log_id}/",
        "consumablesUrl": url,
        "date": date_str,
        "uploader": uploader,
        "players": sorted(players, key=lambda p: p["total"], reverse=True),
    }


def build_honor_board(raids):
    player_stats = {}
    for raid in raids:
        for p in raid["players"]:
            name = p["name"]
            if name not in player_stats:
                player_stats[name] = {
                    "name": name, "raids": 0, "totalPotions": 0,
                    **{key: 0 for key in POTION_COLUMNS.values()}
                }
            player_stats[name]["raids"] += 1
            player_stats[name]["totalPotions"] += p["total"]
            for key in POTION_COLUMNS.values():
                player_stats[name][key] += p.get(key, 0)

    board = list(player_stats.values())
    for p in board:
        p["avgPerRaid"] = round(p["totalPotions"] / p["raids"], 2) if p["raids"] > 0 else 0
    board.sort(key=lambda p: p["avgPerRaid"], reverse=True)
    return board


def save(raids):
    honor_board = build_honor_board(raids)
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "totalRaids": len(raids),
        "raids": raids,
        "honorBoard": honor_board,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== Збирач статистики потів Deus Vult ===\n")
    members = parse_epgp_members()
    log_ids = get_guild_logs()

    raids = []
    total = len(log_ids)
    for i, log_id in enumerate(log_ids):
        print(f"[{i+1}/{total}] {log_id}...", end=" ", flush=True)
        result = parse_consumables(log_id, members)
        if result:
            raids.append(result)
            print(f"✓ {len(result['players'])} гравців")
        else:
            print("пропущено")

        if (i + 1) % 10 == 0:
            save(raids)

    save(raids)
    print(f"\n✓ Готово! {OUTPUT}")
    print(f"  Рейдів: {len(raids)}")
    print(f"  Гравців в дошці: {len(build_honor_board(raids))}")
