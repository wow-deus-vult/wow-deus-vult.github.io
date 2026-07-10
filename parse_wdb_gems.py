"""Parse WoW 3.3.5a WDB cache files to extract gem item data."""
import struct, json, os, re

WDB_ITEM = r"D:\world of warcraft 3.3.5a hd – 3\Cache\WDB\ruRU\itemcache.wdb"
WDB_NAME = r"D:\world of warcraft 3.3.5a hd – 3\Cache\WDB\ruRU\itemnamecache.wdb"

# Gem IDs we've seen in Examiner data
TARGET_IDS = {
    3518, 3524, 3528, 3549, 3570, 3594, 3599, 3601, 3603, 3604, 3605, 3606,
    3607, 3608, 3628, 3718, 3719, 3720, 3721, 3722, 3728, 3730, 3731, 3732,
    3742, 3748, 3754, 3756, 3757, 3758, 3788, 3789, 3790, 3791, 3793, 3794,
    3795, 3797, 3808, 3809, 3810, 3811, 3812, 3813, 3814, 3817, 3818, 3819,
    3820, 3822, 3823, 3824, 3825, 3826, 3827, 3828, 3829, 3830, 3831, 3832,
    3833, 3834, 3835, 3836, 3837, 3838, 3839, 3840, 3842, 3843, 3845, 3847,
    3849, 3850, 3852, 3853, 3854, 3855, 3858, 3859, 3860, 3869, 3870, 3872,
    3873, 3875, 3876, 3878, 3879, 3883,
}


def read_cstring(data, offset):
    """Read null-terminated string at offset."""
    end = data.index(b'\x00', offset)
    return data[offset:end].decode('utf-8', errors='replace'), end + 1


def parse_wdb_header(f):
    magic = f.read(4)
    build, locale, unk1, unk2 = struct.unpack('<4I', f.read(16))
    return magic, build


def parse_itemnamecache(path):
    """Simple: just item ID → name."""
    results = {}
    with open(path, 'rb') as f:
        magic, build = parse_wdb_header(f)
        print(f"  itemnamecache magic={magic} build={build}")
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            item_id, size = struct.unpack('<II', hdr)
            if item_id == 0 and size == 0:
                break
            data = f.read(size)
            if not data:
                break
            # itemnamecache: data is just a null-terminated name string
            try:
                name = data.split(b'\x00')[0].decode('utf-8', errors='replace')
            except Exception:
                name = ''
            if name:
                results[item_id] = name
    return results


def parse_itemcache(path, target_ids=None):
    """
    Parse itemcache.wdb to extract item name, quality, and gem-related fields.
    Structure: fixed binary fields + null-terminated strings (name, description).
    """
    results = {}
    with open(path, 'rb') as f:
        magic, build = parse_wdb_header(f)
        print(f"  itemcache magic={magic} build={build}")
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            item_id, size = struct.unpack('<II', hdr)
            if item_id == 0 and size == 0:
                break
            data = f.read(size)
            if not data:
                break
            if target_ids and item_id not in target_ids:
                continue

            # Parse the fixed fields to find quality and name.
            # WoW 3.3.5a ItemCacheEntry layout (all uint32/int32 unless noted):
            # [0]  classID        [1]  subclassID     [2]  unk0
            # [3]  displayInfoID  [4]  quality        [5]  flags
            # [6]  flags2         [7]  buyprice       [8]  sellprice
            # [9]  inventoryType  [10] allowableClass [11] allowableRace
            # [12] itemLevel      [13] requiredLevel  [14] requiredSkill
            # [15] requiredSkillRank [16] requiredSpell [17] requiredHonorRank
            # [18] requiredCityRank  [19] requiredRepFaction [20] requiredRepValue
            # [21] maxCount       [22] stackCount     [23] containerSlots
            # [24] statsCount     then statsCount pairs (statType, statValue) up to 10
            # After stats: scalingStatDistribution, scalingStatValue
            # 5x damage structs (min float, max float, type uint32) = 5*12 = 60 bytes
            # 7x resistances uint32 = 28 bytes
            # 2x weaponSpeed uint32 = 8 bytes
            # 1x ammo uint32 = 4 bytes
            # 1x rangedModRange float = 4 bytes
            # 5x spells (spellId, trigger, charges, cooldown, category, catCooldown) = 5*24 = 120 bytes
            # bonding uint32
            # Then: null-terminated description string
            # pageText, pageLang, pageMaterial, startQuest, lockID, material,
            # sheath, randomProperty, randomSuffix, block, itemSet, maxDurability,
            # area, map, bagFamily, totemCategory
            # 3x sockets (color, content) = 24 bytes
            # socketBonus, gemProperties, requiredDisenchantSkill
            # armorDamageModifier float, duration int32, itemLimitCategory, holidayId
            # Then: null-terminated name string (at end)

            try:
                pos = 0
                def u32():
                    nonlocal pos
                    v, = struct.unpack_from('<I', data, pos)
                    pos += 4
                    return v
                def i32():
                    nonlocal pos
                    v, = struct.unpack_from('<i', data, pos)
                    pos += 4
                    return v
                def f32():
                    nonlocal pos
                    v, = struct.unpack_from('<f', data, pos)
                    pos += 4
                    return v
                def cstr():
                    nonlocal pos
                    end = data.index(b'\x00', pos)
                    s = data[pos:end].decode('utf-8', errors='replace')
                    pos = end + 1
                    return s

                class_id = u32(); subclass = u32(); unk0 = u32()
                display_id = u32(); quality = u32(); flags = u32()
                flags2 = u32(); buyprice = i32(); sellprice = u32()
                inv_type = u32(); allow_class = i32(); allow_race = i32()
                ilvl = u32(); req_level = u32(); req_skill = u32()
                req_skill_rank = u32(); req_spell = u32(); req_honor = u32()
                req_city = u32(); req_rep_faction = u32(); req_rep_value = u32()
                max_count = i32(); stack_count = i32(); container_slots = u32()
                stats_count = u32()

                stats = []
                for _ in range(min(stats_count, 10)):
                    st = i32(); sv = i32()
                    stats.append((st, sv))

                scaling_stat_dist = u32(); scaling_stat_val = u32()

                # 5 damage structs
                for _ in range(5):
                    f32(); f32(); u32()

                # 7 resistances
                for _ in range(7):
                    u32()

                # 2 weapon speeds
                u32(); u32()
                u32()  # ammo
                f32()  # rangedModRange

                # 5 spells
                for _ in range(5):
                    i32(); u32(); i32(); i32(); u32(); i32()

                bonding = u32()
                description = cstr()
                page_text = u32(); page_lang = u32(); page_mat = u32()
                start_quest = u32(); lock_id = u32(); material = i32()
                sheath = u32(); rand_prop = i32(); rand_suffix = i32()
                block = u32(); item_set = u32(); max_dur = u32()
                area = u32(); map_id = u32(); bag_family = u32()
                totem_cat = u32()

                # 3 sockets
                sockets = []
                for _ in range(3):
                    sc = u32(); ss = u32()
                    sockets.append((sc, ss))

                socket_bonus = u32(); gem_props = u32()
                req_dench = i32()
                f32()  # armorDamageModifier
                i32()  # duration
                u32()  # itemLimitCategory
                u32()  # holidayId

                name = cstr()

                results[item_id] = {
                    'name': name,
                    'quality': quality,
                    'ilvl': ilvl,
                    'inv_type': inv_type,
                    'class_id': class_id,
                    'subclass': subclass,
                    'gem_props': gem_props,
                    'stats': {str(t): v for t, v in stats if v != 0},
                }
            except Exception as e:
                # Try fallback: scan for null-terminated strings near end of data
                strings = []
                i = 0
                while i < len(data):
                    end = data.find(b'\x00', i)
                    if end == -1:
                        break
                    s = data[i:end]
                    try:
                        text = s.decode('utf-8')
                        if len(text) >= 3 and all(32 <= ord(c) < 127 or ord(c) > 127 for c in text):
                            strings.append(text)
                    except Exception:
                        pass
                    i = end + 1
                # The name is typically the last meaningful string
                name = strings[-1] if strings else ''
                results[item_id] = {'name': name, 'quality': 0, 'ilvl': 0, 'error': str(e)}

    return results


print("Parsing itemnamecache.wdb...")
names = parse_itemnamecache(WDB_NAME)
print(f"  Found {len(names)} named items")
target_found = {k: v for k, v in names.items() if k in TARGET_IDS}
print(f"  Target gem IDs found in namecache: {len(target_found)}")
for iid, name in sorted(target_found.items()):
    print(f"    {iid}: {name}")

print()
print("Parsing itemcache.wdb for target gem IDs...")
items = parse_itemcache(WDB_ITEM, TARGET_IDS)
print(f"  Found {len(items)} target items in cache")
print()
for iid, info in sorted(items.items()):
    print(f"  {iid}: q={info['quality']} ilvl={info['ilvl']} inv={info['inv_type']} cls={info['class_id']}/{info['subclass']} name='{info['name']}'")

# Save combined gem lookup
gem_lookup = {}
for iid in TARGET_IDS:
    if iid in items and items[iid]['name']:
        gem_lookup[str(iid)] = items[iid]
    elif iid in names:
        gem_lookup[str(iid)] = {'name': names[iid]}

out = os.path.join(os.path.dirname(__file__), 'armory', 'gem_lookup.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(gem_lookup, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(gem_lookup)} gems to {out}")
