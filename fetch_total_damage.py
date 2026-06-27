"""
fetch_total_damage.py — Deus Vult / FreedomUA
Сума Total Damage кожного гравця ЗІ ЗВІТІВ реальних рейдів (HTML /reports/.../).

Логіка:
  1. Гравці беруться з EPGP.lua (та сама, що у fetch_guild_data.py).
  2. Для кожного звіту рейду тягнемо HTML сторінки /reports/<report_id>/
     і беремо <td class="damage total-cell"> по кожному гравцю.
  3. Сумуємо по всіх рейдах → total damage за весь період.
  4. Один рядок на гравця; клас/спек беруться з найбільшого внеску.
  5. Пишемо в data/total-damage.json.

ВАЖЛИВО: список звітів рейдів задається у get_raid_reports()
         (файл raids.txt поряд зі скриптом, по одному report_id на рядок).
"""

import json, os, re, time, requests
from datetime import datetime, timezone
from html.parser import HTMLParser

SERVER    = "FreedomUA"
BASE      = "https://uwu-logs.xyz"
EPGP_FILE = os.path.join(os.path.dirname(__file__), "EPGP.lua")
OUTPUT    = os.path.join(os.path.dirname(__file__), "data", "total-damage.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DeusVultBot/1.0)",
    "Referer":    f"{BASE}/",
}

CLASS_CSS_TO_NAME = {
    "deathknight": "Death Knight", "death-knight": "Death Knight",
    "druid": "Druid", "hunter": "Hunter", "mage": "Mage",
    "paladin": "Paladin", "priest": "Priest", "rogue": "Rogue",
    "shaman": "Shaman", "warlock": "Warlock", "warrior": "Warrior",
}

# ─── EPGP (ідентично fetch_guild_data.py) ─────────────────────────────────────

def parse_epgp_members(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r'\["time"\]\s*=\s*(\d+).*?\["roster_info"\]\s*=\s*\{(.*?)\},\s*\n\s*\}',
        re.DOTALL
    )
    snapshots = list(pattern.finditer(content))
    if not snapshots:
        raise ValueError("Не знайдено snapshot у EPGP.lua")
    latest = max(snapshots, key=lambda m: int(m.group(1)))
    ts = int(latest.group(1))
    dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
    names = re.findall(r'"([^"]+)",\s*--\s*\[1\]', latest.group(2))
    print(f"   EPGP snapshot від {dt} → {len(names)} гравців")
    return set(names)

# ─── Парсер одного звіту ──────────────────────────────────────────────────────

class ReportParser(HTMLParser):
    """
    Зі сторінки звіту дістає рядки (name, class, spec, total_damage):
      - ім'я: td.player-cell > a (текст)
      - клас: CSS-клас того <a> (warrior/druid/...)
      - спек: td.player-cell title="Fury Warrior"
      - damage: td.damage.total-cell
    """
    def __init__(self):
        super().__init__()
        self.rows = []
        self._name = None
        self._class = None
        self._spec = None
        self._in_player_link = False
        self._await_player_title = False
        self._in_damage_total = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        parts = cls.split()

        if tag == "td" and "player-cell" in parts:
            title = a.get("title", "")
            if title:
                self._spec = title
            self._await_player_title = True

        if tag == "a" and self._await_player_title:
            self._in_player_link = True
            self._class = CLASS_CSS_TO_NAME.get(cls.strip(), cls.strip())

        if tag == "td" and "damage" in parts and "total-cell" in parts:
            self._in_damage_total = True

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_player_link:
            self._name = text
        elif self._in_damage_total:
            num = int(re.sub(r"[^\d]", "", text) or 0)
            if self._name and num:
                self.rows.append((self._name, self._class, self._spec, num))

    def handle_endtag(self, tag):
        if tag == "a":
            self._in_player_link = False
            self._await_player_title = False
        if tag == "td" and self._in_damage_total:
            self._in_damage_total = False


def fetch_report_rows(report_id):
    url = f"{BASE}/reports/{report_id}/"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    p = ReportParser()
    p.feed(r.text)
    return p.rows

# ─── Джерело списку рейдів ────────────────────────────────────────────────────

def get_raid_reports():
    """
    Повертає список report_id усіх рейдів гільдії.
    Приклад ID: "26-06-21--22-00--Denmark--FreedomUA"
    Читає з raids.txt поряд зі скриптом (по одному ID на рядок, # = коментар).
    """
    raids_file = os.path.join(os.path.dirname(__file__), "raids.txt")
    if os.path.exists(raids_file):
        with open(raids_file, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return [
        "26-06-21--22-00--Denmark--FreedomUA",  # приклад
    ]

# ─── Збірка ───────────────────────────────────────────────────────────────────

def build_total_damage(members):
    reports = get_raid_reports()
    print(f"📜 Звітів до обробки: {len(reports)}")

    agg  = {}   # name -> сумарний total damage
    meta = {}   # name -> {class, spec, best}

    for i, rid in enumerate(reports, 1):
        print(f"  [{i}/{len(reports)}] {rid} ...", end=" ", flush=True)
        try:
            rows = fetch_report_rows(rid)
        except Exception as e:
            print(f"⚠ {e}")
            continue

        per_report = {}
        for name, cls, spec, dmg in rows:
            if name not in members:
                continue
            slot = per_report.setdefault(name, {"dmg": 0, "class": cls, "spec": spec, "_best": 0})
            slot["dmg"] += dmg
            if dmg > slot["_best"]:
                slot["_best"] = dmg
                slot["class"] = cls
                slot["spec"]  = spec

        for name, slot in per_report.items():
            agg[name] = agg.get(name, 0) + slot["dmg"]
            m = meta.setdefault(name, {"class": slot["class"], "spec": slot["spec"], "best": 0})
            if slot["dmg"] > m["best"]:
                m["best"]  = slot["dmg"]
                m["class"] = slot["class"]
                m["spec"]  = slot["spec"]

        print(f"{len(per_report)} гравців гільдії")
        time.sleep(0.3)

    rows_out = []
    for name, total in agg.items():
        m = meta[name]
        rows_out.append({
            "name":        name,
            "server":      SERVER,
            "class":       m["class"],
            "spec":        m["spec"],
            "totalDamage": total,
        })
    rows_out.sort(key=lambda r: r["totalDamage"], reverse=True)

    return {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "raidsCount":  len(reports),
        "totalRows":   len(rows_out),
        "rows":        rows_out,
    }

if __name__ == "__main__":
    print("🏰 Deus Vult / FreedomUA — Total Damage\n")
    if not os.path.exists(EPGP_FILE):
        print(f"❌ {EPGP_FILE} не знайдено!")
        exit(1)
    members = parse_epgp_members(EPGP_FILE)
    print(f"   Шукаємо {len(members)} гравців\n")
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    data = build_total_damage(members)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(data['rows'])} рядків → {OUTPUT}")
