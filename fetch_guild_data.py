"""
fetch_guild_data.py
-------------------
Збирає дані гільдії з uwu-logs.xyz і зберігає в data/guild-data.json.
Список гравців автоматично береться з EPGP.lua (найсвіжіший snapshot).

Запуск:
    python fetch_guild_data.py

Залежності:
    pip install requests
"""

import json, os, re, time, requests
from datetime import datetime, timezone

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────

SERVER    = "FreedomUA"
MODE      = "25H"
BASE_URL  = "https://uwu-logs.xyz/top"
EPGP_FILE = os.path.join(os.path.dirname(__file__), "EPGP.lua")
OUTPUT    = os.path.join(os.path.dirname(__file__), "data", "guild-data.json")

# ─── КОНСТАНТИ ───────────────────────────────────────────────────────────────

BOSS_ORDER = [
    "Lord Marrowgar", "Lady Deathwhisper", "Deathbringer Saurfang",
    "Festergut", "Rotface", "Professor Putricide", "Blood Prince Council",
    "Blood-Queen Lana'thel", "Sindragosa", "The Lich King",
    "Toravon the Ice Watcher", "Halion", "Anub'arak", "Valithria Dreamwalker",
]

CLASSES = [
    "Death Knight", "Druid", "Hunter", "Mage", "Paladin",
    "Priest", "Rogue", "Shaman", "Warlock", "Warrior",
]

SPECS_BY_CLASS = {
    "Death Knight": ["Blood", "Frost", "Unholy"],
    "Druid":        ["Balance", "Feral Combat", "Restoration"],
    "Hunter":       ["Beast Mastery", "Marksmanship", "Survival"],
    "Mage":         ["Arcane", "Fire", "Frost"],
    "Paladin":      ["Holy", "Protection", "Retribution"],
    "Priest":       ["Discipline", "Holy", "Shadow"],
    "Rogue":        ["Assassination", "Combat", "Subtlety"],
    "Shaman":       ["Elemental", "Enhancement", "Restoration"],
    "Warlock":      ["Affliction", "Demonology", "Destruction"],
    "Warrior":      ["Arms", "Fury", "Protection"],
}

# Індекси класів (1-based) для API
CLASS_INDEX = {cls: str(i) for i, cls in enumerate(CLASSES)}

# Індекси спеків (1-based) для API
SPEC_INDEX = {
    cls: {spec: str(i + 1) for i, spec in enumerate(specs)}
    for cls, specs in SPECS_BY_CLASS.items()
}

# ─── ПАРСИНГ EPGP.lua ────────────────────────────────────────────────────────

def parse_epgp_members(path: str) -> set[str]:
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

# ─── API uwu-logs ─────────────────────────────────────────────────────────────

# Формат відповіді (масив на гравця):
# [0] log_name (str)
# [1] uDPS (float)
# [2] class_color (str)
# [3] name (str)
# [4] useful_damage (int)
# [5] total_damage (int)
# [6] externals (int)
# [7] logs (list of [dps, count, score, flag])

def fetch_top(boss: str, class_i: str, spec_i: str) -> list:
    payload = {
        "server":    SERVER,
        "boss":      boss,
        "mode":      MODE,
        "best_only": True,
        "class_i":   class_i,
        "spec_i":    spec_i,
        "externals": True,
        "limit":     "1000",
        "sort_by":   "head-useful-dps",
    }
    headers = {
        "Content-Type": "application/json",
        "Origin":       "https://uwu-logs.xyz",
        "Referer":      "https://uwu-logs.xyz/top",
    }
    try:
        r = requests.post(BASE_URL, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  ⚠  {boss} {class_i}/{spec_i}: {e}")
        return []

def parse_entry(entry: list) -> dict:
    """Перетворює сирий масив відповіді на зручний словник."""
    # [7] — масив логів: [[dps, count, score, externals_flag], ...]
    # Беремо перший (найкращий) лог
    logs = entry[7] if len(entry) > 7 and isinstance(entry[7], list) else []
    best_log = logs[0] if logs else []

    return {
        "name":  entry[3],
        "udps":  entry[1],                          # useful DPS
        "score": best_log[2] if len(best_log) > 2 else 0.0,
        "rank":  best_log[1] if len(best_log) > 1 else 9999,
    }

# ─── ОСНОВНА ЛОГІКА ──────────────────────────────────────────────────────────

def build_guild_data(members: set[str]) -> dict:
    # key: (name, class, spec) → row
    rows_map: dict[tuple, dict] = {}

    total = len(CLASSES) * 3 * len(BOSS_ORDER)   # ~14 босів × 10 класів × 3 спеки = 420
    done  = 0

    for boss in BOSS_ORDER:
        print(f"\n📜 {boss}")
        for cls_name, specs in SPECS_BY_CLASS.items():
            cls_i = CLASS_INDEX[cls_name]
            for spec_name in specs:
                spec_i = SPEC_INDEX[cls_name][spec_name]
                done += 1
                print(f"  [{done}/{total}] {cls_name}/{spec_name}...", end=" ", flush=True)

                entries = fetch_top(boss, cls_i, spec_i)

                # Фільтруємо тільки гравців гільдії
                guild_entries = [e for e in entries if e[3] in members]
                print(f"{len(guild_entries)} з {len(entries)}")

                for entry in guild_entries:
                    p = parse_entry(entry)
                    key = (p["name"], cls_name, spec_name)

                    if key not in rows_map:
                        rows_map[key] = {
                            "name":         p["name"],
                            "server":       SERVER,
                            "class":        cls_name,
                            "spec":         spec_name,
                            "specIndex":    int(spec_i),
                            "overallRank":  p["rank"],
                            "overallScore": p["score"],
                            "bosses":       {b: 0 for b in BOSS_ORDER},
                        }

                    row = rows_map[key]
                    row["bosses"][boss] = round(p["udps"], 1)

                    # Оновлюємо загальний score/rank якщо цей лог кращий
                    if p["score"] > row["overallScore"]:
                        row["overallScore"] = p["score"]
                        row["overallRank"]  = p["rank"]

                time.sleep(0.3)   # не перевантажуємо сервер

    rows = sorted(rows_map.values(), key=lambda r: r["overallScore"], reverse=True)

    return {
        "updatedAt":            datetime.now(timezone.utc).isoformat(),
        "lastUpdated":          datetime.now(timezone.utc).isoformat(),
        "totalPlayersInSource": len({r["name"] for r in rows}),
        "totalRows":            len(rows),
        "bossOrder":            BOSS_ORDER,
        "classes":              CLASSES,
        "specsByClass":         SPECS_BY_CLASS,
        "rows":                 rows,
        "updateSummary":        {"totalRows": len(rows), "failedPlayers": 0},
    }

# ─── ТОЧКА ВХОДУ ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🏰 Deus Vult / FreedomUA / ЦЛК 25 ХМ\n")

    if not os.path.exists(EPGP_FILE):
        print(f"❌ Файл {EPGP_FILE} не знайдено!")
        exit(1)

    members = parse_epgp_members(EPGP_FILE)
    print(f"   Шукаємо {len(members)} гравців на uwu-logs\n")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    data = build_guild_data(members)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово! {len(data['rows'])} рядків → {OUTPUT}")
    print(f"   Унікальних гравців: {data['totalPlayersInSource']}")