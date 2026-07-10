"""
Extract SpellItemEnchantment names from WoW 3.3.5a MPQ patches.
Gem IDs from Examiner are SpellItemEnchantment IDs → read from DBC.
"""
import mpyq, struct, sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = r"D:\world of warcraft 3.3.5a hd – 3\Data"

TARGET_IDS = {
    17,18,464,803,846,850,884,927,928,943,983,1071,1075,1099,1119,1128,1144,1147,
    1597,1600,1603,1606,1843,1893,1897,1951,1952,1953,2326,2332,2381,
    2658,2661,2662,2666,2673,2724,3222,3225,3229,3231,3232,3233,3234,
    3236,3238,3241,3243,3244,3245,3246,3252,3253,3256,3294,3296,3297,
    3326,3327,3328,3329,3330,3368,3369,3370,
    3518,3524,3528,3549,3570,3594,3599,3601,3603,3604,3605,3606,3607,3608,
    3628,3718,3719,3720,3721,3722,3728,3730,3731,3732,3742,3748,3754,3756,
    3757,3758,3788,3789,3790,3791,3793,3794,3795,3797,3808,3809,3810,3811,
    3812,3813,3814,3817,3818,3819,3820,3822,3823,3824,3825,3826,3827,3828,
    3829,3830,3831,3832,3833,3834,3835,3836,3837,3838,3839,3840,3842,3843,
    3845,3847,3849,3850,3852,3853,3854,3855,3858,3859,3860,3869,3870,3872,
    3873,3875,3876,3878,3879,3883,
}


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


# SpellItemEnchantment.dbc WotLK 3.3.5a field layout:
# 0: ID
# 1: charges
# 2,3,4: Effect[3]  (enchantment effect type enum)
# 5,6,7: EffectArg[3]
# 8,9,10: EffectAmount[3]
# 11: Condition_id (from SpellItemEnchantmentCondition)
# 12: ScalingType
# 13: MinScalingLevel
# 14: NAME_enUS ← main English name
# 15: NAME_koKR
# 16: NAME_frFR
# 17: NAME_deDE
# 18: NAME_zhCN
# 19: NAME_zhTW
# 20: NAME_esES
# 21: NAME_esMX
# 22: NAME_ruRU
# 23..28: NAME_???(remaining locales) or flags
# 29: name_flags
# 30: ItemVisual (uint32)
# 31: Flags (uint32)
# 32: SrcItemId (uint32)
# 33: Condition_id2 (uint32)
# 34: Skill_id (uint32)
# 35: Skill_tier (uint32)
# 36: RequiredLevel (uint32)
# → 37 fields total
NAME_EN = 14
NAME_RU = 22   # field 22 = ruRU name

# Load best English DBC + Russian locale DBC
en_dbc = None
ru_dbc = None

priority_mpqs_en = [
    r"enus\patch-enus-2.mpq",
    r"enus\patch-enus-3.mpq",
    r"enus\patch-enus.mpq",
    r"enus\locale-enus.mpq",
]
priority_mpqs_ru = [
    r"ruru\patch-ruru-3.mpq",
    r"ruru\patch-ruru-2.mpq",
    r"ruru\patch-ruru.mpq",
    r"ruru\locale-ruru.mpq",
]

DBC_NAME = b"DBFilesClient\\SpellItemEnchantment.dbc"

for mpq_rel in priority_mpqs_en:
    mpq_path = os.path.join(DATA_DIR, mpq_rel)
    if not os.path.exists(mpq_path): continue
    try:
        arc = mpyq.MPQArchive(mpq_path)
        data = arc.read_file(DBC_NAME)
        if data and data[:4] == b'WDBC':
            en_dbc = parse_dbc(data)
            print(f"Loaded EN DBC from {mpq_rel}: {len(en_dbc[0])} records, {en_dbc[2]} fields")
            break
    except Exception as e:
        pass

for mpq_rel in priority_mpqs_ru:
    mpq_path = os.path.join(DATA_DIR, mpq_rel)
    if not os.path.exists(mpq_path): continue
    try:
        arc = mpyq.MPQArchive(mpq_path)
        data = arc.read_file(DBC_NAME)
        if data and data[:4] == b'WDBC':
            ru_dbc = parse_dbc(data)
            print(f"Loaded RU DBC from {mpq_rel}: {len(ru_dbc[0])} records, {ru_dbc[2]} fields")
            break
    except Exception as e:
        pass

# Build lookup dict by ID → name
def build_lookup(dbc, name_field):
    if not dbc: return {}
    recs, sb, fc = dbc
    lookup = {}
    for rec in recs:
        entry_id = rec[0]
        if name_field < len(rec):
            name = get_str(sb, rec[name_field])
            if name:
                lookup[entry_id] = name
    return lookup

en_names = build_lookup(en_dbc, NAME_EN)
ru_names = build_lookup(ru_dbc, NAME_RU)

# For EN DBC, also try Russian name field (field 22)
if en_dbc:
    en_ru_names = build_lookup(en_dbc, NAME_RU)
    print(f"  EN DBC Russian names found: {sum(1 for v in en_ru_names.values() if v)}")

print(f"\nEN names: {len(en_names)}, RU names: {len(ru_names)}")

# Show our target IDs
print("\nTarget ID names:")
results = {}
missing = []
for gid in sorted(TARGET_IDS):
    ru = ru_names.get(gid, '') or en_ru_names.get(gid, '') if en_dbc else ''
    en = en_names.get(gid, '')
    name = ru or en
    if name:
        print(f"  {gid}: EN='{en}' RU='{ru}'")
        results[str(gid)] = {'name_en': en, 'name_ru': ru, 'name': ru or en}
    else:
        missing.append(gid)

print(f"\nFound: {len(results)}, Missing: {len(missing)}")
print(f"Missing IDs: {sorted(missing)}")

# Verify a few known enchants to check field mapping
print("\n--- Verification: known IDs ---")
for test_id in [3234, 3817, 3326, 3330, 3518, 3732]:
    en = en_names.get(test_id, 'NOT FOUND')
    ru = ru_names.get(test_id, '') or (en_ru_names.get(test_id, '') if en_dbc else '')
    print(f"  {test_id}: en='{en}' ru='{ru}'")

# Save result
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'armory', 'enchants_names.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(results)} enchant/gem names -> {out}")
