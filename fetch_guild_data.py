"""
fetch_guild_data.py — Deus Vult / FreedomUA
- Основні дані через /character (25H)
- Міні-боси РС через /top (25N)
"""

import json, os, re, time, requests
from datetime import datetime, timezone

SERVER    = "FreedomUA"
MODE      = "25H"
MODE_RS   = "25N"   # міні-боси РС тільки в 25N
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
    "Halion",
    "Saviana Ragefire", "General Zarithrian", "Baltharus the Warborn",
    "Valithria Dreamwalker",
]

RS_MINI_BOSSES = ["Saviana Ragefire", "General Zarithrian", "Baltharus the Warborn"]

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

# ─── Крок 1: знайти спеки гравців через /top ─────────────────────────────────

def find_guild_members_on_server(members):
    found = {}
    total = len(CLASSES) * 3
    done  = 0
    print("🔍 Крок 1: шукаємо гравців на сервері...")
    for cls_name, specs in SPECS_BY_CLASS.items():
        cls_i = CLASS_INDEX[cls_name]
        for spec_name in specs:
            spec_i = SPEC_INDEX[cls_name][spec_name]
            done += 1
            print(f"  [{done}/{total}] {cls_name}/{spec_name}...", end=" ", flush=True)
            payload = {
                "server": SERVER, "boss": "Lord Marrowgar", "mode": MODE,
                "best_only": True, "class_i": cls_i, "spec_i": spec_i,
                "externals": True, "limit": "1000", "sort_by": "head-useful-dps",
            }
            try:
                r = requests.post(TOP_URL, json=payload, headers=HEADERS, timeout=30)
                r.raise_for_status()
                guild_found = [e[3] for e in r.json() if e[3] in members]
                print(f"{len(guild_found)}")
                for name in guild_found:
                    if name not in found:
                        found[name] = []
                    found[name].append((cls_name, spec_name, spec_i))
            except Exception as e:
                print(f"⚠ {e}")
            time.sleep(0.3)
    return found

# ─── Крок 2: /character для основних даних ───────────────────────────────────

def fetch_character(name, spec_i):
    payload = {"name": name, "server": SERVER, "spec": spec_i}
    try:
        r = requests.post(CHAR_URL, json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠ character {name}/{spec_i}: {e}")
        return None

# ─── Крок 3: /top 25N для міні-босів РС ──────────────────────────────────────

def fetch_rs_mini_bosses(members_specs):
    """
    Для кожного міні-боса РС в 25N збираємо dps_max по гравцях гільдії.
    Повертає dict: {(name, cls, spec): {boss: dps}}
    """
    rs_data = {}   # (name, cls, spec) → {boss: dps}

    print("\n🏰 Крок 3: збираємо міні-боси РС (25N)...")

    for boss in RS_MINI_BOSSES:
        print(f"\n  📜 {boss}")
        for cls_name, specs in SPECS_BY_CLASS.items():
            cls_i = CLASS_INDEX[cls_name]
            for spec_name in specs:
                spec_i = SPEC_INDEX[cls_name][spec_name]
                payload = {
                    "server": SERVER, "boss": boss, "mode": MODE_RS,
                    "best_only": True, "class_i": cls_i, "spec_i": spec_i,
                    "externals": True, "limit": "1000", "sort_by": "head-useful-dps",
                }
                try:
                    r = requests.post(TOP_URL, json=payload, headers=HEADERS, timeout=30)
                    r.raise_for_status()
                    entries = r.json()
                    # Фільтруємо тільки гравців гільдії
                    for entry in entries:
                        name = entry[3]
                        if name not in members_specs:
                            continue
                        udps = round(entry[1], 1)
                        # Знаходимо відповідний спек для цього гравця
                        for (c, s, si) in members_specs.get(name, []):
                            if c == cls_name and s == spec_name:
                                key = (name, c, s)
                                if key not in rs_data:
                                    rs_data[key] = {}
                                rs_data[key][boss] = udps
                except Exception as e:
                    pass
                time.sleep(0.2)

    return rs_data

# ─── Основна логіка ──────────────────────────────────────────────────────────

def build_guild_data(members):
    members_specs = find_guild_members_on_server(members)
    print(f"\n   Знайдено {len(members_specs)} гравців\n")

    # Крок 3: міні-боси РС
    rs_data = fetch_rs_mini_bosses(members_specs)

    # Крок 2: /character для кожного гравця/спеку
    rows = []
    total = sum(len(specs) for specs in members_specs.values())
    done  = 0
    print("\n📊 Крок 2: отримуємо дані по кожному гравцю...")

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

            bosses = {}
            for boss in BOSS_ORDER:
                if boss in RS_MINI_BOSSES:
                    # Беремо з rs_data
                    bosses[boss] = rs_data.get((name, cls_name, spec_name), {}).get(boss, 0)
                else:
                    bd = bosses_data.get(boss, {})
                    bosses[boss] = round(bd.get("dps_max", 0) or 0, 1)

            score = round(overall_points / 100.0, 2)

            rows.append({
                "name":         name,
                "server":       SERVER,
                "class":        cls_name,
                "spec":         spec_name,
                "specIndex":    int(spec_i),
                "overallRank":  overall_rank,
                "overallScore": score,
                "bosses":       bosses,
            })
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
    print("🏰 Deus Vult / FreedomUA\n")
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
