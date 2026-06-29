"""
epgp_parser.py — спільний парсер EPGP.lua для всіх fetch-скриптів Deus Vult.

ПРОБЛЕМА, яку вирішує:
  EPGP-аддон зберігає ростери КІЛЬКОХ гільдій у profiles:
    - "Deus Vult"  — наша
    - "Deus VuIt"  — наш двійник (велика латинська I замість малої l)
    - "Blue Oyster Bar", "End point", ... — ЧУЖІ гільдії
  Старий парсер брав один снапшот за max(time) і ловив лише блоки,
  де ["time"] стоїть перед ["roster_info"]. Це давало два роди помилок:
    1) зникали наші гравці з блоку-двійника "Deus VuIt" (Cutecut, Palm, Magnum...);
    2) у деяких випадках підхоплювалися ЧУЖІ гравці (Limko, Konstan з "End point"),
       бо прив'язка снапшоту до гільдії плуталась.

РІШЕННЯ:
  Прив'язуємося не до time, а до НАЗВИ ГІЛЬДІЇ-ПРОФІЛЮ.
  Беремо гравців ТІЛЬКИ з блоків нашої гільдії (Deus Vult / Deus VuIt),
  об'єднуємо їх. Чужі профілі ігноруються повністю.

Структура EPGP (важливі відступи):
  <4 таби>["Назва гільдії"] = {
      ["log"] = { ... },
      ["snapshot"] = {
          ["time"] = ...,
          <6 табів>["roster_info"] = {
              { "Ім'я", -- [1]
                "CLASS", -- [2]
                "", -- [3]
              }, ...
"""

import re

KNOWN_CLASSES = {
    "DEATHKNIGHT", "DRUID", "HUNTER", "MAGE", "PALADIN",
    "PRIEST", "ROGUE", "SHAMAN", "WARLOCK", "WARRIOR",
}

# Назви профілів НАШОЇ гільдії (обидва написання: l та латинська I).
OUR_GUILD_NAMES = {"Deus Vult", "Deus VuIt"}

# Гравці яких немає в EPGP але вони рейдять з нами (тріали, гості тощо).
# Додавай вручну: "Ім'яГравця",
EXTRA_MEMBERS = {
    # "Пак'тайтус",
    # "Sanya",
    # "Palpatine"
    # "Slicendice"
}


def parse_epgp_members(path="EPGP.lua", our_guilds=OUR_GUILD_NAMES, verbose=True):
    """
    Повертає set імен гравців з ростерів нашої гільдії (обидва написання).
    Чужі гільдії (Blue Oyster Bar, End point тощо) ігноруються.
    """
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    # профілі гільдій — рівно 4 таби на початку рядка: ^\t\t\t\t["Назва"] = {
    profile_marks = [
        (m.start(), m.group(1))
        for m in re.finditer(r'(?m)^\t{4}\["([^"]+)"\]\s*=\s*\{', content)
    ]
    roster_starts = [m.start() for m in re.finditer(r'\["roster_info"\]\s*=\s*\{', content)]

    pat_player = re.compile(
        r'"([^"]+)",\s*--\s*\[1\]\s*\r?\n\s*"([A-Z ]+)",\s*--\s*\[2\]'
    )

    def guild_of(roster_pos):
        """Назва гільдії-профілю, що стоїть найближче ПЕРЕД цим roster_info."""
        g = None
        for pos, name in profile_marks:
            if pos < roster_pos:
                g = name
            else:
                break
        return g

    names = set()
    taken_blocks = 0
    for i, rs in enumerate(roster_starts):
        rend = roster_starts[i + 1] if i + 1 < len(roster_starts) else len(content)
        if guild_of(rs) not in our_guilds:
            continue
        taken_blocks += 1
        segment = content[rs:rend]
        for pm in pat_player.finditer(segment):
            cls = pm.group(2).strip().replace(" ", "")
            if cls in KNOWN_CLASSES:
                names.add(pm.group(1))

    # Додаємо ручний список
    names.update(EXTRA_MEMBERS)

    if verbose:
        extra = len(EXTRA_MEMBERS)
        print(f"   EPGP: {len(names)} гравців (з {taken_blocks} ростер-блоків нашої гільдії{f' + {extra} вручну' if extra else ''})")
    return names


if __name__ == "__main__":
    members = parse_epgp_members()
    print(f"\nУсього: {len(members)}")
    for who in ("Мараксус", "Cutecut", "Palm", "Magnum", "Limko", "Konstan"):
        print(f"  {who}: {who in members}")
