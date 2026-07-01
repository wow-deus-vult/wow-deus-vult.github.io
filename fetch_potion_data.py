"""
fetch_potion_data.py -- Deus Vult / FreedomUA
Збирає статистику потів з /consumables/ сторінок uwu-logs
Результат: data/potion-stats.json

Черга незавантажених логів: data/pending_logs.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue
from dedup_helper import load_duplicate_map, is_duplicate_log

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/potion-stats.json"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}
DELAY    = 4.0

GUILD_UPLOADERS = [
    "Denmark", "Bonem", "Sweden", "Norway", "Калабаня", "Лісовиця",
    "Пірофобія", "Содахарчова", "Чіпічапа", "Капуста", "Зорекрила",
    "Сількамяна", "Тайтус", "Закарпайтус", "Шатайтус",
]

EXTRA_LOGS = json.load(open("extra_logs.json", encoding="utf-8"))["extra_logs"]

POTION_COLUMNS = {
    "Potion of Speed":        "potionOfSpeed",
    "Potion of Wild Magic":   "potionOfWildMagic",
    "Insane Strength Potion": "insaneStrength",
    "Flame Cap":              "flameCap",
    "Indestructible Potion":  "indestructiblePotion",
}


def safe_get(url):
    time.sleep(DELAY)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            return r
        if r.status_code == 429:
            print(f"  ! 429, чекаємо 10с...", end=" ", flush=True)
            time.sleep(10)
            r2 = requests.get(url, headers=HEADERS, timeout=15)
            if r2.status_code == 200:
                return r2
            print(f"  ERR retry={r2.status_code}", end=" ", flush=True)
        else:
            print(f"  ERR {r.status_code}", end=" ", flush=True)
        return None
    except Exception as e:
        print(f"  ERR exception={e}", end=" ", flush=True)
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
        row = {"name": name, "total": 0}
        for potion_name, key in POTION_COLUMNS.items():
            idx = col_indices.get(potion_name)
            try:
                row[key] = int(tds[idx].get_text(strip=True)) if idx is not None and idx < len(tds) else 0
            except Exception:
                row[key] = 0
        # Рахуємо total самостійно як суму наших потів
        row["total"] = sum(row[key] for key in POTION_COLUMNS.values())
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


def load_raids_cache():
    cache = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache):
        return []
    with open(cache, encoding="utf-8") as f:
        return json.load(f)


def save_raids_cache(raids):
    import os
    cache = OUTPUT.replace(".json", "_cache.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(raids, f, ensure_ascii=False)


def deduplicate_raids(raids):
    """
    Прибирає дублі рейдів: якщо два логи з тієї ж дати (або +1 день)
    мають 12+ спільних гравців -- це частини одного реального рейду.
    З групи дублів лишаємо ОДИН лог -- той з найбільшою кількістю гравців.
    """
    if not raids:
        return raids

    from datetime import date as date_cls

    def to_date(d):
        return date_cls.fromisoformat(d) if isinstance(d, str) else d

    sorted_raids = sorted(enumerate(raids), key=lambda x: to_date(x[1]["date"]))

    used = set()
    groups = []

    for i, (orig_i, r) in enumerate(sorted_raids):
        if orig_i in used:
            continue
        group = [orig_i]
        used.add(orig_i)
        players_i = {p["name"] for p in r["players"]}
        date_i = to_date(r["date"])

        for j in range(i + 1, len(sorted_raids)):
            orig_j, r2 = sorted_raids[j]
            if orig_j in used:
                continue
            date_j = to_date(r2["date"])
            day_diff = abs((date_j - date_i).days)
            if day_diff > 1:
                break
            players_j = {p["name"] for p in r2["players"]}
            overlap = len(players_i & players_j)
            if overlap >= 12:
                group.append(orig_j)
                used.add(orig_j)

        groups.append(group)

    deduped = []
    merged_count = 0
    for group in groups:
        if len(group) == 1:
            deduped.append(raids[group[0]])
            continue
        merged_count += len(group) - 1
        # Лишаємо лог з найбільшою кількістю гравців (найповніший)
        best_idx = max(group, key=lambda idx: len(raids[idx]["players"]))
        deduped.append(raids[best_idx])

    if merged_count:
        print(f"  \U0001f501 Дедуплікація: прибрано {merged_count} дублікат(ів) рейдів")

    return deduped


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


def save_output(raids):
    import os
    raids = deduplicate_raids(raids)
    honor_board = build_honor_board(raids)
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "totalRaids": len(raids),
        "raids": raids,
        "honorBoard": honor_board,
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import os
    print("=== Збирач статистики потів Deus Vult ===\n")
    members = parse_epgp_members()

    queue = LogQueue("data/pending_potion.json")
    all_ids = get_all_log_ids()
    queue.add_logs(all_ids)

    raids = load_raids_cache()
    print(f"  Рейдів у кеші: {len(raids)}")

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

        result = parse_consumables(log_id, members)
        if result:
            raids.append(result)
            queue.mark_done(log_id)
            save_raids_cache(raids)
            save_output(raids)
            processed += 1
            print(f"OK {len(result['players'])} гравців")
        else:
            print("пропущено (лишається в черзі)")
            skipped += 1

    save_output(raids)
    print(f"\n=== Результат ===")
    print(f"  Оброблено цього разу: {processed}")
    print(f"  Залишилось в черзі:   {queue.pending_count}")
    print(f"  Всього рейдів:        {len(raids)}")
    print(f"  Гравців в дошці:      {len(build_honor_board(raids))}")
    print(f"\nOK Збережено: {OUTPUT}")
