"""
armory_stats.py — character stat calculator for the Armory.

Computes unbuffed character-panel stats (like the in-game 'C' panel):
base race/class stats + gear + enchants + gems + socket bonuses
+ standard-build talent modifiers per dominant tree.

Limits (honest): individual talents/glyphs are not visible in scans, so
talent modifiers assume the standard PvE build of the dominant tree.
"""
import json, os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
BASE_STATS_FILE = os.path.join(_HERE, "armory", "base_stats.json")

with open(BASE_STATS_FILE, encoding="utf-8") as f:
    BASE_STATS = json.load(f)   # "Race:CLASS" -> [str, agi, sta, int, spi]

# GearScore codes → base_stats keys
RACE_MAP = {
    "HU": "Human", "DW": "Dwarf", "GN": "Gnome", "NE": "NightElf", "DR": "Draenei",
    "OR": "Orc", "TR": "Troll", "TA": "Tauren", "UN": "Undead", "BE": "BloodElf",
}
CLASS_MAP = {
    "WA": "WARRIOR", "PA": "PALADIN", "HU": "HUNTER", "RO": "ROGUE", "PR": "PRIEST",
    "DK": "DEATHKNIGHT", "SH": "SHAMAN", "MA": "MAGE", "WK": "WARLOCK", "DR": "DRUID",
}

CASTER_CLASSES = {"PR", "MA", "WK"}          # always spell power
CASTER_TREES = {                              # class → trees that play as caster
    "PA": {0},        # holy
    "SH": {0, 2},     # ele, resto
    "DR": {0, 2},     # balance, resto
}

# Stat text patterns for enchant/gem EN names, e.g. "+30 Spell Power",
# "Increases attack power by 140"
ENCH_PATTERNS = [
    (r'\+(\d+) Strength',                  'str'),
    (r'\+(\d+) Agility',                   'agi'),
    (r'\+(\d+) Stamina',                   'sta'),
    (r'\+(\d+) Intellect',                 'int'),
    (r'\+(\d+) Spirit',                    'spi'),
    (r'\+(\d+) Attack Power',              'ap'),
    (r'\+(\d+) (?:Spell Power|Spell Damage and Healing)', 'sp'),
    (r'\+(\d+) Critical Strike Rating',    'crit'),
    (r'\+(\d+) Hit Rating',                'hit'),
    (r'\+(\d+) Haste Rating',              'haste'),
    (r'\+(\d+) Expertise(?: Rating)?',     'exp'),
    (r'\+(\d+) Armor Penetration(?: Rating)?', 'arp'),
    (r'\+(\d+) Resilience Rating',         'res'),
    (r'\+(\d+) Defense Rating',            'def'),
    (r'\+(\d+) Dodge Rating',              'dodge'),
    (r'\+(\d+) Parry Rating',              'parry'),
    (r'\+(\d+) Armor',                     'armor'),
    (r'critical strike rating by (\d+)',   'crit'),
    (r'\bhit rating by (\d+)',             'hit'),
    (r'haste rating by (\d+)',             'haste'),
    (r'expertise(?: rating)? by (\d+)',    'exp'),
    (r'armor penetration(?: rating)? by (\d+)', 'arp'),
    (r'defense rating by (\d+)',           'def'),
    (r'dodge rating by (\d+)',             'dodge'),
    (r'parry rating by (\d+)',             'parry'),
    (r'spell power by (\d+)',              'sp'),
    (r'attack power by (\d+)',             'ap'),
    (r'Strength by (\d+)',                 'str'),
    (r'Agility by (\d+)',                  'agi'),
    (r'Stamina by (\d+)',                  'sta'),
    (r'Intellect by (\d+)',                'int'),
    (r'Spirit by (\d+)',                   'spi'),
    (r'(?:Restores|restores) (\d+) mana per 5 sec', 'mp5'),
]

def enchant_stats(name_en):
    """Parse stats from an enchant/gem English name."""
    if not name_en:
        return {}
    # skip proc-style enchants ("chance to ...", "sometimes ...")
    if re.search(r'chance|sometimes|often|occasionally', name_en, re.I):
        return {}
    out = {}
    for pat, key in ENCH_PATTERNS:
        for m in re.finditer(pat, name_en, re.I):
            out[key] = out.get(key, 0) + int(m.group(1))
    # "+10 All Stats" / "All Stats by 10" → all five primary stats
    for m in re.finditer(r'\+(\d+) (?:to )?All Stats|All Stats(?: and\b[^+]*)? by (\d+)', name_en, re.I):
        v = int(m.group(1) or m.group(2))
        for k in ('str', 'agi', 'sta', 'int', 'spi'):
            out[k] = out.get(k, 0) + v
    return out


# ── Socket matching ───────────────────────────────────────────────────────────
# gem_color → which socket colors it satisfies
GEM_MATCHES = {
    "red":       {"red"},
    "yellow":    {"yellow"},
    "blue":      {"blue"},
    "orange":    {"red", "yellow"},
    "purple":    {"red", "blue"},
    "green":     {"yellow", "blue"},
    "prismatic": {"red", "yellow", "blue"},
    "meta":      {"meta"},
}

def socket_bonus_active(sockets, gem_colors):
    """True if every socket has a gem whose color satisfies it (in order)."""
    if len(gem_colors) < len(sockets):
        return False
    for i, sock in enumerate(sockets):
        gc = gem_colors[i] if i < len(gem_colors) else None
        if not gc or sock not in GEM_MATCHES.get(gc, set()):
            return False
    return True


# ── Talent modifiers (standard 3.3.5 PvE builds per dominant tree) ────────────
# keys: str/agi/sta/int/spi multipliers, armor_items multiplier,
#       ap_per_armor (Bladed Armor), ap_mul, exp_pts (flat expertise points)
TALENTS = {
    ("DK", 0): {"str": 1.06 * 1.02, "sta": 1.03, "ap_per_armor": 5 / 180},   # Blood: VotTW+AbomMight+BladedArmor
    ("DK", 1): {"str": 1.04, "ap_per_armor": 5 / 180},                       # Frost: Endless Winter
    ("DK", 2): {"str": 1.03, "ap_per_armor": 5 / 180},                       # Unholy: Ravenous Dead
    ("WA", 0): {"str": 1.04, "sta": 1.04},                                   # Arms: Strength of Arms
    ("WA", 1): {"str": 1.20},                                                # Fury: Imp Berserker Stance
    ("WA", 2): {"str": 1.02, "sta": 1.06, "armor_items": 1.10},              # Prot: Vitality+Toughness
    ("PA", 0): {"int": 1.10},                                                # Holy: Divine Intellect
    ("PA", 1): {"str": 1.15, "sta": 1.06 * 1.08, "armor_items": 1.10, "exp_pts": 6},  # Prot
    ("PA", 2): {"str": 1.15},                                                # Ret: Divine Strength
    ("HU", 0): {},                                                           # BM
    ("HU", 1): {"agi": 1.04, "int": 1.04},                                   # MM: Combat Experience
    ("HU", 2): {"agi": 1.15 * 1.03},                                         # SV: LightningReflexes+HuntingParty
    ("RO", 0): {},                                                           # Assa
    ("RO", 1): {"sta": 1.04, "agi": 1.02},                                   # Combat: Vitality
    ("RO", 2): {"agi": 1.15, "str": 1.15},                                   # Sub: Sinister Calling
    ("PR", 0): {"int": 1.15},                                                # Disc: Mental Strength
    ("PR", 1): {"spi": 1.05},                                                # Holy: Spirit of Redemption
    ("PR", 2): {},                                                           # Shadow
    ("SH", 0): {},                                                           # Ele
    ("SH", 1): {"int": 1.10, "sta": 1.10},                                   # Enh: AncestralKnowledge+Toughness
    ("SH", 2): {},                                                           # Resto
    ("MA", 0): {"int": 1.15},                                                # Arcane: Arcane Mind
    ("MA", 1): {},                                                           # Fire
    ("MA", 2): {},                                                           # Frost
    ("WK", 0): {"sta": 1.10},                                                # Affli: Demonic Embrace
    ("WK", 1): {"sta": 1.10},                                                # Demo
    ("WK", 2): {"sta": 1.10},                                                # Destro
    ("DR", 0): {},                                                           # Balance
    ("DR", 1): {"str": 1.06, "agi": 1.06, "sta": 1.06, "int": 1.06, "spi": 1.06},  # Feral: SotF
    ("DR", 2): {},                                                           # Resto
}


def parse_points(spec_str):
    """'0/17/54' → [0, 17, 54] or None."""
    if not spec_str:
        return None
    try:
        pts = [int(x) for x in spec_str.split("/")]
        return pts if len(pts) == 3 and sum(pts) > 0 else None
    except ValueError:
        return None


def talent_mods(class_code, tree, pts=None):
    """Talent stat modifiers. With real point spread (pts) uses per-subtree
    rules where we have them; otherwise the dominant-tree defaults."""
    if pts and class_code == "DK":
        b, f, u = pts
        mods = {}
        str_mul = 1.0
        if b >= 5:  mods["ap_per_armor"] = 5 / 180   # Bladed Armor (Blood t1)
        if b >= 13: str_mul *= 1.06                   # Veteran of the Third War
        if b >= 13: mods["sta"] = 1.03
        if f >= 15: str_mul *= 1.04                   # Endless Winter
        if u >= 10: str_mul *= 1.03                   # Ravenous Dead
        if str_mul != 1.0:
            mods["str"] = round(str_mul, 6)
        return mods
    return TALENTS.get((class_code, tree), {}) if tree is not None else {}


def dominant_tree(talent_points):
    """'18/0/53' → index of tree with most points (0-based); None if unknown."""
    if not talent_points:
        return None
    try:
        pts = [int(x) for x in talent_points.split("/")]
        if len(pts) == 3 and sum(pts) > 0:
            return pts.index(max(pts))
    except ValueError:
        pass
    return None


SHIRT_TABARD_SLOTS = {4, 19}

def compute_stats(equip, items_cache, enchants_cache, race_code, class_code,
                  talent_points=None, level=80, tree=None):
    """Return the character-panel stat dict, or None if base stats unknown.
    tree: 0/1/2 forces a talent tree; None = derive from talent_points."""
    race = RACE_MAP.get(race_code)
    cls  = CLASS_MAP.get(class_code)
    if not race or not cls:
        return None
    base = BASE_STATS.get(f"{race}:{cls}")
    if not base:
        return None

    t = {"str": base[0], "agi": base[1], "sta": base[2], "int": base[3], "spi": base[4],
         "sp": 0, "ap": 0, "hit": 0, "crit": 0, "haste": 0, "exp": 0, "arp": 0,
         "mp5": 0, "def": 0, "dodge": 0, "parry": 0, "res": 0}
    armor_items = 0

    for slot in equip:
        iid = slot.get("itemId")
        if not iid or slot.get("slot") in SHIRT_TABARD_SLOTS:
            continue
        item = items_cache.get(str(iid), {})
        for k, v in (item.get("stats") or {}).items():
            if k in t:
                t[k] += v
        armor_items += item.get("armor", 0)

        # enchant
        eid = slot.get("enchantId")
        if eid:
            en = enchants_cache.get(str(eid), {})
            for k, v in enchant_stats(en.get("name_en") or en.get("name", "")).items():
                if k == "armor":
                    armor_items += v
                elif k in t:
                    t[k] += v

        # gems
        gem_colors = []
        for gid in slot.get("gems") or []:
            if not gid:
                gem_colors.append(None)
                continue
            ge = enchants_cache.get(str(gid), {})
            gem_colors.append(ge.get("gem_color"))
            for k, v in enchant_stats(ge.get("name_en") or ge.get("name", "")).items():
                if k == "armor":
                    armor_items += v
                elif k in t:
                    t[k] += v

        # socket bonus (only when sockets are matched)
        sockets = item.get("sockets") or []
        sb = item.get("socketBonus") or {}
        if sockets and sb and socket_bonus_active(sockets, gem_colors):
            for k, v in sb.items():
                if k == "armor":
                    armor_items += v
                elif k in t:
                    t[k] += v

    # talents
    pts = parse_points(talent_points)
    if tree is None:
        tree = dominant_tree(talent_points)
    mods = talent_mods(class_code, tree, pts)
    for stat in ("str", "agi", "sta", "int", "spi"):
        if stat in mods:
            t[stat] = round(t[stat] * mods[stat])
    armor_items = round(armor_items * mods.get("armor_items", 1.0))

    armor = armor_items + t["agi"] * 2

    # attack power (unbuffed, standard formulas @80)
    if class_code in ("WA", "PA", "DK"):
        ap = t["str"] * 2 + level * 3 - 20
    elif class_code in ("RO", "SH"):
        ap = t["str"] + t["agi"] + level * 2 - 20
    elif class_code == "HU":
        ap = t["agi"] + level * 2 - 10          # ranged AP
    elif class_code == "DR":
        ap = t["str"] * 2 - 20                  # caster form
    else:
        ap = 0
    ap += t["ap"]                               # flat AP from gear/enchants
    ap += round(armor * mods.get("ap_per_armor", 0))
    ap = round(ap * mods.get("ap_mul", 1.0))

    exp_pts = int(t["exp"] / 8.1974) + mods.get("exp_pts", 0)

    is_caster = class_code in CASTER_CLASSES or (
        tree is not None and tree in CASTER_TREES.get(class_code, set()))

    out = {
        "str": t["str"], "agi": t["agi"], "sta": t["sta"],
        "int": t["int"], "spi": t["spi"],
        "armor": armor,
        "hit": t["hit"], "crit": t["crit"], "haste": t["haste"],
        "caster": is_caster,
    }
    if is_caster:
        out["sp"]  = t["sp"]
        out["mp5"] = t["mp5"]
    else:
        out["ap"]  = ap
        out["expPts"] = exp_pts
        out["arp"] = t["arp"]
        if t["sp"]:
            out["sp"] = t["sp"]                 # hybrids (enh/ret) still show SP
    if t["def"]:    out["def"]    = t["def"]
    if t["dodge"]:  out["dodge"]  = t["dodge"]
    if t["parry"]:  out["parry"]  = t["parry"]
    if t["res"]:    out["res"]    = t["res"]
    return out
