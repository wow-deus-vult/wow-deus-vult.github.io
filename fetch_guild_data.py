"""
fetch_guild_data.py — Deus Vult / FreedomUA / ЦЛК 25 ХМ
"""

import json, os, re, time, requests
from datetime import datetime, timezone

SERVER    = "FreedomUA"
MODE      = "25H"
BASE_URL  = "https://uwu-logs.xyz/top"
EPGP_FILE = os.path.join(os.path.dirname(__file__), "EPGP.lua")
OUTPUT    = os.path.join(os.path.dirname(__file__), "data", "guild-data.json")

BOSS_ORDER = [
    "Lord Marrowgar", "Lady Deathwhisper", "Deathbringer Saurfang",
    "Festergut", "Rotface", "Professor Putricide", "Blood Prince Council",
    "Blood-Queen Lana'thel", "Sindragosa", "The Lich King",
    "Halion",
    # Ruby Sanctum міні-боси
    "Saviana Ragefire", "General Zarithrian", "Baltharus the Warborn",
    # Хіл-бос окремо
    "Valithria Dreamwalker",
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

CLASS_INDEX = {cls: str(i) for i, cls in enumerate(CLASSES)}
SPEC_INDEX  = {
    cls: {spec: str(i + 1) for i, spec in enumerate(specs)}
    for cls, specs in SPECS_BY_CLASS.items()
}

# ─── EPGP ────────────────────────────────────────────────────────────────────

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

# ─── API ─────────────────────────────────────────────────────────────────────

def fetch_top(boss, class_i, spec_i):
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
        print(f"  ⚠  {e}")
        return []

def parse_entry(entry, server_rank):
    """
    entry[0] = log_name
    entry[1] = uDPS (корисний DPS)
    entry[3] = name
    entry[7] = [[dps, count, score, ext_flag], ...]  — масив логів гравця
    server_rank = позиція в масиві відповіді (1-based) = реальний ранг на сервері
    """
    logs = entry[7] if len(entry) > 7 and isinstance(entry[7], list) else []
    # Знаходимо лог з найкращим score
    best = max(logs, key=lambda l: l[2] if len(l) > 2 else 0, default=[0, 0, 0, 0])
    return {
        "name":  entry[3],
        "udps":  round(entry[1], 1),
        "score": best[2] if len(best) > 2 else 0.0,
        "rank":  server_rank,   # реальна позиція в топі сервера
    }

# ─── MAIN ────────────────────────────────────────────────────────────────────

def build_guild_data(members):
    rows_map = {}
    total = len(CLASSES) * 3 * len(BOSS_ORDER)
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

                found = 0
                for server_rank, entry in enumerate(entries, start=1):
                    if entry[3] not in members:
                        continue
                    found += 1
                    p   = parse_entry(entry, server_rank)
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
                    row["bosses"][boss] = p["udps"]

                    if p["score"] > row["overallScore"]:
                        row["overallScore"] = p["score"]
                        row["overallRank"]  = p["rank"]

                print(f"{found}")
                time.sleep(0.3)

    rows = sorted(rows_map.values(), key=lambda r: r["overallScore"], reverse=True)
    return {
        "lastUpdated":          datetime.now(timezone.utc).isoformat(),
        "totalPlayersInSource": len({r["name"] for r in rows}),
        "totalRows":            len(rows),
        "bossOrder":            BOSS_ORDER,
        "classes":              CLASSES,
        "specsByClass":         SPECS_BY_CLASS,
        "rows":                 rows,
    }

if __name__ == "__main__":
    print("🏰 Deus Vult / FreedomUA / ЦЛК 25 ХМ\n")
    if not os.path.exists(EPGP_FILE):
        print(f"❌ {EPGP_FILE} не знайдено!")
        exit(1)
    members = parse_epgp_members(EPGP_FILE)
    print(f"   Шукаємо {len(members)} гравців\n")
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    data = build_guild_data(members)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(data['rows'])} рядків → {OUTPUT}")
    print(f"   Унікальних гравців: {data['totalPlayersInSource']}")
