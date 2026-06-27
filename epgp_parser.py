"""
epgp_parser.py — спільний парсер EPGP.lua для всіх fetch-скриптів Deus Vult.

Чому окремий модуль:
  Старі локальні parse_epgp_members у скриптах:
    1) брали лише ОДИН снапшот;
    2) ловили тільки блоки, де ["time"] стоїть ПЕРЕД ["roster_info"].
  У реальному EPGP.lua виявилось:
    * назва гільдії існує у двох варіантах: "Deus Vult" і "Deus VuIt"
      (друга — через велику латинську I замість малої l), гравці рознесені по обох;
    * у блоці-двійнику порядок полів зворотний (roster_info ПЕРЕД time),
      тож старий регекс його не бачив → зникали гравці (Cutecut, Palm, Magnum...).
  Цей парсер бере гравців з УСІХ свіжих снапшотів (вікно RECENT_WINDOW_DAYS днів
  від найновішого), будь-який порядок полів, будь-яка назва гільдії.
  Старі торішні снапшоти відсікаються автоматично.

Виклик сумісний з обома старими стилями:
  parse_epgp_members()                 # шлях за замовч. "EPGP.lua"
  parse_epgp_members(EPGP_FILE)        # явний шлях (як у guild_data / heal_data)
"""

import re
from datetime import datetime

KNOWN_CLASSES = {
    "DEATHKNIGHT", "DRUID", "HUNTER", "MAGE", "PALADIN",
    "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR",
}

# Беремо снапшоти не старіші за стільки днів від найновішого.
RECENT_WINDOW_DAYS = 30


def parse_epgp_members(path="EPGP.lua", recent_window_days=RECENT_WINDOW_DAYS, verbose=True):
    """
    Повертає set імен гравців з усіх свіжих снапшотів EPGP.lua.
    Ловить обидва порядки полів (time до/після roster_info)
    і обидві назви гільдії (Deus Vult / Deus VuIt).
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    times = [int(m.group(1)) for m in re.finditer(r'\["time"\]\s*=\s*(\d+)', content)]
    if not times:
        if verbose:
            print("   EPGP: жодного снапшоту не знайдено")
        return set()
    newest = max(times)
    cutoff = newest - recent_window_days * 86400

    roster_starts = [m.start() for m in re.finditer(r'\["roster_info"\]\s*=\s*\{', content)]

    pat_player = re.compile(
        r'"([^"]+)",\s*--\s*\[1\]\s*\r?\n\s*"([A-Z ]+)",\s*--\s*\[2\]'
    )

    names = set()
    for i, rstart in enumerate(roster_starts):
        rend = roster_starts[i + 1] if i + 1 < len(roster_starts) else len(content)
        segment = content[rstart:rend]

        tmatch = re.search(r'\["time"\]\s*=\s*(\d+)', segment)
        seg_time = int(tmatch.group(1)) if tmatch else None
        if seg_time is None or seg_time < cutoff:
            continue

        for pm in pat_player.finditer(segment):
            cls = pm.group(2).strip().replace(" ", "")
            if cls in KNOWN_CLASSES:
                names.add(pm.group(1))

    if verbose:
        dt = datetime.fromtimestamp(newest).strftime('%Y-%m-%d %H:%M')
        print(f"   EPGP: {len(names)} гравців (свіжі снапшоти до {dt}, вікно {recent_window_days} дн.)")
    return names


if __name__ == "__main__":
    members = parse_epgp_members()
    print(f"\nУсього: {len(members)}")
    for who in ("Мараксус", "Cutecut", "Palm", "Magnum"):
        print(f"  {who}: {who in members}")
