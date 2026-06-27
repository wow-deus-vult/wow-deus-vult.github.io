"""
fetch_total_damage.py — Deus Vult / FreedomUA
Total Damage кожного гравця, розбитий ПО СЕЗОНАХ.

Логіка узгоджена з fetch_potion_data.py:
  - гравці з EPGP.lua
  - список рейдів через /logs_list (get_all_freedom_logs)
  - у кожному звіті /reports/<id>/ беремо <td class="damage total-cell"> по гравцях
  - дата рейду береться з log_id (як у потах)
  - рейди розкладаються по сезонах із seasons.json
Результат: data/total-damage.json
  {
    "lastUpdated": ...,
    "seasons": [ {id,name,start,end, raidsCount, rows:[...]} , ... ],
    "currentSeasonId": "s2"   # сезон, у який потрапляє сьогоднішня дата (або останній)
    "allTime": { raidsCount, rows:[...] }
  }

Запуск: python fetch_total_damage.py
"""

import json, os, re, time, requests
from datetime import datetime, timezone, date
from bs4 import BeautifulSoup

BASE_URL     = "https://uwu-logs.xyz"
SERVER       = "FreedomUA"
OUTPUT       = "data/total-damage.json"
SEASONS_FILE = "seasons.json"
HEADERS      = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}

# ─── ТЕСТОВИЙ РЕЖИМ ───────────────────────────────────────────────────────────
# Якщо НЕ порожній — беруться ТІЛЬКИ ці логи (без обходу /logs_list).
# Коли все працює — постав TEST_LOGS = [].
TEST_LOGS = [
    "26-06-21--22-00--Denmark--FreedomUA",
]
# ──────────────────────────────────────────────────────────────────────────────

CLASS_CSS_TO_NAME = {
    "deathknight": "Death Knight", "death-knight": "Death Knight",
    "druid": "Druid", "hunter": "Hunter", "mage": "Mage",
    "paladin": "Paladin", "priest": "Priest", "rogue": "Rogue",
    "shaman": "Shaman", "warlock": "Warlock", "warrior": "Warrior",
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


def load_seasons():
    """Читає seasons.json. Якщо немає — створює дефолтний поточний сезон на 3 міс."""
    if os.path.exists(SEASONS_FILE):
        with open(SEASONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        seasons = data.get("seasons", [])
        print(f"  Сезонів у seasons.json: {len(seasons)}")
        return seasons
    # дефолт — один поточний сезон
    today = date.today()
    s = {
        "id": "s1", "name": "Season 1",
        "start": today.replace(day=1).isoformat(),
        "end":   "2099-12-31",
    }
    print("  ⚠ seasons.json не знайдено — створюю дефолтний Season 1")
    with open(SEASONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"seasons": [s]}, f, ensure_ascii=False, indent=2)
    return [s]


def log_id_to_date(log_id):
    """'26-06-21--22-00--Denmark--FreedomUA' -> date(2026, 6, 21)"""
    parts = log_id.split("--")
    yy, mm, dd = parts[0].split("-")
    return date(int("20" + yy), int(mm), int(dd))


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


def parse_report_damage(log_id, members):
    """name -> {'dmg': int, 'class': str, 'spec': str} для одного звіту."""
    url = f"{BASE_URL}/reports/{log_id}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception:
        return None

    per_player = {}
    for tr in soup.find_all('tr'):
        player_cell = tr.find('td', class_='player-cell')
        if not player_cell:
            continue
        a = player_cell.find('a')
        if not a:
            continue
        name = a.get_text(strip=True)
        if name not in members:
            continue

        a_cls = " ".join(a.get("class", [])).strip()
        cls_name = CLASS_CSS_TO_NAME.get(a_cls, a_cls)
        spec = player_cell.get("title", "")

        dmg_cell = tr.find('td', class_=lambda c: c and 'damage' in c.split() and 'total-cell' in c.split())
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
            slot["spec"]  = spec

    return per_player or None


def aggregate(per_report_list):
    """Список per_report -> відсортовані rows[] (сума по гравцях)."""
    agg, meta = {}, {}
    for per_player in per_report_list:
        for name, slot in per_player.items():
            agg[name] = agg.get(name, 0) + slot["dmg"]
            m = meta.setdefault(name, {"class": slot["class"], "spec": slot["spec"], "best": 0})
            if slot["dmg"] > m["best"]:
                m["best"]  = slot["dmg"]
                m["class"] = slot["class"]
                m["spec"]  = slot["spec"]
    rows = [{
        "name": n, "server": SERVER,
        "class": meta[n]["class"], "spec": meta[n]["spec"],
        "totalDamage": dmg,
    } for n, dmg in agg.items()]
    rows.sort(key=lambda r: r["totalDamage"], reverse=True)
    return rows


def build(members, log_ids, seasons):
    # 1) збираємо damage по кожному рейду + дату
    raids = []  # {"date": date, "per_player": {...}}
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
            time.sleep(0.3)
            continue
        raids.append({"date": rdate, "per_player": per})
        print(f"✓ {len(per)} гравців ({rdate})")
        time.sleep(0.3)

    # 2) розкладаємо по сезонах
    season_out = []
    today = date.today()
    current_id = None

    for s in seasons:
        s_start = date.fromisoformat(s["start"])
        s_end   = date.fromisoformat(s["end"])
        in_season = [r["per_player"] for r in raids if s_start <= r["date"] <= s_end]
        rows = aggregate(in_season)
        season_out.append({
            "id": s["id"], "name": s["name"],
            "start": s["start"], "end": s["end"],
            "raidsCount": len(in_season),
            "rows": rows,
        })
        if s_start <= today <= s_end:
            current_id = s["id"]

    # якщо сьогодні поза всіма сезонами — беремо останній за датою
    if current_id is None and season_out:
        current_id = max(seasons, key=lambda s: s["end"])["id"]

    # 3) All Time — усі рейди разом
    all_rows = aggregate([r["per_player"] for r in raids])

    return {
        "lastUpdated":     datetime.now(timezone.utc).isoformat(),
        "currentSeasonId": current_id,
        "seasons":         season_out,
        "allTime":         {"raidsCount": len(raids), "rows": all_rows},
    }


def save(data):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== Збирач Total Damage Deus Vult (сезони) ===\n")
    members = parse_epgp_members()
    seasons = load_seasons()

    if TEST_LOGS:
        print(f"⚙ ТЕСТОВИЙ РЕЖИМ — лише {len(TEST_LOGS)} лог(ів)\n")
        log_ids = TEST_LOGS
    else:
        log_ids = get_all_freedom_logs()

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
