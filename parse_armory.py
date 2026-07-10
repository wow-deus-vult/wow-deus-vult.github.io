#!/usr/bin/env python3
"""
parse_armory.py
Parses GearScore.lua from WoW (R113 account) and fetches item data from wowhead.
Outputs armory/armory_data.json for the GitHub Pages armory.

Usage:
  python parse_armory.py              # parse + fetch missing items + save
  python parse_armory.py --parse-only # parse Lua only, skip wowhead fetch
  python parse_armory.py --export     # rebuild JSON from existing cache, no new fetches
"""

import re, json, time, os, sys, argparse, random
from datetime import date
import requests

LUA_PATH    = r"D:\world of warcraft 3.3.5a hd – 3\WTF\Account\R113\SavedVariables\GearScore.lua"
OUTPUT_DIR  = "armory"
ITEMS_CACHE = os.path.join(OUTPUT_DIR, "items_cache.json")
DATA_FILE   = os.path.join(OUTPUT_DIR, "armory_data.json")
GS_BEST     = os.path.join(OUTPUT_DIR, "gs_best.json")

SLOT_NAMES = [
    None,
    "Head","Neck","Shoulders","Shirt","Chest",
    "Waist","Legs","Feet","Wrist","Hands",
    "Ring 1","Ring 2","Trinket 1","Trinket 2","Back",
    "Main Hand","Off Hand","Ranged",
]

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"


# ── LUA PARSER ────────────────────────────────────────────────────────────────

def parse_lua():
    print(f"Reading: {LUA_PATH}")
    with open(LUA_PATH, encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Strip Lua comments
    content = re.sub(r"--[^\n]*", "", content)

    marker = '["Players"] = {'
    start = content.find(marker)
    if start == -1:
        print("ERROR: Players section not found!")
        return []

    # Find matching closing brace for the Players block
    pos = start + len(marker)
    depth = 1
    while pos < len(content) and depth > 0:
        if content[pos] == "{": depth += 1
        elif content[pos] == "}": depth -= 1
        pos += 1

    players_text = content[start + len(marker) : pos - 1]

    players = []
    scan = 0

    while scan < len(players_text):
        m = re.search(r'\["([^"]+)"\]\s*=\s*\{', players_text[scan:])
        if not m:
            break

        name = m.group(1)
        block_open = scan + m.end()

        depth = 1
        j = block_open
        while j < len(players_text) and depth > 0:
            if players_text[j] == "{": depth += 1
            elif players_text[j] == "}": depth -= 1
            j += 1

        body = players_text[block_open : j - 1]
        char = {"Name": name}

        for fm in re.finditer(r'\["(\w+)"\]\s*=\s*"([^"]*)"', body):
            char[fm.group(1)] = fm.group(2)
        for fm in re.finditer(r'\["(\w+)"\]\s*=\s*(-?\d+)', body):
            if fm.group(1) not in char:
                char[fm.group(1)] = int(fm.group(2))

        # Equip slots: "itemId:enchantId" or nil
        equip = []
        em = re.search(r'\["Equip"\]\s*=\s*\{([^}]*)\}', body, re.DOTALL)
        if em:
            for im in re.finditer(r'"(\d+:\d+)"|nil', em.group(1)):
                equip.append(im.group(1) if im.group(1) else "0:0")
        char["Equip"] = equip

        players.append(char)
        scan = j

    print(f"Parsed {len(players)} characters")
    return players


# ── BEST GS STORE ─────────────────────────────────────────────────────────────

def apply_best_gs(characters):
    """Keep the snapshot with highest GearScore per character across all scans.
    Guards against transmog making the addon record wrong low-level items."""
    best = {}
    if os.path.exists(GS_BEST):
        with open(GS_BEST, encoding="utf-8") as f:
            best = json.load(f)

    updated = 0
    for char in characters:
        name = char.get("Name", "")
        gs   = char.get("GearScore", 0) or 0
        prev_gs = best.get(name, {}).get("GearScore", 0) or 0
        if gs > prev_gs:
            best[name] = char
            updated += 1

    with open(GS_BEST, "w", encoding="utf-8") as f:
        json.dump(best, f, ensure_ascii=False, separators=(",", ":"))

    # Build result: use best record for each character
    # Include both current-scan chars (possibly replaced by better historical)
    # and historical chars not in current scan
    result = list(best.values())
    kept   = sum(1 for c in characters if (c.get("GearScore") or 0) < (best.get(c["Name"], {}).get("GearScore") or 0))
    print(f"  Best GS: {len(result)} total | {updated} improved | {kept} kept historical (transmog guard)")
    return result


# ── ITEM CACHE ────────────────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(ITEMS_CACHE):
        with open(ITEMS_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(ITEMS_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def fetch_item(item_id):
    url = f"https://nether.wowhead.com/wotlk/tooltip/item/{item_id}"
    for attempt in range(3):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 429:
                wait = 45 + attempt * 30
                print(f"\n  [429] waiting {wait}s…", flush=True)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return None
            data = r.json()
            tooltip = data.get("tooltip", "")
            ilvl_m = re.search(r"Item Level.*?(\d{2,3})", tooltip)
            return {
                "name":    data.get("name", f"Item {item_id}"),
                "quality": data.get("quality", 1),
                "icon":    data.get("icon", "inv_misc_questionmark"),
                "ilvl":    int(ilvl_m.group(1)) if ilvl_m else 0,
            }
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def fetch_items(characters, cache):
    # Collect all unique non-zero item IDs
    item_ids = set()
    for char in characters:
        for entry in char.get("Equip", []):
            iid = entry.split(":")[0]
            if iid and iid != "0":
                item_ids.add(iid)

    missing = sorted([iid for iid in item_ids if iid not in cache], key=int)
    print(f"\nUnique items: {len(item_ids)} | Missing from cache: {len(missing)}")
    if not missing:
        print("All items cached!")
        return cache

    eta_min = len(missing) * 1.3 / 60
    print(f"Fetching {len(missing)} items from wowhead (~{eta_min:.0f} min)…\n")

    for i, iid in enumerate(missing):
        print(f"  [{i+1}/{len(missing)}] {iid}… ", end="", flush=True)
        data = fetch_item(iid)
        if data:
            cache[iid] = data
            print(f"{data['name']} (ilvl {data['ilvl']}, q{data['quality']})")
        else:
            cache[iid] = {"name": f"Item {iid}", "quality": 1, "icon": "inv_misc_questionmark", "ilvl": 0}
            print("FAILED")

        if (i + 1) % 50 == 0:
            save_cache(cache)
            print(f"  [OK] Cache saved ({i+1}/{len(missing)})\n")

        time.sleep(random.uniform(0.9, 1.6))

    save_cache(cache)
    return cache


# ── OUTPUT ────────────────────────────────────────────────────────────────────

def build_json(characters, cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chars_out = []
    for char in characters:
        equip = []
        for slot_idx, entry in enumerate(char.get("Equip", []), start=1):
            parts = entry.split(":")
            item_id   = int(parts[0]) if parts[0] else 0
            enchant_id = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            equip.append({"slot": slot_idx, "itemId": item_id, "enchantId": enchant_id})

        chars_out.append({
            "name":    char.get("Name", ""),
            "gs":      char.get("GearScore", 0),
            "ilvl":    char.get("Average", 0),
            "class":   char.get("Class", ""),
            "race":    char.get("Race", ""),
            "guild":   char.get("Guild", ""),
            "faction": char.get("Faction", "H"),
            "level":   char.get("Level", 80),
            "spec":    char.get("Spec", 1),
            "sex":     char.get("Sex", 1),
            "date":    char.get("Date", 0),
            "scanned": char.get("Scanned", ""),
            "equip":   equip,
        })

    chars_out.sort(key=lambda x: x["gs"], reverse=True)

    out = {
        "updated":    date.today().isoformat(),
        "characters": chars_out,
        "items":      cache,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(DATA_FILE) / 1024
    print(f"\nSaved: {DATA_FILE}")
    print(f"  Characters : {len(chars_out)}")
    print(f"  Items      : {len(cache)}")
    print(f"  File size  : {size_kb:.0f} KB")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parse-only", action="store_true",
                        help="Parse Lua only, skip wowhead fetch")
    parser.add_argument("--export", action="store_true",
                        help="Rebuild JSON from cache only, no new fetches")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    characters = parse_lua()
    if not characters:
        sys.exit(1)

    characters = apply_best_gs(characters)

    cache = load_cache()
    print(f"Items already cached: {len(cache)}")

    if not args.parse_only and not args.export:
        cache = fetch_items(characters, cache)

    build_json(characters, cache)


if __name__ == "__main__":
    main()
