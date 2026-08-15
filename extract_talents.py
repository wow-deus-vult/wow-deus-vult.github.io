"""
extract_talents.py — build armory/talents.json from client DBCs.

Talent trees per class (tier/col grid, ranks, names EN/RU, icons) so the
armory can render in-game-like trees from GS_SpecGear TalentRanks strings.
The rank-string order is GetTalentInfo order = talents sorted by (tier, col).
"""
import mpyq, struct, os, sys, json, glob
sys.stdout.reconfigure(encoding='utf-8')

from wow_paths import data_dir as _wow_data_dir
DATA = _wow_data_dir()
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

# description column (ruRU canonical=178; detect to be safe) + basepoints (EN file, cols 86-88)
def detect_desc_col(d, spell_id, probe):
    rc, fc, rs, sbs = struct.unpack_from('<4I', d, 4)
    sb = d[20 + rc * rs: 20 + rc * rs + sbs]
    for rec in dbc_iter(d):
        if rec[0] != spell_id:
            continue
        for col, v in enumerate(rec):
            if 0 < v < sbs and probe in sb[v:sb.find(b'\x00', v)]:
                return col
    return None

DESC_RU_COL = detect_desc_col(spell_ru, 49664, 'урон от магии льда'.encode('utf-8')) if spell_ru else None
DESC_EN_COL = detect_desc_col(spell_en, 49664, b'Increases your frost')
BP_COLS = (86, 87, 88)   # EffectBasePoints1-3 in this (shifted) EN layout
print(f"Desc cols: RU={DESC_RU_COL} EN={DESC_EN_COL}")

AURA_COLS = (101, 102, 103)   # EffectApplyAuraName1-3 in this layout
AURA_WEAPON_CRIT, AURA_SPELL_CRIT = 52, 57

spell_names_en, spell_icons, spell_bp, spell_desc_en, spell_auras = {}, {}, {}, {}, {}
for rec in dbc_iter(spell_en):
    sid = rec[0]
    spell_names_en[sid] = rec[NAME_EN_COL]
    spell_icons[sid] = rec[ICON_COL]
    bp = tuple(struct.unpack('<i', struct.pack('<I', rec[c]))[0] for c in BP_COLS)
    spell_bp[sid] = bp
    spell_auras[sid] = [(rec[AURA_COLS[e]], bp[e] + 1) for e in range(3) if rec[AURA_COLS[e]]]
    if DESC_EN_COL:
        spell_desc_en[sid] = rec[DESC_EN_COL]
spell_names_ru, spell_desc_ru = {}, {}
if spell_ru and NAME_RU_COL:
    for rec in dbc_iter(spell_ru):
        spell_names_ru[rec[0]] = rec[NAME_RU_COL]
        if DESC_RU_COL:
            spell_desc_ru[rec[0]] = rec[DESC_RU_COL]

import re as _re

def render_desc(sid):
    """Substitute $s1 / $49665s2 / ${...} macros with numbers."""
    off = spell_desc_ru.get(sid) or spell_desc_en.get(sid, 0)
    src = spell_ru if spell_desc_ru.get(sid) else spell_en
    raw = dbc_str(src, off)
    if not raw:
        return ''

    def sub_val(m):
        ref = int(m.group(1)) if m.group(1) else sid
        idx = int(m.group(3)) - 1
        bp = spell_bp.get(ref, (0, 0, 0))
        v = abs(bp[idx] + 1) if idx < 3 else 0
        return str(v)

    txt = _re.sub(r'\$(\d+)?([sSoOmM])([1-3])', sub_val, raw)
    # simple ${a/b} / ${a*b} arithmetic left after substitution
    def sub_math(m):
        try:
            return str(round(eval(m.group(1), {"__builtins__": {}}), 1)).rstrip('0').rstrip('.')
        except Exception:
            return '?'
    txt = _re.sub(r'\$\{([\d\s\.\+\-\*\/]+)\}', sub_math, txt)
    txt = _re.sub(r'\$[a-zA-Z]\d?', '?', txt)   # leftover macros ($d etc.)
    return txt

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
    entry = {
        "tier": tier, "col": col, "max": len(ranks),
        "name": dbc_str(spell_en, spell_names_en.get(sp1, 0)),
        "name_ru": dbc_str(spell_ru, spell_names_ru.get(sp1, 0)) if spell_ru else "",
        "icon": icons.get(spell_icons.get(sp1, 0), "inv_misc_questionmark"),
        "desc": [render_desc(r) for r in ranks],
    }
    # panel crit bonuses straight from spell auras (52 = weapon crit %, 57 = spell crit %)
    critW = [sum(v for a, v in spell_auras.get(r, []) if a == AURA_WEAPON_CRIT) for r in ranks]
    critS = [sum(v for a, v in spell_auras.get(r, []) if a == AURA_SPELL_CRIT) for r in ranks]
    if any(critW): entry["critW"] = critW
    if any(critS): entry["critS"] = critS
    by_tab.setdefault(tab_id, []).append(entry)

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
