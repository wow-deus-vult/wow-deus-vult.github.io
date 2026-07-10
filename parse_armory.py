#!/usr/bin/env python3
"""
parse_armory.py
Parses GearScore.lua + Examiner.lua and fetches item/enchant data from wowhead.
Outputs armory/armory_data.json for the GitHub Pages armory.

Usage:
  python parse_armory.py              # parse + fetch missing items/enchants + save
  python parse_armory.py --parse-only # parse Lua only, skip wowhead fetch
  python parse_armory.py --export     # rebuild JSON from existing cache, no new fetches
"""

import re, json, time, os, sys, argparse, random
from datetime import date
import requests

LUA_PATH       = r"D:\world of warcraft 3.3.5a hd – 3\WTF\Account\R113\SavedVariables\GearScore.lua"
EXAMINER_LUA   = r"D:\world of warcraft 3.3.5a hd – 3\WTF\Account\R113\SavedVariables\Examiner.lua"
OUTPUT_DIR     = "armory"
ITEMS_CACHE    = os.path.join(OUTPUT_DIR, "items_cache.json")
ENCHANTS_CACHE = os.path.join(OUTPUT_DIR, "enchants_cache.json")
DATA_FILE      = os.path.join(OUTPUT_DIR, "armory_data.json")
GS_BEST        = os.path.join(OUTPUT_DIR, "gs_best.json")

# Examiner slot name → slot number used in GearScore (1-18)
EXAMINER_SLOT_MAP = {
    "HeadSlot": 1,       "NeckSlot": 2,       "ShoulderSlot": 3,  "ShirtSlot": 4,
    "ChestSlot": 5,      "WaistSlot": 6,       "LegsSlot": 7,      "FeetSlot": 8,
    "WristSlot": 9,      "HandsSlot": 10,      "Finger0Slot": 11,  "Finger1Slot": 12,
    "Trinket0Slot": 13,  "Trinket1Slot": 14,   "BackSlot": 15,
    "MainHandSlot": 16,  "SecondaryHandSlot": 17, "RangedSlot": 18,
}

SLOT_NAMES = [
    None,
    "Head","Neck","Shoulders","Shirt","Chest",
    "Waist","Legs","Feet","Wrist","Hands",
    "Ring 1","Ring 2","Trinket 1","Trinket 2","Back",
    "Main Hand","Off Hand","Ranged",
]

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"


# ── GEARSCORE LUA PARSER ──────────────────────────────────────────────────────

def parse_lua():
    print(f"Reading: {LUA_PATH}")
    with open(LUA_PATH, encoding="utf-8", errors="replace") as f:
        content = f.read()

    content = re.sub(r"--[^\n]*", "", content)

    marker = '["Players"] = {'
    start = content.find(marker)
    if start == -1:
        print("ERROR: Players section not found!")
        return []

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

        equip = []
        em = re.search(r'\["Equip"\]\s*=\s*\{([^}]*)\}', body, re.DOTALL)
        if em:
            for im in re.finditer(r'"(\d+:\d+)"|nil', em.group(1)):
                equip.append(im.group(1) if im.group(1) else "0:0")
        char["Equip"] = equip

        players.append(char)
        scan = j

    print(f"Parsed {len(players)} characters from GearScore")
    return players


# ── EXAMINER LUA PARSER ───────────────────────────────────────────────────────

def parse_examiner():
    """Parse Examiner.lua → {name: {slot_num: {itemId, enchantId, gems: [id,...]}}}"""
    if not os.path.exists(EXAMINER_LUA):
        print("Examiner.lua not found, skipping.")
        return {}

    with open(EXAMINER_LUA, encoding="utf-8", errors="replace") as f:
        content = f.read()

    content = re.sub(r"--[^\n]*", "", content)

    marker = "Examiner_Cache = {"
    start = content.find(marker)
    if start == -1:
        print("  Examiner_Cache empty or not found.")
        return {}

    pos = start + len(marker)
    depth = 1
    while pos < len(content) and depth > 0:
        if content[pos] == "{": depth += 1
        elif content[pos] == "}": depth -= 1
        pos += 1
    cache_text = content[start + len(marker) : pos - 1]

    result = {}
    scan = 0

    while scan < len(cache_text):
        m = re.search(r'\["([^"]+)"\]\s*=\s*\{', cache_text[scan:])
        if not m:
            break

        name = m.group(1)
        block_open = scan + m.end()

        depth = 1
        j = block_open
        while j < len(cache_text) and depth > 0:
            if cache_text[j] == "{": depth += 1
            elif cache_text[j] == "}": depth -= 1
            j += 1

        char_body = cache_text[block_open : j - 1]
        scan = j

        items_m = re.search(r'\["Items"\]\s*=\s*\{', char_body)
        if not items_m:
            continue

        items_pos = items_m.end()
        items_depth = 1
        k = items_pos
        while k < len(char_body) and items_depth > 0:
            if char_body[k] == "{": items_depth += 1
            elif char_body[k] == "}": items_depth -= 1
            k += 1
        items_body = char_body[items_pos : k - 1]

        slots = {}
        for slot_m in re.finditer(r'\["(\w+)"\]\s*=\s*"item:([^"]+)"', items_body):
            slot_name  = slot_m.group(1)
            link_parts = slot_m.group(2).split(":")
            slot_num   = EXAMINER_SLOT_MAP.get(slot_name)
            if slot_num is None:
                continue

            item_id    = int(link_parts[0]) if link_parts[0] else 0
            enchant_id = int(link_parts[1]) if len(link_parts) > 1 and link_parts[1] else 0
            gems = [int(link_parts[i]) for i in range(2, min(5, len(link_parts)))
                    if link_parts[i] and int(link_parts[i]) != 0]

            slots[slot_num] = {"itemId": item_id, "enchantId": enchant_id, "gems": gems}

        if slots:
            result[name] = slots

    print(f"Examiner: {len(result)} characters with detailed gear")
    return result


# ── BEST GS STORE ─────────────────────────────────────────────────────────────

def apply_best_gs(characters):
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


# ── ENCHANT / GEM CACHE ───────────────────────────────────────────────────────

def load_enchants_cache():
    if os.path.exists(ENCHANTS_CACHE):
        with open(ENCHANTS_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_enchants_cache(cache):
    with open(ENCHANTS_CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))


def fetch_enchant(eid):
    """Fetch a SpellItemEnchantment entry from wowhead."""
    url = f"https://nether.wowhead.com/wotlk/tooltip/enchantment/{eid}"
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
            name = data.get("name", "")
            if not name:
                return None
            return {
                "name": name,
                "icon": data.get("icon", "inv_enchant_formulaepic_01"),
            }
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def fetch_enchants(characters, examiner_data, ecache):
    """Collect all enchant/gem SpellItemEnchantment IDs and fetch missing ones."""
    all_ids = set()

    # Enchants from GearScore (all 663 characters)
    for char in characters:
        for entry in char.get("Equip", []):
            parts = entry.split(":")
            eid = parts[1] if len(parts) > 1 else "0"
            if eid and eid != "0":
                all_ids.add(eid)

    # Enchants + gems from Examiner (inspected characters)
    for slots in examiner_data.values():
        for slot in slots.values():
            eid = slot.get("enchantId", 0)
            if eid:
                all_ids.add(str(eid))
            for gid in slot.get("gems", []):
                if gid:
                    all_ids.add(str(gid))

    missing = sorted([eid for eid in all_ids if eid not in ecache], key=int)
    print(f"\nUnique enchants/gems: {len(all_ids)} | Missing: {len(missing)}")
    if not missing:
        print("All enchants/gems cached!")
        return ecache

    print(f"Fetching {len(missing)} enchants/gems from wowhead…\n")
    for i, eid in enumerate(missing):
        print(f"  [{i+1}/{len(missing)}] {eid}… ", end="", flush=True)
        data = fetch_enchant(eid)
        if data:
            ecache[eid] = data
            print(data["name"])
        else:
            ecache[eid] = {"name": "", "icon": ""}
            print("not found")

        if (i + 1) % 50 == 0:
            save_enchants_cache(ecache)
        time.sleep(random.uniform(0.8, 1.4))

    save_enchants_cache(ecache)
    return ecache


# ── OUTPUT ────────────────────────────────────────────────────────────────────

def build_json(characters, items_cache, examiner_data, enchants_cache):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chars_out = []

    for char in characters:
        name = char.get("Name", "")
        exam_slots = examiner_data.get(name, {})

        equip = []
        for slot_idx, entry in enumerate(char.get("Equip", []), start=1):
            parts = entry.split(":")
            item_id    = int(parts[0]) if parts[0] else 0
            enchant_id = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            gems       = []

            # Examiner overrides: more precise enchant + adds gems
            if slot_idx in exam_slots:
                ex = exam_slots[slot_idx]
                enchant_id = ex["enchantId"]
                gems       = ex["gems"]

            equip.append({
                "slot":      slot_idx,
                "itemId":    item_id,
                "enchantId": enchant_id,
                "gems":      gems,
            })

        chars_out.append({
            "name":        name,
            "gs":          char.get("GearScore", 0),
            "ilvl":        char.get("Average", 0),
            "class":       char.get("Class", ""),
            "race":        char.get("Race", ""),
            "guild":       char.get("Guild", ""),
            "faction":     char.get("Faction", "H"),
            "level":       char.get("Level", 80),
            "spec":        char.get("Spec", 1),
            "sex":         char.get("Sex", 1),
            "date":        char.get("Date", 0),
            "scanned":     char.get("Scanned", ""),
            "equip":       equip,
            "hasGems":     bool(exam_slots),
        })

    chars_out.sort(key=lambda x: x["gs"], reverse=True)

    out = {
        "updated":    date.today().isoformat(),
        "characters": chars_out,
        "items":      items_cache,
        "enchants":   {k: v for k, v in enchants_cache.items() if v.get("name")},
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(DATA_FILE) / 1024
    with_gems = sum(1 for c in chars_out if c["hasGems"])
    print(f"\nSaved: {DATA_FILE}")
    print(f"  Characters       : {len(chars_out)}")
    print(f"  With gems/enchants: {with_gems}")
    print(f"  Items            : {len(items_cache)}")
    print(f"  Enchants/gems    : {len(enchants_cache)}")
    print(f"  File size        : {size_kb:.0f} KB")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parse-only", action="store_true",
                        help="Parse Lua only, skip wowhead fetch")
    parser.add_argument("--export", action="store_true",
                        help="Rebuild JSON from existing cache, no new fetches")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    characters = parse_lua()
    if not characters:
        sys.exit(1)

    characters = apply_best_gs(characters)

    examiner_data  = parse_examiner()
    items_cache    = load_cache()
    enchants_cache = load_enchants_cache()

    print(f"Items cached: {len(items_cache)} | Enchants cached: {len(enchants_cache)}")

    if not args.parse_only and not args.export:
        items_cache    = fetch_items(characters, items_cache)
        enchants_cache = fetch_enchants(characters, examiner_data, enchants_cache)

    build_json(characters, items_cache, examiner_data, enchants_cache)


if __name__ == "__main__":
    main()
