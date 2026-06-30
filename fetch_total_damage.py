"""
fetch_total_damage.py — Deus Vult / FreedomUA
Total Damage кожного гравця, розбитий ПО СЕЗОНАХ.
Результат: data/total-damage.json

Черга незавантажених логів: data/pending_logs.json
При кожному запуску підхоплює з того місця де зупинився.
"""

import json, os, re, time, requests
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members
from log_queue import LogQueue

BASE_URL     = "https://uwu-logs.xyz"
SERVER       = "FreedomUA"
OUTPUT       = "data/total-damage.json"
SEASONS_FILE = "seasons.json"
HEADERS      = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}
DELAY        = 4.0

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

CLASS_CSS_TO_NAME = {
    "deathknight": "Death Knight", "death-knight": "Death Knight",
    "druid": "Druid", "hunter": "Hunter", "mage": "Mage",
    "paladin": "Paladin", "priest": "Priest", "rogue": "Rogue",
    "shaman": "Shaman", "warlock": "Warlock", "warrior": "Warrior",
}


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


def load_seasons():
    if os.path.exists(SEASONS_FILE):
        with open(SEASONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        seasons = data.get("seasons", [])
        print(f"  Сезонів у seasons.json: {len(seasons)}")
        return seasons
    today = date.today()
    s = {"id": "s1", "name": "Season 1",
         "start": today.replace(day=1).isoformat(), "end": "2099-12-31"}
    with open(SEASONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"seasons": [s]}, f, ensure_ascii=False, indent=2)
    return [s]


def log_id_to_date(log_id):
    parts = log_id.split("--")
    yy, mm, dd = parts[0].split("-")
    return date(int("20" + yy), int(mm), int(dd))


def get_all_log_ids():
    """Збирає логи з /logs_list (наших uploaders) + EXTRA_LOGS."""
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


def parse_report_damage(log_id, members):
    url = f"{BASE_URL}/reports/{log_id}/"
    r = safe_get(url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    per_player = {}
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
        a_cls = " ".join(a.get("class", [])).strip()
        cls_name = CLASS_CSS_TO_NAME.get(a_cls, a_cls)
        spec = pc.get("title", "")
        dmg_cell = tr.find("td", class_=lambda c: c and "damage" in c and "total-cell" in c)
        if not dmg_cell:
            continue
        num = int(re.sub(r"[^\d]", "", dmg_cell.get_text(strip=True)) or 0)
        if not num:
            continue
        slot = per_player.setdefault(name, {"dmg": 0, "class": cls_name, "spec": spec, "_best": 0})
        slot["dmg"] += num
        if num > slot["_best"]:
            slot["_best"] = num
            slot["class"] = cls_name
            slot["spec"] = spec
    return per_player or None


def load_existing_raids():
    """Завантажує вже зібрані рейди з JSON."""
    if not os.path.exists(OUTPUT):
        return []
    with open(OUTPUT, encoding="utf-8") as f:
        data = json.load(f)
    # Відновлюємо список рейдів з allTime rows — але нам потрібні сирі дані.
    # Зберігаємо їх окремо у _raids_cache.json
    cache = OUTPUT.replace(".json", "_cache.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_raids_cache(raids):
    cache = OUTPUT.replace(".json", "_cache.json")
    with open(cache, "w", encoding="utf-8") as f:
        # date не серіалізується — конвертуємо в str
        serializable = [{"date": str(r["date"]), "log_id": r.get("log_id", ""),
                          "per_player": r["per_player"]} for r in raids]
        json.dump(serializable, f, ensure_ascii=False)


def load_raids_cache():
    cache = OUTPUT.replace(".json", "_cache.json")
    if not os.path.exists(cache):
        return []
    with open(cache, encoding="utf-8") as f:
        raw = json.load(f)
    return [{"date": date.fromisoformat(r["date"]), "log_id": r.get("log_id", ""),
              "per_player": r["per_player"]} for r in raw]


def aggregate(per_report_list):
    agg, meta = {}, {}
    for per_player in per_report_list:
        for name, slot in per_player.items():
            agg[name] = agg.get(name, 0) + slot["dmg"]
            m = meta.setdefault(name, {"class": slot["class"], "spec": slot["spec"], "best": 0})
            if slot["dmg"] > m["best"]:
                m["best"] = slot["dmg"]
                m["class"] = slot["class"]
                m["spec"] = slot["spec"]
    rows = [{"name": n, "server": SERVER, "class": meta[n]["class"],
             "spec": meta[n]["spec"], "totalDamage": dmg}
            for n, dmg in agg.items()]
    rows.sort(key=lambda r: r["totalDamage"], reverse=True)
    return rows


def deduplicate_raids(raids):
    """
    Прибирає дублі рейдів: якщо два логи з тієї ж дати (або +1 день)
    мають 12+ спільних гравців — це частини одного реального рейду
    (різні люди заливали різні шматки). З групи дублів об'єднуємо
    дані: для кожного гравця беремо МАКСИМУМ серед дублів (не суму),
    щоб не множити total damage.

    Додатково зберігає data/duplicate_logs_map.json — мапу
    {дублікат_log_id: канонічний_log_id}, яку можуть використовувати
    інші скрипти (tank, heal, potion, raid_stats) для пропуску дублів
    без повторного аналізу складу гравців.
    """
    if not raids:
        return raids

    sorted_raids = sorted(enumerate(raids), key=lambda x: x[1]["date"])

    used = set()
    groups = []

    for i, (orig_i, r) in enumerate(sorted_raids):
        if orig_i in used:
            continue
        group = [orig_i]
        used.add(orig_i)
        players_i = set(r["per_player"].keys())

        for j in range(i + 1, len(sorted_raids)):
            orig_j, r2 = sorted_raids[j]
            if orig_j in used:
                continue
            day_diff = abs((r2["date"] - r["date"]).days)
            if day_diff > 1:
                break
            players_j = set(r2["per_player"].keys())
            overlap = len(players_i & players_j)
            if overlap >= 12:
                group.append(orig_j)
                used.add(orig_j)

        groups.append(group)

    deduped = []
    merged_count = 0
    duplicate_map = {}  # дублікат_log_id -> канонічний_log_id

    for group in groups:
        if len(group) == 1:
            deduped.append(raids[group[0]])
            continue
        merged_count += len(group) - 1
        base_date = raids[group[0]]["date"]
        # Канонічний — лог з найбільшою кількістю гравців
        canonical_idx = max(group, key=lambda idx: len(raids[idx]["per_player"]))
        canonical_log_id = raids[canonical_idx].get("log_id", "")

        merged_players = {}
        for idx in group:
            for name, slot in raids[idx]["per_player"].items():
                if name not in merged_players or slot["dmg"] > merged_players[name]["dmg"]:
                    merged_players[name] = slot
            log_id = raids[idx].get("log_id", "")
            if log_id and idx != canonical_idx:
                duplicate_map[log_id] = canonical_log_id

        deduped.append({"date": base_date, "log_id": canonical_log_id, "per_player": merged_players})

    if merged_count:
        print(f"  \U0001f501 Дедуплікація: об'єднано {merged_count} дублікат(ів) рейдів")

    # Зберігаємо мапу дублікатів для інших скриптів
    dup_map_path = "data/duplicate_logs_map.json"
    os.makedirs(os.path.dirname(dup_map_path), exist_ok=True)
    with open(dup_map_path, "w", encoding="utf-8") as f:
        json.dump(duplicate_map, f, ensure_ascii=False, indent=2)

    return deduped


def save_output(raids, seasons):
    raids = deduplicate_raids(raids)
    season_out = []
    today = date.today()
    current_id = None
    for s in seasons:
        s_start = date.fromisoformat(s["start"])
        s_end = date.fromisoformat(s["end"])
        in_season = [r["per_player"] for r in raids if s_start <= r["date"] <= s_end]
        rows = aggregate(in_season)
        season_out.append({"id": s["id"], "name": s["name"],
                           "start": s["start"], "end": s["end"],
                           "raidsCount": len(in_season), "rows": rows})
        if s_start <= today <= s_end:
            current_id = s["id"]
    if current_id is None and season_out:
        current_id = max(seasons, key=lambda s: s["end"])["id"]
    all_rows = aggregate([r["per_player"] for r in raids])
    data = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "currentSeasonId": current_id,
        "seasons": season_out,
        "allTime": {"raidsCount": len(raids), "rows": all_rows},
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


if __name__ == "__main__":
    print("=== Збирач Total Damage Deus Vult (сезони) ===\n")
    members = parse_epgp_members()
    seasons = load_seasons()

    # Черга
    queue = LogQueue("data/pending_total_damage.json")
    all_ids = get_all_log_ids()
    queue.add_logs(all_ids)

    # Завантажуємо вже зібрані рейди з кешу
    raids = load_raids_cache()
    print(f"  Рейдів у кеші: {len(raids)}")

    pending = queue.iter_pending()
    total_pending = len(pending)
    print(f"\nОбробляємо {total_pending} логів з черги...\n")

    processed = 0
    skipped = 0

    for i, log_id in enumerate(pending):
        print(f"[{i+1}/{total_pending}] {log_id}...", end=" ", flush=True)
        try:
            rdate = log_id_to_date(log_id)
        except Exception:
            print("дата?")
            queue.mark_done(log_id)  # некоректний ID — прибираємо
            continue

        per = parse_report_damage(log_id, members)
        if not per:
            print("пропущено (лишається в черзі)")
            skipped += 1
            continue

        raids.append({"date": rdate, "log_id": log_id, "per_player": per})
        queue.mark_done(log_id)
        save_raids_cache(raids)
        processed += 1
        print(f"✓ {len(per)} гравців ({rdate})")

    # Зберігаємо фінальний результат
    data = save_output(raids, seasons)

    cur = next((s for s in data["seasons"] if s["id"] == data["currentSeasonId"]), None)
    print(f"\n=== Результат ===")
    print(f"  Оброблено цього разу: {processed}")
    print(f"  Залишилось в черзі:   {queue.pending_count}")
    print(f"  Всього рейдів:        {len(raids)}")
    print(f"  Поточний сезон: {data['currentSeasonId']}")
    if cur and cur["rows"]:
        print(f"  Топ-3 сезону ({cur['name']}):")
        for r in cur["rows"][:3]:
            print(f"    {r['name']:20} {r['totalDamage']:>16,}".replace(",", " "))
    if data["allTime"]["rows"]:
        print(f"  Топ-3 All Time:")
        for r in data["allTime"]["rows"][:3]:
            print(f"    {r['name']:20} {r['totalDamage']:>16,}".replace(",", " "))
    print(f"\n✓ Збережено: {OUTPUT}")
