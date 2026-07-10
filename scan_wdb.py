"""
Scan WoW 3.3.5a WDB itemcache as a hash table.
Item records appear at hash-computed offsets, not sequentially.
Pattern: 8 bytes | itemID (4 bytes) | unk (4 bytes) | quality (4 bytes) | ... | name (null-term string)
"""
import struct, sys, json, os
sys.stdout.reconfigure(encoding='utf-8')

WDB = r"D:\world of warcraft 3.3.5a hd – 3\Cache\WDB\ruRU\itemcache.wdb"

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

with open(WDB, 'rb') as f:
    raw = f.read()

print(f"File size: {len(raw):,} bytes")

# Structure observed: at each hit of target_id as uint32 LE,
# the record is at offset-8 with layout:
#   [8 bytes context] [4: item_id] [4: unk1] [4: quality] [4: unk2] [4: allowable_class] [name string]
# Let's verify by scanning all TARGET_IDs

results = {}
quality_names = {0:'poor', 1:'common', 2:'uncommon', 3:'rare', 4:'epic', 5:'legendary', 6:'artifact', 7:'heirloom'}

for gid in sorted(TARGET_IDS):
    needle = struct.pack('<I', gid)
    pos = 0
    found = []
    while True:
        idx = raw.find(needle, pos)
        if idx == -1: break
        pos = idx + 1

        # Try to interpret as an item record
        # The item ID seems to appear at idx, preceded by 8 bytes
        # Layout at idx-8: [8 ctx] [item_id@idx] [4 unk1] [4 quality] [4 unk2] [4 class_mask] [name]
        rec_start = idx  # item id is at idx
        if rec_start + 24 >= len(raw):
            continue

        unk1 = struct.unpack_from('<I', raw, rec_start+4)[0]
        quality = struct.unpack_from('<I', raw, rec_start+8)[0]
        unk2 = struct.unpack_from('<I', raw, rec_start+12)[0]
        class_mask = struct.unpack_from('<i', raw, rec_start+16)[0]

        # Name starts at rec_start+20
        name_start = rec_start + 20
        null_pos = raw.find(b'\x00', name_start)
        if null_pos == -1 or null_pos - name_start > 200:
            continue

        name_bytes = raw[name_start:null_pos]
        try:
            name = name_bytes.decode('utf-8')
        except:
            try:
                name = name_bytes.decode('cp1251')
            except:
                name = repr(name_bytes)

        if len(name) < 2:
            continue
        # Filter: name should be printable text
        if not all(ord(c) >= 32 for c in name if c != '\n'):
            continue

        found.append({
            'offset': idx,
            'name': name,
            'quality': quality,
            'ilvl_maybe': unk1,
            'unk2': unk2,
            'class_mask': class_mask,
        })

    if found:
        # Pick the most likely gem entry (quality 2-5, name looks like gem)
        best = found[0]
        for f in found:
            if 2 <= f['quality'] <= 5:
                best = f
                break
        print(f"  {gid}: quality={best['quality']}({quality_names.get(best['quality'],'?')}) ilvl?={best['ilvl_maybe']} name='{best['name']}'")
        results[str(gid)] = {'name': best['name'], 'quality': best['quality']}
    else:
        print(f"  {gid}: NOT FOUND")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'armory', 'gem_lookup.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(results)} gems -> {out}")
