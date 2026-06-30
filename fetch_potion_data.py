"""
fetch_potion_data.py — Deus Vult / FreedomUA
Збирає статистику потів з /consumables/ сторінок uwu-logs
Результат: data/potion-stats.json

Черга незавантажених логів: data/pending_logs.json
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue

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
    # Січень-березень 2026
    "26-01-04--19-15--Norway--FreedomUA",
    "26-01-05--19-07--Norway--FreedomUA",
    "26-01-05--19-53--Denmark--FreedomUA",
    "26-01-05--20-26--Bonem--FreedomUA",
    "26-01-06--19-22--Denmark--FreedomUA",
    "26-01-07--19-12--Bonem--FreedomUA",
    "26-01-07--20-28--Bonem--FreedomUA",
    "26-01-11--19-12--Bonem--FreedomUA",
    "26-01-12--19-13--Norway--FreedomUA",
    "26-01-12--20-03--Bonem--FreedomUA",
    "26-01-25--19-13--Тайтус--FreedomUA",
    "26-01-26--19-09--Шатайтус--FreedomUA",
    "26-01-26--20-13--Шатайтус--FreedomUA",
    "26-01-28--19-44--Тайтус--FreedomUA",
    "26-02-01--19-37--Тайтус--FreedomUA",
    "26-02-02--19-09--Шатайтус--FreedomUA",
    "26-02-03--19-22--Закарпайтус--FreedomUA",
    "26-02-03--22-58--Шатайтус--FreedomUA",
    "26-02-19--19-32--Тайтус--FreedomUA",
    "26-02-23--19-16--Содахарчова--FreedomUA",
    "26-02-23--22-08--Калабаня--FreedomUA",
    "26-02-24--19-24--Капуста--FreedomUA",
    "26-02-25--19-32--Сількамяна--FreedomUA",
    "26-03-01--19-31--Bonem--FreedomUA",
    "26-03-02--19-35--Сількамяна--FreedomUA",
    "26-03-04--19-15--Norway--FreedomUA",
    "26-03-04--20-23--Norway--FreedomUA",
    "26-03-09--19-31--Norway--FreedomUA",
    "26-03-10--19-25--Denmark--FreedomUA",
    "26-03-11--19-11--Denmark--FreedomUA",
    "26-03-11--19-51--Bonem--FreedomUA",
    "26-03-11--20-40--Bonem--FreedomUA",
]

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
            print(f"  ⚠ 429, чекаємо 10с...", end=" ", flush=True)
            time.sleep(10)
            r2 = requests.get(url, headers=HEADERS, timeout=15)
            if r2.status_code == 200:
                return r2
            print(f"  ✗ retry={r2.status_code}", end=" ", flush=True)
        else:
            print(f"  ✗ {r.status_code}", end=" ", flush=True)
        return None
    except Exception as e:
        print(f"  ✗ exception={e}", end=" ", flush=True)
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
    мають 12+ спільних гравців — це частини одного реального рейду.
    З групи дублів лишаємо ОДИН лог — той з найбільшою кількістю гравців.
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

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total_pending}] {log_id}...", end=" ", flush=True)
        result = parse_consumables(log_id, members)
        if result:
            raids.append(result)
            queue.mark_done(log_id)
            save_raids_cache(raids)
            save_output(raids)
            processed += 1
            print(f"✓ {len(result['players'])} гравців")
        else:
            print("пропущено (лишається в черзі)")
            skipped += 1

    save_output(raids)
    print(f"\n=== Результат ===")
    print(f"  Оброблено цього разу: {processed}")
    print(f"  Залишилось в черзі:   {queue.pending_count}")
    print(f"  Всього рейдів:        {len(raids)}")
    print(f"  Гравців в дошці:      {len(build_honor_board(raids))}")
    print(f"\n✓ Збережено: {OUTPUT}")
