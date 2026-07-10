"""
Update enchants_cache.json with names from DBC + gem icons from GemProperties.
"""
import mpyq, struct, sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR  = r"D:\world of warcraft 3.3.5a hd – 3\Data"
CACHE_OUT = r"D:\Uwu-parcer-DEUS\armory\enchants_cache.json"


def parse_dbc(data):
    if data[:4] != b'WDBC': return None, None, None
    rc, fc, rs, sb_size = struct.unpack_from('<4I', data, 4)
    words = rs // 4
    recs_end = 20 + rc * rs
    sb = data[recs_end:recs_end + sb_size]
    recs = [struct.unpack_from(f'<{words}I', data, 20 + i * rs) for i in range(rc)]
    return recs, sb, fc


def get_str(sb, off):
    if off == 0 or off >= len(sb): return ''
    end = sb.find(b'\x00', off)
    raw = sb[off:(end if end != -1 else off+300)]
    for enc in ['utf-8', 'cp1251']:
        try: return raw.decode(enc)
        except: pass
    return ''


def load_mpq_dbc(mpq_rel, dbc_name):
    path = os.path.join(DATA_DIR, mpq_rel)
    if not os.path.exists(path): return None
    try:
        arc = mpyq.MPQArchive(path)
        data = arc.read_file(dbc_name.encode() if isinstance(dbc_name, str) else dbc_name)
        if data and data[:4] == b'WDBC': return parse_dbc(data)
    except: pass
    return None


# ── 1. SpellItemEnchantment names ─────────────────────────────────────────────
sie_en = load_mpq_dbc(r"enus\patch-enus-2.mpq", "DBFilesClient\\SpellItemEnchantment.dbc")
sie_ru = load_mpq_dbc(r"ruru\patch-ruru-3.mpq", "DBFilesClient\\SpellItemEnchantment.dbc")

def build_sie_lookup(dbc, name_field):
    if not dbc: return {}
    recs, sb, _ = dbc
    return {r[0]: get_str(sb, r[name_field]) for r in recs if name_field < len(r)}

en_names = build_sie_lookup(sie_en, 14)
ru_names = build_sie_lookup(sie_ru, 22) or build_sie_lookup(sie_en, 22)
print(f"SpellItemEnchantment: {len(en_names)} EN, {len(ru_names)} RU names loaded")


# ── 2. GemProperties: enchantId → socketColor ────────────────────────────────
# SocketColor enum (WoW 3.3.5a): 1=Meta, 2=Red, 4=Yellow, 8=Blue
# 6=Red+Yellow=Orange, 14=Red+Yellow+Blue=Prismatic
gp_dbc = load_mpq_dbc(r"enus\patch-enus.mpq", "DBFilesClient\\GemProperties.dbc")

enchant_to_sc = {}  # SpellItemEnchantment ID → socket color mask
if gp_dbc:
    gp_recs, _, _ = gp_dbc
    for r in gp_recs:
        if len(r) >= 5 and r[1]:
            enchant_to_sc[r[1]] = r[4]
    print(f"GemProperties: {len(enchant_to_sc)} mappings")

# WoW 3.3.5a SocketColor bitmask: 1=Meta, 2=Red, 4=Yellow, 8=Blue
# Hybrids are sums: Orange=6 (R+Y), Purple=10 (R+B), Green=12 (Y+B), Prismatic=14
SC_ICON = {
    1:  ("meta",      "inv_misc_gem_diamond_06"),
    2:  ("red",       "inv_jewelcrafting_gem_37"),
    4:  ("yellow",    "inv_jewelcrafting_gem_38"),
    8:  ("blue",      "inv_jewelcrafting_gem_39"),
    6:  ("orange",    "inv_jewelcrafting_gem_40"),  # Red+Yellow
    10: ("purple",    "inv_jewelcrafting_gem_41"),  # Red+Blue
    12: ("green",     "inv_jewelcrafting_gem_42"),  # Yellow+Blue
    14: ("prismatic", "inv_misc_gem_diamond_02"),   # Red+Yellow+Blue
}

# Override for known gems where GemProperties might differ from Freedom x5:
# 3628 = +21 Agi + 3% Crit Dmg = Chaotic Skyflare Diamond → Meta
# 3637 = +32 Sta + 2% armor from gear = Austere Earthsiege Diamond → Meta
# 3879 = +10 All Stats → could be meta or other
MANUAL_OVERRIDES = {
    3628: "inv_misc_gem_diamond_06",   # Chaotic Skyflare Diamond
    3637: "inv_misc_gem_diamond_06",   # Austere Earthsiege Diamond
    3621: "inv_misc_gem_diamond_06",   # Relentless Earthsiege Diamond
    3623: "inv_misc_gem_diamond_06",   # Insightful Earthsiege Diamond
    3625: "inv_misc_gem_diamond_06",   # Swift Skyflare Diamond
    3633: "inv_misc_gem_diamond_06",   # Revitalizing Skyflare Diamond
    3639: "inv_misc_gem_diamond_06",   # Beaming Earthsiege Diamond
    3640: "inv_misc_gem_diamond_06",   # Ember Skyflare Diamond
    3879: "inv_misc_gem_diamond_07",   # +10 All Stats (special meta or large)
}

# ── 3. Update enchants_cache.json ────────────────────────────────────────────
with open(CACHE_OUT, encoding='utf-8') as f:
    cache = json.load(f)

for eid_str, entry in cache.items():
    eid = int(eid_str)
    name_ru = ru_names.get(eid, '')
    name_en = en_names.get(eid, '')
    entry['name'] = name_ru or name_en
    entry['name_en'] = name_en
    if name_ru:
        entry['name_ru'] = name_ru

    # Icon from GemProperties socket color
    if eid in MANUAL_OVERRIDES:
        entry['icon'] = MANUAL_OVERRIDES[eid]
        entry['gem_color'] = 'meta'
    else:
        sc = enchant_to_sc.get(eid, 0)
        if sc and sc in SC_ICON:
            color_name, icon = SC_ICON[sc]
            entry['icon'] = icon
            entry['gem_color'] = color_name
        else:
            # not a gem (or unknown mask) — clear stale values
            entry['icon'] = ''
            entry.pop('gem_color', None)

with open(CACHE_OUT, 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, separators=(',', ':'))

named   = sum(1 for v in cache.values() if v.get('name'))
with_icon = sum(1 for v in cache.values() if v.get('icon'))
gems    = sum(1 for v in cache.values() if v.get('gem_color'))
print(f"Final: {len(cache)} entries, {named} with names, {with_icon} with icons, {gems} gems")

# Summary of our target gem IDs
print("\nTarget gem IDs:")
TARGET_GEMS = [3518,3524,3528,3549,3570,3628,3732,3742,3879]
for gid in TARGET_GEMS:
    v = cache.get(str(gid), {})
    print(f"  {gid}: [{v.get('gem_color','?')}] icon={v.get('icon','none')} name={v.get('name','?')}")
print(f"\nSaved -> {CACHE_OUT}")
