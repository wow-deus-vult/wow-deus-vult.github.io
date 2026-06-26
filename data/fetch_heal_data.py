"""
fetch_heal_data.py — Deus Vult / FreedomUA
Рейтинг хілів по Валітрії Dreamwalker (єдиний бос де /character дає HPS)
"""

import json, os, re, time, requests
from datetime import datetime, timezone

SERVER    = "FreedomUA"
CHAR_URL  = "https://uwu-logs.xyz/character"
TOP_URL   = "https://uwu-logs.xyz/top"
EPGP_FILE = os.path.join(os.path.dirname(__file__), "EPGP.lua")
OUTPUT    = os.path.join(os.path.dirname(__file__), "data", "guild-heal.json")

HEADERS = {
    "Content-Type": "application/json",
    "Origin":       "https://uwu-logs.xyz",
    "Referer":      "https://uwu-logs.xyz/character",
}

BOSS = "Valithria Dreamwalker"
MODE = "25H"

# Тільки хіл-спеки
HEAL_SPECS = {
    "Paladin":  [("Holy",         "1")],
    "Priest":   [("Discipline",   "1"), ("Holy", "2")],
    "Druid":    [("Restoration",  "3")],
    "Shaman":   [("Restoration",  "3")],
}

CLASSES = [
    "Death Knight", "Druid", "Hunter", "Mage", "Paladin",
    "Priest", "Rogue", "Shaman", "Warlock", "Warrior",
]
CLASS_INDEX = {cls: str(i) for i, cls in enumerate(CLASSES)}


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


# ─── Крок 1: знайти хілів гільдії через /top ─────────────────────────────────

def find_guild_healers(members):
    found = {}
    print("🔍 Шукаємо хілів гільдії...")
    for cls_name, specs in HEAL_SPECS.items():
        cls_i = CLASS_INDEX[cls_name]
        for spec_name, spec_i in specs:
            print(f"  {cls_name}/{spec_name}...", end=" ", flush=True)
            payload = {
                "server": SERVER, "boss": BOSS, "mode": MODE,
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


# ─── Крок 2: /character для HPS на Валітрії ──────────────────────────────────

def fetch_character(name, spec_i):
    payload = {"name": name, "server": SERVER, "spec": spec_i}
    try:
        r = requests.post(CHAR_URL, json=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  ⚠ {name}/{spec_i}: {e}")
        return None




# ─── Крок 3: /rank для server_rank на Валітрії ───────────────────────────────

def get_server_ranks(rows):
    """POST /rank з HPS значеннями всіх хілів → отримуємо server_rank."""
    print("\n🏆 Отримуємо server_rank через /rank...")
    
    # Групуємо по спеку (rank рахується окремо для кожного spec)
    from collections import defaultdict
    by_spec = defaultdict(list)
    for row in rows:
        if row["hps"] > 0:
            by_spec[(row["class"], row["spec"])].append(row)
    
    rank_url = "https://uwu-logs.xyz/rank"
    
    for (cls, spec), spec_rows in by_spec.items():
        dps_payload = {r["name"]: r["hps"] for r in spec_rows}
        specs_payload = {r["name"]: f"{spec} {cls}" for r in spec_rows}
        
        payload = {
            "server": SERVER,
            "boss": BOSS,
            "mode": MODE,
            "dps": dps_payload,
            "specs": specs_payload,
        }
        try:
            r = requests.post(rank_url, json=payload, headers=HEADERS, timeout=30)
            r.raise_for_status()
            rank_data = r.json()
            for row in spec_rows:
                if row["name"] in rank_data:
                    row["server_rank"] = rank_data[row["name"]].get("rank")
                    row["server_percentile"] = rank_data[row["name"]].get("percentile")
            print(f"  {cls}/{spec}: {len(spec_rows)} гравців")
        except Exception as e:
            print(f"  ⚠ {cls}/{spec}: {e}")
        time.sleep(0.3)
    
    return rows

# ─── Основна логіка ──────────────────────────────────────────────────────────

def build_heal_data(members):
    healers = find_guild_healers(members)
    print(f"\n   Знайдено {len(healers)} хілів гільдії\n")

    rows = []
    total = sum(len(specs) for specs in healers.values())
    done = 0

    print("📊 Отримуємо HPS дані...")
    for name, specs in healers.items():
        for cls_name, spec_name, spec_i in specs:
            done += 1
            print(f"  [{done}/{total}] {name} / {cls_name} {spec_name}...", end=" ", flush=True)

            data = fetch_character(name, spec_i)
            if not data:
                print("пропущено")
                continue

            bosses_data = data.get("bosses", {})
            val_data = bosses_data.get(BOSS, {})
            hps = round(val_data.get("dps_max", 0) or 0, 1)
            server_rank = val_data.get("rank", None)

            overall_rank  = data.get("overall_rank", 9999) or 9999
            overall_score = round((data.get("overall_points", 0) or 0) / 100.0, 2)

            rows.append({
                "name":         name,
                "class":        cls_name,
                "spec":         spec_name,
                "hps":          hps,
                "server_rank":  server_rank,
                "overall_rank": overall_rank,
                "overall_score": overall_score,
            })
            print(f"HPS={hps} server_rank=#{server_rank}")
            time.sleep(0.2)

    # Отримуємо server_rank
    rows = get_server_ranks(rows)

    # Рахуємо гільд-ранк по HPS
    rows.sort(key=lambda r: r["hps"], reverse=True)
    for i, row in enumerate(rows):
        row["guild_rank"] = i + 1

    return {
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "boss":        BOSS,
        "mode":        MODE,
        "totalHealers": len(rows),
        "rows":        rows,
    }


if __name__ == "__main__":
    print("🏥 Heal рейтинг Deus Vult / FreedomUA\n")
    if not os.path.exists(EPGP_FILE):
        print(f"❌ {EPGP_FILE} не знайдено!")
        exit(1)
    members = parse_epgp_members(EPGP_FILE)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    data = build_heal_data(members)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(data['rows'])} хілів → {OUTPUT}")
