"""
fetch_potion_data.py — Deus Vult / FreedomUA
Збирає статистику потів з /consumables/ сторінок uwu-logs
Запуск: python fetch_potion_data.py
Результат: data/potion-stats.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/potion-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}

POTION_COLUMNS = {
    "Potion of Speed":        "potionOfSpeed",
    "Potion of Wild Magic":   "potionOfWildMagic",
    "Insane Strength Potion": "insaneStrength",
    "Flame Cap":              "flameCap",
    "Destruction Potion":     "destructionPotion",
}


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


def parse_consumables(log_id, members):
    url = f"{BASE_URL}/reports/{log_id}/consumables/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        return None

    tbody = soup.find('tbody', id='potions-table-body')
    thead = soup.find('thead')
    if not tbody or not thead:
        return None

    col_indices = {}
    for i, th in enumerate(thead.find_all('th')):
        title = th.get('title', '')
        if title in POTION_COLUMNS:
            col_indices[title] = i

    players = []
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        player_cell = tr.find('td', class_='player-cell')
        if not player_cell:
            continue
        a = player_cell.find('a')
        if not a:
            continue
        name = a.get_text(strip=True)
        if name not in members:
            continue
        try:
            total = int(tds[1].get_text(strip=True)) if len(tds) > 1 else 0
        except:
            total = 0
        row = {'name': name, 'total': total}
        for potion_name, key in POTION_COLUMNS.items():
            idx = col_indices.get(potion_name)
            try:
                row[key] = int(tds[idx].get_text(strip=True)) if idx and idx < len(tds) else 0
            except:
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
    log_ids = get_all_freedom_logs()

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
        time.sleep(0.3)

        if (i + 1) % 10 == 0:
            save(raids)

    save(raids)
    print(f"\n✓ Готово! {OUTPUT}")
    print(f"  Рейдів: {len(raids)}")
    print(f"  Гравців в дошці: {len(build_honor_board(raids))}")
