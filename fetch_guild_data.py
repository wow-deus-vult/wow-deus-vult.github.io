"""
fetch_guild_data.py — Deus Vult / FreedomUA
Збирає дані через /character API (overall_points, dps_max по босах).
"""

import json, os, re, time, requests
from datetime import datetime, timezone

SERVER    = "FreedomUA"
MODE      = "25H"
CHAR_URL  = "https://uwu-logs.xyz/character"
TOP_URL   = "https://uwu-logs.xyz/top"
EPGP_FILE = os.path.join(os.path.dirname(__file__), "EPGP.lua")
OUTPUT    = os.path.join(os.path.dirname(__file__), "data", "guild-data.json")

HEADERS = {
    "Content-Type": "application/json",
    "Origin":       "https://uwu-logs.xyz",
    "Referer":      "https://uwu-logs.xyz/character",
}

BOSS_ORDER = [
    "Lord Marrowgar", "Lady Deathwhisper", "Deathbringer Saurfang",
    "Festergut", "Rotface", "Professor Putricide", "Blood Prince Council",
    "Blood-Queen Lana'thel", "Sindragosa", "The Lich King",
    "Halion", "Saviana Ragefire", "General Zarithrian", "Baltharus the Warborn",
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

# ─── Крок 1: знайти які гравці з гільдії є на сервері і їх спеки ─────────────

def find_guild_members_on_server(members):
    """
    Проходить по /top для кожного класу/спеку і збирає
    унікальних гравців гільдії разом з їх класом/спеком.
    Повертає dict: {name: [(class, spec, spec_i), ...]}
    """
    found = {}  # name → list of (cls, spec, spec_i)
    total = len(CLASSES) * 3
    done  = 0

    print("🔍 Крок 1: шукаємо гравців гільдії на сервері...")

    for cls_name, specs in SPECS_BY_CLASS.items():
        cls_i = CLASS_INDEX[cls_name]
        for spec_name in specs:
            spec_i = SPEC_INDEX[cls_name][spec_name]
            done += 1
            print(f"  [{done}/{total}] {cls_name}/{spec_name}...", end=" ", flush=True)

            # Запитуємо будь-якого боса щоб знайти хто є на сервері
            payload = {
                "server":    SERVER,
                "boss":      "Lord Marrowgar",
                "mode":      MODE,
                "best_only": True,
                "class_i":   cls_i,
                "spec_i":    spec_i,
                "externals": True,
                "limit":     "1000",
                "sort_by":   "head-useful-dps",
            }
            try:
                r = requests.post(TOP_URL, json=payload, headers=HEADERS, timeout=30)
                r.raise_for_status()
                entries = r.json()
                guild_found = [e[3] for e in entries if e[3] in members]
                print(f"{len(guild_found)}")
                for name in guild_found:
                    if name not in found:
                        found[name] = []
                    found[name].append((cls_name, spec_name, spec_i))
            except Exception as e:
                print(f"⚠ {e}")

            time.sleep(0.3)

    return found

# ─── Крок 2: для кожного гравця отримати дані через /character ───────────────

def fetch_character(name, spec_i):
    """
    POST /character → {name, server, spec}
    Повертає overall_points, overall_rank, bosses з dps_max і rank_players
    """
    payload = {"name": name, "server": SERVER, "spec": spec_i}
    try:
        r = requests.post(CHAR_URL, json=payload, headers={
            **HEADERS, "Referer": "https://uwu-logs.xyz/character"
        }, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠ {name}/{spec_i}: {e}")
        return None

def build_guild_data(members):
    # Крок 1: знайти спеки гравців
    members_specs = find_guild_members_on_server(members)
    print(f"\n   Знайдено {len(members_specs)} гравців з {len(members)} можливих\n")

    # Крок 2: для кожного гравця і кожного його спеку — запит /character
    rows = []
    total = sum(len(specs) for specs in members_specs.values())
    done  = 0

    print("📊 Крок 2: отримуємо дані по кожному гравцю...")

    for name, specs in members_specs.items():
        for cls_name, spec_name, spec_i in specs:
            done += 1
            print(f"  [{done}/{total}] {name} / {cls_name} {spec_name}...", end=" ", flush=True)

            data = fetch_character(name, spec_i)
            if not data:
                print("пропущено")
                continue

            overall_points = data.get("overall_points", 0) or 0
            overall_rank   = data.get("overall_rank", 9999) or 9999
            bosses_data    = data.get("bosses", {})

            # Збираємо DPS по босах
            bosses = {}
            for boss in BOSS_ORDER:
                bd = bosses_data.get(boss, {})
                bosses[boss] = round(bd.get("dps_max", 0) or 0, 1)

            # overall_points наприклад 9935.09 → score 99.35
            score = round(overall_points / 100.0, 2)

            row = {
                "name":         name,
                "server":       SERVER,
                "class":        cls_name,
                "spec":         spec_name,
                "specIndex":    int(spec_i),
                "overallRank":  overall_rank,
                "overallScore": score,
                "bosses":       bosses,
            }
            rows.append(row)
            print(f"score={score:.2f} rank=#{overall_rank}")
            time.sleep(0.2)

    rows.sort(key=lambda r: r["overallScore"], reverse=True)

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
    print("🏰 Deus Vult / FreedomUA / ЦЛК+РС 25 ХМ\n")
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
