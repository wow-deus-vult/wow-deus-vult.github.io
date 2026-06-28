"""
fetch_total_damage.py — Deus Vult / FreedomUA
Total Damage кожного гравця, розбитий ПО СЕЗОНАХ.
Результат: data/total-damage.json
"""

import json, os, re, time, requests
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup
from epgp_parser import parse_epgp_members

BASE_URL     = "https://uwu-logs.xyz"
SERVER       = "FreedomUA"
OUTPUT       = "data/total-damage.json"
SEASONS_FILE = "seasons.json"
HEADERS      = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}

GUILD_UPLOADERS = [
    "Denmark", "Bonem", "Sweden", "Norway", "Калабаня", "Лісовиця",
    "Пірофобія", "Содахарчова", "Чіпічапа", "Капуста", "Зорекрила",
    "Сількамяна", "Тайтус", "Закарпайтус", "Шатайтус",
]

EXTRA_LOGS = [
    "26-03-23--19-25--Bonem--FreedomUA",
    "26-04-05--19-36--Bonem--FreedomUA",
]

CLASS_CSS_TO_NAME = {
    "deathknight": "Death Knight", "death-knight": "Death Knight",
    "druid": "Druid", "hunter": "Hunter", "mage": "Mage",
    "paladin": "Paladin", "priest": "Priest", "rogue": "Rogue",
    "shaman": "Shaman", "warlock": "Warlock", "warrior": "Warrior",
}


def check_connection():
    """Перевіряє доступність сайту. Повертає True якщо ок."""
    try:
        r = requests.get(f"{BASE_URL}/logs_list", headers=HEADERS, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def wait_for_connection():
    """Чекає поки сайт не стане доступним (2 спроби)."""
    if check_connection():
        return True
    print("  ⚠ Сайт недоступний, чекаємо 2с...")
    time.sleep(2)
    if check_connection():
        return True
    print("  ✗ Сайт так і не відповів, пропускаємо")
    return False


def safe_get(url):
    """GET з перевіркою конекту. Повертає response або None."""
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
    print("  ⚠ seasons.json не знайдено — створюю дефолтний Season 1")
    with open(SEASONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"seasons": [s]}, f, ensure_ascii=False, indent=2)
    return [s]


def log_id_to_date(log_id):
    parts = log_id.split("--")
    yy, mm, dd = parts[0].split("-")
    return date(int("20" + yy), int(mm), int(dd))


def get_guild_logs():
    """Збирає тільки логи наших uploaders + EXTRA_LOGS."""
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
    print(f"Логів для обробки: {len(log_ids)} (наших uploaders + {len(EXTRA_LOGS)} extra)")
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


def build(members, log_ids, seasons):
    raids = []
    total = len(log_ids)
    for i, log_id in enumerate(log_ids):
        print(f"[{i+1}/{total}] {log_id}...", end=" ", flush=True)
        try:
            rdate = log_id_to_date(log_id)
        except Exception:
            print("дата?"); continue
        per = parse_report_damage(log_id, members)
        if not per:
            print("пропущено")
            continue
        raids.append({"date": rdate, "per_player": per})
        print(f"✓ {len(per)} гравців ({rdate})")

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
    return {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "currentSeasonId": current_id,
        "seasons": season_out,
        "allTime": {"raidsCount": len(raids), "rows": all_rows},
    }


def save(data):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== Збирач Total Damage Deus Vult (сезони) ===\n")
    members = parse_epgp_members()
    seasons = load_seasons()
    log_ids = get_guild_logs()
    data = build(members, log_ids, seasons)
    save(data)

    cur = next((s for s in data["seasons"] if s["id"] == data["currentSeasonId"]), None)
    print(f"\n✓ Готово! {OUTPUT}")
    print(f"  Поточний сезон: {data['currentSeasonId']}")
    if cur and cur["rows"]:
        print(f"  Топ-3 сезону ({cur['name']}):")
        for r in cur["rows"][:3]:
            print(f"    {r['name']:20} {r['totalDamage']:>16,}".replace(",", " "))
    if data["allTime"]["rows"]:
        print(f"  Топ-3 All Time:")
        for r in data["allTime"]["rows"][:3]:
            print(f"    {r['name']:20} {r['totalDamage']:>16,}".replace(",", " "))
