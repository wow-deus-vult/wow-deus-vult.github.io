"""
merge_wdb_items.py — override items_cache with server-true stats from itemcache.wdb.

Freedom x5 customizes items (e.g. 47436 turned into a tank cloak with negative
stats) — wowhead knows nothing about that. The client's itemcache.wdb stores
ITEM_QUERY_SINGLE_RESPONSE exactly as the server sent it: stats (int32, can be
negative), armor, sockets, socket bonus, RU name. WDB wins over wowhead.
"""
import struct, json, os, sys, glob
sys.stdout.reconfigure(encoding='utf-8')

ITEMS_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "armory", "items_cache.json")

from wow_paths import wdb_itemcaches, active_install
# порядок: активна інсталяція останньою, ruRU після enUS — щоб її записи перемагали
WDB_PATHS = sorted(wdb_itemcaches(),
                   key=lambda p: (p.startswith(active_install()), "ruRU" in p))

# ItemMod enum (3.3.5) → our stat keys
STAT_MAP = {
    3: 'agi', 4: 'str', 5: 'int', 6: 'spi', 7: 'sta',
    12: 'def', 13: 'dodge', 14: 'parry', 15: 'block',
    16: 'hit', 17: 'hit', 18: 'hit',
    19: 'crit', 20: 'crit', 21: 'crit',
    28: 'haste', 29: 'haste', 30: 'haste',
    31: 'hit', 32: 'crit', 35: 'res', 36: 'haste', 37: 'exp',
    38: 'ap', 39: 'ap', 41: 'sp', 42: 'sp', 43: 'mp5',
    44: 'arp', 45: 'sp',
}
SOCKET_COLOR = {1: 'meta', 2: 'red', 4: 'yellow', 8: 'blue'}


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0
    def u32(self):
        v = struct.unpack_from('<I', self.d, self.p)[0]; self.p += 4; return v
    def i32(self):
        v = struct.unpack_from('<i', self.d, self.p)[0]; self.p += 4; return v
    def f32(self):
        v = struct.unpack_from('<f', self.d, self.p)[0]; self.p += 4; return v
    def cstr(self):
        e = self.d.find(b'\x00', self.p)
        s = self.d[self.p:e].decode('utf-8', errors='replace')
        self.p = e + 1
        return s


def parse_record(data):
    """Parse one ITEM_QUERY_SINGLE_RESPONSE payload → dict."""
    r = Reader(data)
    out = {}
    r.u32()                      # class
    r.u32()                      # subclass
    r.i32()                      # sound override subclass
    out['name'] = r.cstr()       # name1 (RU on ruRU client)
    r.cstr(); r.cstr(); r.cstr() # name2..4
    out['displayId'] = r.u32()
    out['quality'] = r.u32()
    r.u32(); r.u32()             # flags, flags2
    r.u32(); r.u32()             # buy, sell price
    r.u32()                      # inventory type
    r.u32(); r.u32()             # allowable class, race
    out['ilvl'] = r.u32()
    r.u32()                      # required level
    for _ in range(7): r.u32()   # reqSkill, reqSkillRank, reqSpell, honor, city, repFaction, repRank
    r.u32(); r.u32(); r.u32()    # maxCount, stackable, containerSlots
    stats_count = r.u32()
    if stats_count > 32:
        raise ValueError("bad statsCount")
    stats = {}
    for _ in range(stats_count):
        st, val = r.u32(), r.i32()
        key = STAT_MAP.get(st)
        if key:
            stats[key] = stats.get(key, 0) + val
    out['stats'] = stats
    r.u32(); r.u32()             # scalingStatDistribution, scalingStatValue
    for _ in range(2):           # 2 damage entries
        r.f32(); r.f32(); r.u32()
    out['armor'] = r.i32()
    for _ in range(6): r.i32()   # resistances
    r.u32()                      # delay
    r.u32()                      # ammo type
    r.f32()                      # ranged mod range
    for _ in range(5):           # 5 spell slots
        r.u32(); r.u32(); r.i32(); r.i32(); r.u32(); r.u32()
    r.u32()                      # bonding
    r.cstr()                     # description
    for _ in range(9): r.u32()   # pageText, languageId, pageMaterial, startQuest,
                                 # lockId, material, sheath, randomProperty, randomSuffix
    r.u32()                      # block value
    r.u32(); r.u32()             # itemSet, maxDurability
    r.u32(); r.u32()             # area, map
    r.u32(); r.u32()             # bagFamily, totemCategory
    sockets = []
    for _ in range(3):
        color, _content = r.u32(), r.u32()
        if color in SOCKET_COLOR:
            sockets.append(SOCKET_COLOR[color])
    out['sockets'] = sockets
    out['socketBonusId'] = r.u32()
    return out


def parse_wdb(path):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw[:4] != b'BDIW':
        print(f"  {path}: not a BDIW file, skip")
        return {}
    pos = 24                      # header: magic, build, locale, unk, version, unk
    items = {}
    n_bad = 0
    while pos + 8 <= len(raw):
        entry, length = struct.unpack_from('<II', raw, pos)
        pos += 8
        if entry == 0 and length == 0:
            break
        if length == 0 or pos + length > len(raw):
            break
        try:
            items[entry] = parse_record(raw[pos:pos + length])
        except Exception:
            n_bad += 1
        pos += length
    print(f"  {os.path.basename(os.path.dirname(os.path.dirname(path)))}: "
          f"{len(items)} items parsed, {n_bad} bad records")
    return items


def load_display_icons():
    """displayId → icon name from ItemDisplayInfo.dbc (for items wowhead lacks)."""
    try:
        import mpyq
    except ImportError:
        return {}
    from wow_paths import data_dir as _wow_data_dir
    DATA_DIR = _wow_data_dir()
    for rel in (r"enus\patch-enus-2.mpq", r"enus\patch-enus.mpq", r"enus\locale-enus.mpq",
                r"patch-2.mpq", r"patch.mpq", r"common-2.mpq", r"common.mpq"):
        path = os.path.join(DATA_DIR, rel)
        if not os.path.exists(path):
            continue
        try:
            arc = mpyq.MPQArchive(path)
            d = arc.read_file("DBFilesClient\\ItemDisplayInfo.dbc".encode())
            if not d or d[:4] != b'WDBC':
                continue
            rc, fc, rs, sbs = struct.unpack_from('<4I', d, 4)
            sb = d[20 + rc * rs: 20 + rc * rs + sbs]
            icons = {}
            for i in range(rc):
                rec = struct.unpack_from(f'<{fc}I', d, 20 + i * rs)
                off = rec[5]
                if off and off < len(sb):
                    e = sb.find(b'\x00', off)
                    icons[rec[0]] = sb[off:e].decode('ascii', errors='replace').lower()
            print(f"  ItemDisplayInfo: {len(icons)} icons from {rel}")
            return icons
        except Exception:
            continue
    return {}


def main():
    with open(ITEMS_CACHE, encoding='utf-8') as f:
        cache = json.load(f)

    # enchant names for socket bonus resolution
    ench_path = os.path.join(os.path.dirname(ITEMS_CACHE), "enchants_cache.json")
    ench = {}
    if os.path.exists(ench_path):
        with open(ench_path, encoding='utf-8') as f:
            ench = json.load(f)
    from armory_stats import enchant_stats

    wdb_all = {}
    for p in WDB_PATHS:
        for iid, rec in parse_wdb(p).items():
            wdb_all[iid] = rec    # later installs overwrite; all should agree

    icons = load_display_icons()

    overridden = 0
    for iid_str, entry in cache.items():
        rec = wdb_all.get(int(iid_str))
        if not rec:
            continue
        # items wowhead doesn't know (or knows under a placeholder): take WDB identity
        if not entry.get('name') or entry.get('name', '').startswith('Item '):
            entry['name'] = rec['name']
            entry['quality'] = rec.get('quality', 1)
            entry['icon'] = icons.get(rec.get('displayId'), entry.get('icon') or 'inv_misc_questionmark')
        changed = (entry.get('stats') != rec['stats'] or
                   entry.get('armor', 0) != (rec['armor'] or 0) or
                   entry.get('sockets', []) != rec['sockets'])
        entry['stats'] = rec['stats']
        if rec['armor']:
            entry['armor'] = rec['armor']
        else:
            entry.pop('armor', None)
        if rec['sockets']:
            entry['sockets'] = rec['sockets']
        else:
            entry.pop('sockets', None)
        sb = rec.get('socketBonusId')
        if sb:
            sb_en = ench.get(str(sb), {})
            sb_stats = enchant_stats(sb_en.get('name_en') or sb_en.get('name', ''))
            if sb_stats:
                entry['socketBonus'] = sb_stats
        if rec.get('ilvl'):
            entry['ilvl'] = rec['ilvl']
        if rec.get('name'):
            entry['name_ru'] = rec['name']
        entry['wdb'] = True
        if changed:
            overridden += 1

    with open(ITEMS_CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    total_wdb = sum(1 for v in cache.values() if v.get('wdb'))
    print(f"WDB truth applied: {total_wdb} items matched, {overridden} had different data than wowhead")


if __name__ == '__main__':
    main()
