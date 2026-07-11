"""
extract_talents.py — build armory/talents.json from client DBCs.

Talent trees per class (tier/col grid, ranks, names EN/RU, icons) so the
armory can render in-game-like trees from GS_SpecGear TalentRanks strings.
The rank-string order is GetTalentInfo order = talents sorted by (tier, col).
"""
import mpyq, struct, os, sys, json, glob
sys.stdout.reconfigure(encoding='utf-8')

DATA = glob.glob("D:/world of warcraft 3.3.5a hd*3/Data")[0]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "armory", "talents.json")

CLASS_MASK = {1: "WA", 2: "PA", 4: "HU", 8: "RO", 16: "PR",
              32: "DK", 64: "SH", 128: "MA", 256: "WK", 1024: "DR"}


def load_dbc(rels, name):
    for rel in rels:
        p = os.path.join(DATA, rel)
        if not os.path.exists(p):
            continue
        try:
            arc = mpyq.MPQArchive(p)
            d = arc.read_file(("DBFilesClient\\" + name).encode())
            if d and d[:4] == b'WDBC':
                return d
        except Exception:
            pass
    return None


def dbc_iter(d):
    rc, fc, rs, sbs = struct.unpack_from('<4I', d, 4)
    sb = d[20 + rc * rs: 20 + rc * rs + sbs]
    for i in range(rc):
        yield struct.unpack_from(f'<{fc}I', d, 20 + i * rs)


def dbc_str(d, off):
    rc, fc, rs, sbs = struct.unpack_from('<4I', d, 4)
    sb = d[20 + rc * rs: 20 + rc * rs + sbs]
    if not off or off >= len(sb):
        return ''
    e = sb.find(b'\x00', off)
    return sb[off:e].decode('utf-8', errors='replace')


EN = [r"enus\patch-enus-2.mpq", r"enus\patch-enus.mpq", r"enus\locale-enus.mpq"]
RU = [r"ruru\patch-ruru-3.mpq", r"ruru\patch-ruru-2.mpq", r"ruru\patch-ruru.mpq", r"ruru\locale-ruru.mpq"]

# ── TalentTab: id → (nameEN, nameRU, classCode, orderIndex) ───────────────────
tab_en = load_dbc(EN, "TalentTab.dbc")
tab_ru = load_dbc(RU, "TalentTab.dbc")
ru_tab_names = {}
if tab_ru:
    for rec in dbc_iter(tab_ru):
        ru_tab_names[rec[0]] = dbc_str(tab_ru, rec[9])   # ruRU locale column

tabs = {}
for rec in dbc_iter(tab_en):
    tab_id, name_off = rec[0], rec[1]
    cls_mask, order = rec[20], rec[22]
    cls = CLASS_MASK.get(cls_mask)
    if not cls:
        continue                                  # pet talent tabs etc.
    tabs[tab_id] = {
        "cls": cls, "order": order,
        "name_en": dbc_str(tab_en, name_off),
        "name_ru": ru_tab_names.get(tab_id, ""),
    }
print(f"TalentTab: {len(tabs)} class tabs")

# ── Spell names + icons ───────────────────────────────────────────────────────
spell_en = load_dbc(EN, "Spell.dbc")
spell_ru = load_dbc(RU, "Spell.dbc")
icon_dbc = load_dbc(EN, "SpellIcon.dbc")

icons = {}
for rec in dbc_iter(icon_dbc):
    path = dbc_str(icon_dbc, rec[1])
    icons[rec[0]] = path.rsplit('\\', 1)[-1].lower()
print(f"SpellIcon: {len(icons)} icons")

# Spell.dbc 3.3.5 (234+ fields): SpellIconID=133, name enUS=136 … ruRU=144?
# We verified name col empirically before (142 worked for one layout) — detect:
def detect_name_col(d, probe=b'Veteran of the Third War'):
    rc, fc, rs, sbs = struct.unpack_from('<4I', d, 4)
    sb = d[20 + rc * rs: 20 + rc * rs + sbs]
    off = sb.find(probe)
    if off == -1:
        return None
    for rec in dbc_iter(d):
        if off in rec:
            return rec.index(off)
    return None

NAME_EN_COL = detect_name_col(spell_en) or 136
NAME_RU_COL = None
if spell_ru:
    NAME_RU_COL = detect_name_col(spell_ru, 'Ветеран Третьей войны'.encode('utf-8'))
print(f"Spell name cols: EN={NAME_EN_COL} RU={NAME_RU_COL}")

# icon col: probe a known spell/icon pair — detect by checking values map into icons
def detect_icon_col(d):
    recs = list(dbc_iter(d))[:400]
    fc = len(recs[0])
    best, best_hits = None, 0
    for col in range(120, 140):
        hits = sum(1 for r in recs if r[col] in icons and r[col] != 0)
        if hits > best_hits:
            best, best_hits = col, hits
    return best

ICON_COL = detect_icon_col(spell_en)
print(f"Spell icon col: {ICON_COL}")

spell_names_en, spell_icons = {}, {}
for rec in dbc_iter(spell_en):
    spell_names_en[rec[0]] = rec[NAME_EN_COL]
    spell_icons[rec[0]] = rec[ICON_COL]
spell_names_ru = {}
if spell_ru and NAME_RU_COL:
    for rec in dbc_iter(spell_ru):
        spell_names_ru[rec[0]] = rec[NAME_RU_COL]

# ── Talent.dbc: id, tab, tier, col, rankSpells[9] ────────────────────────────
talent_dbc = load_dbc(EN, "Talent.dbc")
by_tab = {}
for rec in dbc_iter(talent_dbc):
    tid, tab_id, tier, col = rec[0], rec[1], rec[2], rec[3]
    if tab_id not in tabs:
        continue
    ranks = [r for r in rec[4:13] if r]
    if not ranks:
        continue
    sp1 = ranks[0]
    by_tab.setdefault(tab_id, []).append({
        "tier": tier, "col": col, "max": len(ranks),
        "name": dbc_str(spell_en, spell_names_en.get(sp1, 0)),
        "name_ru": dbc_str(spell_ru, spell_names_ru.get(sp1, 0)) if spell_ru else "",
        "icon": icons.get(spell_icons.get(sp1, 0), "inv_misc_questionmark"),
    })

# GetTalentInfo enumerates sorted by (tier, col)
out = {}
for tab_id, tinfo in tabs.items():
    tlist = sorted(by_tab.get(tab_id, []), key=lambda t: (t["tier"], t["col"]))
    out.setdefault(tinfo["cls"], [None, None, None])[tinfo["order"]] = {
        "name": tinfo["name_ru"] or tinfo["name_en"],
        "name_en": tinfo["name_en"],
        "talents": tlist,
    }

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
size = os.path.getsize(OUT) / 1024
print(f"Saved {OUT} ({size:.0f} KB)")
for cls, tabs3 in sorted(out.items()):
    print(f"  {cls}: " + " | ".join(f"{t['name_en']}({len(t['talents'])})" if t else "?" for t in tabs3))
