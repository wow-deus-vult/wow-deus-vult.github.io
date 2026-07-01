"""
fetch_tank_data.py -- Deus Vult / FreedomUA
Рейтинг танків по Damage Taken з усіх логів.
- Total Damage Taken за всі логи
- Окремо: Damage Taken від The Lich King і Halion
Результат: data/guild-tank.json
"""

import json, os, re, time, requests
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue
from dedup_helper import load_duplicate_map, is_duplicate_log

FETCH_FAILED = object()  # sentinel: мережева помилка → лишаємо в черзі

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/guild-tank.json"
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

# Танкові title з player-cell (точне визначення спеку)
TANK_TITLES = {
    "Blood Death Knight":   ("Death Knight", "Blood"),
    "Protection Paladin":   ("Paladin",       "Protection"),
    "Protection Warrior":   ("Warrior",       "Protection"),
}

# Боси де рахуємо taken окремо
SPECIAL_BOSSES = {"The Lich King", "Halion"}

BOSS_CSS = {
    "lord-marrowgar":        "Lord Marrowgar",
    "lady-deathwhisper":     "Lady Deathwhisper",
    "deathbringer-saurfang": "Deathbringer Saurfang",
    "festergut":             "Festergut",
    "rotface":               "Rotface",
    "professor-putricide":   "Professor Putricide",
    "blood-prince-council":  "Blood Prince Council",
    "blood-queen-lanathel":  "Blood-Queen Lana'thel",
    "sindragosa":            "Sindragosa",
    "the-lich-king":         "The Lich King",
    "valithria-dreamwalker": "Valithria Dreamwalker",
    "halion":                "Halion",
    "saviana-ragefire":      "Saviana Ragefire",
    "general-zarithrian":    "General Zarithrian",
    "baltharus-the-warborn": "Baltharus the Warborn",
}


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
            print(f"  ERR {r2.status_code}", end=" ", flush=True)
        else:
            print(f"  ERR {r.status_code}", end=" ", flush=True)
        return None
    except Exception as e:
        print(f"  ERR {e}", end=" ", flush=True)
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


def parse_boss_taken(log_id, boss_href, members):
    """Парсить сторінку боса і повертає {name: taken} для танків."""
    url = f"{BASE_URL}/reports/{log_id}/{boss_href}"
    r = safe_get(url)
    if not r:
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    result = {}
    for tr in soup.find_all("tr"):
        pc = tr.find("td", class_="player-cell")
        if not pc:
            continue
        a = pc.find("a")
        if not a:
            continue
        name = a.get_text(strip=True)
        if name == "Total" or name not in members:
            continue
        pc_title = pc.get("title", "")
        if pc_title not in TANK_TITLES:
            continue
        cls_name, spec_name = TANK_TITLES[pc_title]
        # Беремо taken total-cell
        for td in tr.find_all("td"):
            classes = td.get("class", [])
            if "taken" in classes and "total-cell" in classes:
                val = int(re.sub(r"[^\d]", "", td.get_text(strip=True)) or 0)
                if val > 0:
                    result[name] = {
                        "taken": val,
                        "class": cls_name,
                        "spec":  spec_name,
                    }
                break
    return result


def parse_log(log_id, members):
    """Парсить лог і збирає taken по всіх босах для танків."""
    url = f"{BASE_URL}/reports/{log_id}/"
    r = safe_get(url)
    if not r:
        return FETCH_FAILED
    soup = BeautifulSoup(r.text, "html.parser")

    boss_kills = {}
    seen = set()
    for a in soup.find_all("a", class_="kill-link"):
        href = a.get("href", "")
        boss_match = re.search(r"boss=([^&]+)", href)
        mode_match = re.search(r"mode=([^&]+)", href)
        if not boss_match or not mode_match:
            continue
        boss_css = boss_match.group(1).lower()
        mode = mode_match.group(1)
        if "25" not in mode:
            continue
        boss_name = BOSS_CSS.get(boss_css)
        if not boss_name or boss_name in seen:
            continue
        seen.add(boss_name)
        boss_kills[boss_name] = href

    if not boss_kills:
        return None

    log_data = {}
    for boss_name, href in boss_kills.items():
        taken = parse_boss_taken(log_id, href, members)
        if taken:
            log_data[boss_name] = taken

    return log_data or None


def load_cache():
    cache_path = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache):
    cache_path = OUTPUT.replace(".json", "_cache.json")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def build_output(cache):
    """
    Для кожного танка:
    - totalTaken: сума по всіх босах всіх логів
    - lichTaken:  сума по The Lich King
    - halionTaken: сума по Halion
    """
    player_data = {}

    player_raids = {}  # name -> set of log_ids

    for log_id, log_data in cache.items():
        for boss_name, tanks in log_data.items():
            for name, data in tanks.items():
                taken = data["taken"]
                if name not in player_data:
                    player_data[name] = {
                        "class": data["class"],
                        "spec":  data["spec"],
                        "totalTaken": 0,
                        "lichTaken":  0,
                        "halionTaken": 0,
                    }
                    player_raids[name] = set()
                player_data[name]["totalTaken"] += taken
                player_raids[name].add(log_id)
                if boss_name == "The Lich King":
                    player_data[name]["lichTaken"] += taken
                if boss_name == "Halion":
                    player_data[name]["halionTaken"] += taken

    rows = []
    for name, data in player_data.items():
        rows.append({
            "name":         name,
            "server":       SERVER,
            "class":        data["class"],
            "spec":         data["spec"],
            "totalTaken":   data["totalTaken"],
            "lichTaken":    data["lichTaken"],
            "halionTaken":  data["halionTaken"],
            "raidCount":    len(player_raids.get(name, set())),
        })

    rows.sort(key=lambda r: r["totalTaken"], reverse=True)
    for i, row in enumerate(rows):
        row["guildRank"] = i + 1

    return {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "totalTanks":  len(rows),
        "rows":        rows,
    }


def save_output(data):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== Збирач Tank рейтингу Deus Vult ===\n")
    members = parse_epgp_members()

    queue = LogQueue("data/pending_tank_rating.json")
    all_ids = get_all_log_ids()
    queue.add_logs(all_ids)

    cache = load_cache()
    print(f"  Логів у кеші: {len(cache)}")

    pending = queue.iter_pending()
    total = len(pending)
    print(f"  Залишилось обробити: {total}\n")

    processed = 0
    skipped = 0

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total}] {log_id}...", end=" ", flush=True)
        result = parse_log(log_id, members)
        if result is FETCH_FAILED:
            print("мережева помилка, лишається в черзі")
            skipped += 1
            continue
        if not result:
            print("пропущено (не ICC/RS, mark done)")
            queue.mark_done(log_id)
            continue

        cache[log_id] = result
        queue.mark_done(log_id)
        save_cache(cache)
        tanks_found = sum(len(v) for v in result.values())
        print(f"OK {len(result)} босів, {tanks_found} танк-записів")
        processed += 1

    data = build_output(cache)
    save_output(data)

    print(f"\n=== Результат ===")
    print(f"  Оброблено: {processed} | Пропущено: {skipped} | В черзі: {queue.pending_count}")
    print(f"  Танків в рейтингу: {data['totalTanks']}")
    if data["rows"]:
        print(f"  Топ-3:")
        for r in data["rows"][:3]:
            print(f"    {r['name']:20} Total Taken: {r['totalTaken']:>15,}".replace(",", " "))
    print(f"\nOK Збережено: {OUTPUT}")
