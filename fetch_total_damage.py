"""
fetch_total_damage.py — Deus Vult / FreedomUA
Сума Total Damage кожного гравця ЗІ ЗВІТІВ усіх рейдів гільдії.

Логіка повністю узгоджена з fetch_potion_data.py:
  - гравці беруться з EPGP.lua
  - список рейдів — через /logs_list (get_all_freedom_logs), як у потах
  - у кожному звіті /reports/<id>/ беремо <td class="damage total-cell">
    по кожному гравцю гільдії й сумуємо по всіх рейдах
  - один рядок на гравця (клас/спек з найбільшого внеску)
Результат: data/total-damage.json

Запуск: python fetch_total_damage.py
"""

import json, re, time, requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_URL = "https://uwu-logs.xyz"
SERVER   = "FreedomUA"
OUTPUT   = "data/total-damage.json"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Origin": BASE_URL}

# ─── ТЕСТОВИЙ РЕЖИМ ───────────────────────────────────────────────────────────
# Якщо список НЕ порожній — беруться ТІЛЬКИ ці логи (без обходу /logs_list).
# Зручно перевірити парсинг на одному відомому звіті, поки uwu-logs нестабільний.
# Коли все працює — очисти список (TEST_LOGS = []), щоб збирати всі рейди автоматично.
TEST_LOGS = [
    "26-06-21--22-00--Denmark--FreedomUA",
]
# ──────────────────────────────────────────────────────────────────────────────

# CSS-клас класу в <a> → людська назва (uwu-logs: <a class="warrior">)
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


def get_all_freedom_logs():
    """Ідентично fetch_potion_data.py — список усіх логів FreedomUA через /logs_list."""
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
    """
    Зі сторінки звіту /reports/<id>/ дістає сумарний total damage по гравцях гільдії.
    Повертає dict: name -> {"dmg": int, "class": str, "spec": str}
    (dmg — сума всіх damage total-cell гравця в цьому звіті).
    """
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

        # клас із CSS-класу <a>, спек із title player-cell ("Fury Warrior")
        a_cls = " ".join(a.get("class", [])).strip()
        cls_name = CLASS_CSS_TO_NAME.get(a_cls, a_cls)
        spec = player_cell.get("title", "")

        # сумарний damage цього рядка
        dmg_cell = tr.find('td', class_=lambda c: c and 'damage' in c.split() and 'total-cell' in c.split())
        if not dmg_cell:
            continue
        raw = dmg_cell.get_text(strip=True)
        num = int(re.sub(r"[^\d]", "", raw) or 0)
        if not num:
            continue

        slot = per_player.setdefault(name, {"dmg": 0, "class": cls_name, "spec": spec, "_best": 0})
        slot["dmg"] += num
        if num > slot["_best"]:
            slot["_best"] = num
            slot["class"] = cls_name
            slot["spec"]  = spec

    return per_player or None


def build_rows(members, log_ids):
    agg  = {}   # name -> сумарний total damage по всіх рейдах
    meta = {}   # name -> {class, spec, best}
    raids_used = 0

    total = len(log_ids)
    for i, log_id in enumerate(log_ids):
        print(f"[{i+1}/{total}] {log_id}...", end=" ", flush=True)
        per_player = parse_report_damage(log_id, members)
        if not per_player:
            print("пропущено")
            time.sleep(0.3)
            continue
        raids_used += 1
        for name, slot in per_player.items():
            agg[name] = agg.get(name, 0) + slot["dmg"]
            m = meta.setdefault(name, {"class": slot["class"], "spec": slot["spec"], "best": 0})
            if slot["dmg"] > m["best"]:
                m["best"]  = slot["dmg"]
                m["class"] = slot["class"]
                m["spec"]  = slot["spec"]
        print(f"✓ {len(per_player)} гравців")
        time.sleep(0.3)

    rows = []
    for name, dmg in agg.items():
        m = meta[name]
        rows.append({
            "name":        name,
            "server":      SERVER,
            "class":       m["class"],
            "spec":        m["spec"],
            "totalDamage": dmg,
        })
    rows.sort(key=lambda r: r["totalDamage"], reverse=True)
    return rows, raids_used


def save(rows, raids_used):
    data = {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "raidsCount":  raids_used,
        "totalRows":   len(rows),
        "rows":        rows,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== Збирач Total Damage Deus Vult ===\n")
    members = parse_epgp_members()

    if TEST_LOGS:
        print(f"⚙ ТЕСТОВИЙ РЕЖИМ — лише {len(TEST_LOGS)} лог(ів), без /logs_list\n")
        log_ids = TEST_LOGS
    else:
        log_ids = get_all_freedom_logs()

    rows, raids_used = build_rows(members, log_ids)
    save(rows, raids_used)

    print(f"\n✓ Готово! {OUTPUT}")
    print(f"  Рейдів використано: {raids_used}")
    print(f"  Гравців: {len(rows)}")

    # короткий топ-5 для швидкої очної перевірки
    if rows:
        print("\n  Топ-5 за Total Damage:")
        for r in rows[:5]:
            print(f"    {r['name']:20} {r['totalDamage']:>16,}".replace(",", " "))
