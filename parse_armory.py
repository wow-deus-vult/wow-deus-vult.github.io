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

# GearScore saves a record under the localized "Unknown" placeholder when it
# scans a player before the client resolved their name — garbage entries.
BAD_NAMES = {"Невідомо", "Неизвестно", "Unknown", "Inconnu", "Unbekannt"}


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
        if name in BAD_NAMES:
            scan = j
            continue
        char = {"Name": name}

        for fm in re.finditer(r'\["(\w+)"\]\s*=\s*"([^"]*)"', body):
            char[fm.group(1)] = fm.group(2)
        for fm in re.finditer(r'\["(\w+)"\]\s*=\s*(-?\d+)', body):
            if fm.group(1) not in char:
                char[fm.group(1)] = int(fm.group(2))

        equip = []
        em = re.search(r'\["Equip"\]\s*=\s*\{([^}]*)\}', body, re.DOTALL)
        if em:
            for im in re.finditer(r'"([\d:]+)"|nil', em.group(1)):
                equip.append(im.group(1) if im.group(1) else "0:0")
        char["Equip"] = equip

        players.append(char)
        scan = j

    print(f"Parsed {len(players)} characters from GearScore")
    return players


def parse_specgear():
    """Parse GS_SpecGear (patched addon) → {name: {tree0based: snapshot}}.
    snapshot = {"Equip": [...], "GearScore": n, "Average": n, "Date": str, "Spec": str}"""
    with open(LUA_PATH, encoding="utf-8", errors="replace") as f:
        content = f.read()
    content = re.sub(r"--[^\n]*", "", content)

    marker = "GS_SpecGear = {"
    start = content.find(marker)
    if start == -1:
        return {}
    pos = start + len(marker)
    depth = 1
    while pos < len(content) and depth > 0:
        if content[pos] == "{": depth += 1
        elif content[pos] == "}": depth -= 1
        pos += 1
    text = content[start + len(marker) : pos - 1]

    def _blocks(src):
        """Iterate top-level ["key"] = { ... } blocks of src → (key, body)."""
        scan = 0
        while scan < len(src):
            m = re.search(r'\["([^"]+)"\]\s*=\s*\{', src[scan:])
            if not m:
                break
            open_pos = scan + m.end()
            depth = 1
            j = open_pos
            while j < len(src) and depth > 0:
                if src[j] == "{": depth += 1
                elif src[j] == "}": depth -= 1
                j += 1
            yield m.group(1), src[open_pos : j - 1]
            scan = j

    result = {}
    name_bodies = []
    for _realm, realm_body in _blocks(text):
        name_bodies.extend(_blocks(realm_body))

    for name, body in name_bodies:
        if name in BAD_NAMES:
            continue
        trees = {}
        for tm in re.finditer(r'\[(\d)\]\s*=\s*\{', body):
            tree = int(tm.group(1)) - 1        # lua 1-based → 0-based
            t_open = tm.end()
            d2 = 1
            k = t_open
            while k < len(body) and d2 > 0:
                if body[k] == "{": d2 += 1
                elif body[k] == "}": d2 -= 1
                k += 1
            t_body = body[t_open : k - 1]

            snap = {}
            for fm in re.finditer(r'\["(\w+)"\]\s*=\s*"([^"]*)"', t_body):
                snap[fm.group(1)] = fm.group(2)
            for fm in re.finditer(r'\["(\w+)"\]\s*=\s*(-?\d+)', t_body):
                if fm.group(1) not in snap:
                    snap[fm.group(1)] = int(fm.group(2))
            equip = []
            em = re.search(r'\["Equip"\]\s*=\s*\{([^}]*)\}', t_body, re.DOTALL)
            if em:
                for im in re.finditer(r'"([\d:]+)"|nil', em.group(1)):
                    equip.append(im.group(1) if im.group(1) else "0:0")
            snap["Equip"] = equip
            if equip:
                trees[tree] = snap
        if trees:
            result[name] = trees

    if result:
        total = sum(len(v) for v in result.values())
        print(f"SpecGear: {len(result)} characters, {total} spec snapshots")
    return result


# ── EXAMINER LUA PARSER ───────────────────────────────────────────────────────

def parse_examiner():
    """Parse Examiner.lua → ({name: {slot_num: {itemId, enchantId, gems}}}, {name: talentPoints})"""
    if not os.path.exists(EXAMINER_LUA):
        print("Examiner.lua not found, skipping.")
        return {}, {}

    with open(EXAMINER_LUA, encoding="utf-8", errors="replace") as f:
        content = f.read()

    content = re.sub(r"--[^\n]*", "", content)

    marker = "Examiner_Cache = {"
    start = content.find(marker)
    if start == -1:
        print("  Examiner_Cache empty or not found.")
        return {}, {}

    pos = start + len(marker)
    depth = 1
    while pos < len(content) and depth > 0:
        if content[pos] == "{": depth += 1
        elif content[pos] == "}": depth -= 1
        pos += 1
    cache_text = content[start + len(marker) : pos - 1]

    result = {}
    talents = {}
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
            gems = [int(link_parts[i]) for i in range(2, min(6, len(link_parts)))
                    if link_parts[i] and int(link_parts[i]) != 0]

            slots[slot_num] = {"itemId": item_id, "enchantId": enchant_id, "gems": gems}

        if slots:
            result[name] = slots
            tp_m = re.search(r'\["talentPoints"\]\s*=\s*"([^"]*)"', char_body)
            if tp_m:
                talents[name] = tp_m.group(1)

    print(f"Examiner: {len(result)} characters with detailed gear")
    return result, talents


# ── BEST GS STORE ─────────────────────────────────────────────────────────────

def apply_best_gs(characters):
    best = {}
    if os.path.exists(GS_BEST):
        with open(GS_BEST, encoding="utf-8") as f:
            best = json.load(f)
    for bad in BAD_NAMES:
        best.pop(bad, None)

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


STAT_PATTERNS = [
    (r'\+(\d+) Strength',                 'str'),
    (r'\+(\d+) Agility',                  'agi'),
    (r'\+(\d+) Stamina',                  'sta'),
    (r'\+(\d+) Intellect',                'int'),
    (r'\+(\d+) Spirit',                   'spi'),
    (r'\+(\d+) Attack Power',             'ap'),
    (r'\+(\d+) Spell Power',              'sp'),
    (r'\+(\d+) Critical Strike Rating',   'crit'),
    (r'\+(\d+) Hit Rating',               'hit'),
    (r'\+(\d+) Haste Rating',             'haste'),
    (r'\+(\d+) Expertise(?: Rating)?',    'exp'),
    (r'\+(\d+) Armor Penetration(?: Rating)?', 'arp'),
    (r'\+(\d+) Resilience Rating',        'res'),
    (r'\+(\d+) Defense Rating',           'def'),
    (r'\+(\d+) Dodge Rating',             'dodge'),
    (r'\+(\d+) Parry Rating',             'parry'),
    (r'\+(\d+) Block Rating',             'block'),
    # green "Equip:" lines (both "Improves X by N" and "Increases X by N")
    (r'critical strike rating by (\d+)',  'crit'),
    (r'\bhit rating by (\d+)',            'hit'),
    (r'haste rating by (\d+)',            'haste'),
    (r'expertise(?: rating)? by (\d+)',   'exp'),
    (r'armor penetration(?: rating)? by (\d+)', 'arp'),
    (r'defense rating by (\d+)',          'def'),
    (r'dodge rating by (\d+)',            'dodge'),
    (r'parry rating by (\d+)',            'parry'),
    (r'resilience rating by (\d+)',       'res'),
    (r'spell power by (\d+)',             'sp'),
    (r'attack power by (\d+)',            'ap'),
    (r'Restores (\d+) mana per 5 sec',    'mp5'),
]

def extract_stats(text):
    """Parse stat lines from tag-stripped tooltip text (permanent stats only)."""
    # drop proc/temporary sentences: "chance to…", "…for 10 sec", "Use: …"
    text = re.sub(r'[^.!<]*?(?:chance|when struck|when you|sometimes|for \d+ sec)[^.!]*[.!]',
                  ' ', text, flags=re.IGNORECASE)
    stats = {}
    for pattern, key in STAT_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            stats[key] = stats.get(key, 0) + int(m.group(1))
    # "+10 All Stats" → all five primary stats
    for m in re.finditer(r'\+(\d+) (?:to )?All Stats', text, re.IGNORECASE):
        v = int(m.group(1))
        for k in ('str', 'agi', 'sta', 'int', 'spi'):
            stats[k] = stats.get(k, 0) + v
    return stats


def parse_gear_details(tooltip_html):
    """Extract armor, sockets, socket bonus and stats from wowhead tooltip HTML."""
    text = re.sub(r'<[^>]+>', ' ', tooltip_html)
    text = re.sub(r'\s+', ' ', text)

    # Socket bonus — cut it out so it doesn't pollute base item stats
    sb_stats = {}
    sb_m = re.search(r'Socket Bonus:\s*([^<]{0,80}?)(?:Durability|Requires|Classes|$)', text)
    if sb_m:
        sb_stats = extract_stats(sb_m.group(1))
        text = text[:sb_m.start()] + ' ' + text[sb_m.end(1):]

    armor_m = re.search(r'(\d[\d,]*) Armor(?!\s*Penetration)', text)
    armor = int(armor_m.group(1).replace(',', '')) if armor_m else 0

    sockets = [c.lower() for c in re.findall(r'(Meta|Red|Yellow|Blue) Socket', text)]

    out = {"stats": extract_stats(text)}
    if armor:    out["armor"]   = armor
    if sockets:  out["sockets"] = sockets
    if sb_stats: out["socketBonus"] = sb_stats
    return out


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
            out = {
                "name":    data.get("name", f"Item {item_id}"),
                "quality": data.get("quality", 1),
                "icon":    data.get("icon", "inv_misc_questionmark"),
                "ilvl":    int(ilvl_m.group(1)) if ilvl_m else 0,
                "v":       3,   # parser version marker (v3: arp/exp without "rating")
            }
            out.update(parse_gear_details(tooltip))
            return out
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None


def update_gear_details(equipped_ids, cache):
    """Re-fetch equipped items that lack the new detail fields (armor/sockets/fixed stats)."""
    missing = sorted([iid for iid in equipped_ids
                      if cache.get(iid, {}).get('v') != 3], key=int)
    print(f"\nEquipped items needing detail re-fetch: {len(missing)}")
    if not missing:
        return cache
    eta = len(missing) * 1.3 / 60
    print(f"Fetching {len(missing)} items (~{eta:.0f} min)…\n")
    for i, iid in enumerate(missing):
        print(f"  [{i+1}/{len(missing)}] {iid}… ", end="", flush=True)
        data = fetch_item(iid)
        if data:
            cache[iid] = data
            print(f"{data['name']} armor={data.get('armor',0)} sockets={data.get('sockets',[])}")
        else:
            print("FAILED")
        if (i + 1) % 50 == 0:
            save_cache(cache)
        time.sleep(random.uniform(0.9, 1.6))
    save_cache(cache)
    return cache


def update_item_stats(equipped_ids, cache):
    """Re-fetch stats for equipped items that don't have stats yet."""
    missing = sorted([iid for iid in equipped_ids
                      if iid in cache and not cache[iid].get('stats')], key=int)
    print(f"\nEquipped items without stats: {len(missing)}")
    if not missing:
        print("All equipped items have stats!")
        return cache

    eta = len(missing) * 1.3 / 60
    print(f"Fetching stats for {len(missing)} items (~{eta:.0f} min)…\n")
    for i, iid in enumerate(missing):
        print(f"  [{i+1}/{len(missing)}] {iid}… ", end="", flush=True)
        data = fetch_item(iid)
        if data:
            cache[iid]['stats'] = data.get('stats', {})
            s = cache[iid]['stats']
            summary = ' '.join(f"{k}:{v}" for k, v in list(s.items())[:4]) if s else "no stats"
            print(summary)
        else:
            cache[iid]['stats'] = {}
            print("FAILED")
        if (i + 1) % 50 == 0:
            save_cache(cache)
        time.sleep(random.uniform(0.9, 1.6))

    save_cache(cache)
    return cache


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

    # Enchants + gems from GearScore (all characters; gems present with patched addon)
    for char in characters:
        for entry in char.get("Equip", []):
            parts = entry.split(":")
            for p in parts[1:6]:
                if p and p.isdigit() and p != "0":
                    all_ids.add(p)

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

def sum_char_stats(equip, items_cache):
    """Sum item stats for all equipped slots."""
    total = {}
    for slot in equip:
        if not slot["itemId"]:
            continue
        item = items_cache.get(str(slot["itemId"]), {})
        for stat, val in (item.get("stats") or {}).items():
            total[stat] = total.get(stat, 0) + val
    return total if total else None


def build_equip_list(equip_strings, exam_slots=None):
    """GearScore Equip strings → list of {slot, itemId, enchantId, gems}."""
    exam_slots = exam_slots or {}
    equip = []
    for slot_idx, entry in enumerate(equip_strings, start=1):
        parts = entry.split(":")
        item_id    = int(parts[0]) if parts[0] and parts[0].isdigit() else 0
        enchant_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        # gems straight from GearScore strings (patched addon keeps fields 3-6)
        gems       = [int(p) for p in parts[2:6] if p and p.isdigit() and int(p) != 0]

        # Examiner overrides: more precise enchant + adds gems
        if slot_idx in exam_slots:
            ex = exam_slots[slot_idx]
            enchant_id = ex["enchantId"]
            gems       = ex["gems"] or gems

        equip.append({
            "slot":      slot_idx,
            "itemId":    item_id,
            "enchantId": enchant_id,
            "gems":      gems,
        })
    return equip


# class-typical tree guess when spec is unknown (matches JS DEFAULT_TREE)
DEFAULT_TREE = {"DK": 2, "WA": 1, "PA": 2, "HU": 1, "RO": 1,
                "PR": 2, "SH": 0, "MA": 2, "WK": 0, "DR": 1}

def build_json(characters, items_cache, examiner_data, enchants_cache,
               examiner_talents=None, spec_gear=None):
    from armory_stats import compute_stats, dominant_tree
    examiner_talents = examiner_talents or {}
    spec_gear = spec_gear or {}
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chars_out = []

    for char in characters:
        name = char.get("Name", "")
        exam_slots = examiner_data.get(name, {})

        equip = build_equip_list(char.get("Equip", []), exam_slots)

        # per-spec gear snapshots from the patched addon
        gear_by_spec = {}
        for tree, snap in (spec_gear.get(name) or {}).items():
            gear_by_spec[tree] = {
                "equip": build_equip_list(snap.get("Equip", [])),
                "gs":    snap.get("GearScore", 0),
                "ilvl":  snap.get("Average", 0),
                "date":  snap.get("Date", ""),
                "spec":  snap.get("Spec", ""),
            }

        stats = sum_char_stats(equip, items_cache)
        lvl = char.get("Level", 80) or 80
        race, cls = char.get("Race", ""), char.get("Class", "")
        exam_tp = examiner_talents.get(name)
        exam_tree = dominant_tree(exam_tp)

        # specs: only trees we actually SAW the character in.
        # Gear follows the spec; stats follow the gear.
        specs = {}
        for tree, gb in gear_by_spec.items():
            specs[str(tree)] = {
                "equip": gb["equip"], "gs": gb["gs"], "ilvl": gb["ilvl"],
                "date": gb["date"], "spec": gb["spec"],
                "stats": compute_stats(gb["equip"], items_cache, enchants_cache,
                                       race, cls, talent_points=gb.get("spec"),
                                       level=lvl, tree=tree),
            }
        # Examiner-known spec: attribute the main gear to that tree
        if exam_tree is not None and str(exam_tree) not in specs:
            specs[str(exam_tree)] = {
                "equip": equip, "gs": char.get("GearScore", 0),
                "ilvl": char.get("Average", 0), "date": "", "spec": exam_tp,
                "stats": compute_stats(equip, items_cache, enchants_cache,
                                       race, cls, talent_points=exam_tp,
                                       level=lvl, tree=exam_tree),
            }

        spec_detected = exam_tree
        if gear_by_spec:
            spec_detected = int(max(gear_by_spec,
                                    key=lambda t: str(gear_by_spec[t].get("date", ""))))

        # spec unknown → stats from main gear with the class-typical tree guess
        stats_main = None
        if not specs:
            stats_main = compute_stats(equip, items_cache, enchants_cache,
                                       race, cls, level=lvl,
                                       tree=DEFAULT_TREE.get(cls, 0))

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
            "hasGems":     bool(exam_slots) or any(e["gems"] for e in equip),
            "stats":       stats,
            "specs":       specs or None,
            "specTree":    spec_detected,
            "statsMain":   stats_main,
            "talents":     examiner_talents.get(name, ""),
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
    parser.add_argument("--update-stats", action="store_true",
                        help="Re-fetch stats for equipped items that are missing them")
    parser.add_argument("--update-gear", action="store_true",
                        help="Re-fetch equipped items lacking armor/sockets/equip-line stats (parser v2)")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    characters = parse_lua()
    if not characters:
        sys.exit(1)

    characters = apply_best_gs(characters)

    examiner_data, examiner_talents = parse_examiner()
    spec_gear      = parse_specgear()
    items_cache    = load_cache()
    enchants_cache = load_enchants_cache()

    print(f"Items cached: {len(items_cache)} | Enchants cached: {len(enchants_cache)}")

    if not args.parse_only and not args.export:
        items_cache    = fetch_items(characters, items_cache)
        enchants_cache = fetch_enchants(characters, examiner_data, enchants_cache)

    if args.update_stats or args.update_gear:
        # Collect all equipped item IDs across all characters
        equipped_ids = set()
        for char in characters:
            for entry in char.get("Equip", []):
                iid = entry.split(":")[0]
                if iid and iid != "0":
                    equipped_ids.add(iid)
        if args.update_gear:
            items_cache = update_gear_details(equipped_ids, items_cache)
        if args.update_stats:
            items_cache = update_item_stats(equipped_ids, items_cache)

    build_json(characters, items_cache, examiner_data, enchants_cache,
               examiner_talents, spec_gear)


if __name__ == "__main__":
    main()
