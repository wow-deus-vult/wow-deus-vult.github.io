import re, requests
from bs4 import BeautifulSoup

POTION_COLUMNS = {
    "Potion of Speed":        "potionOfSpeed",
    "Potion of Wild Magic":   "potionOfWildMagic",
    "Insane Strength Potion": "insaneStrength",
    "Flame Cap":              "flameCap",
    "Destruction Potion":     "destructionPotion",
}

with open('EPGP.lua', encoding='utf-8') as f:
    content = f.read()
pattern = re.compile(
    r'\["time"\]\s*=\s*(\d+).*?\["roster_info"\]\s*=\s*\{(.*?)\},\s*\n\s*\}',
    re.DOTALL
)
snapshots = list(pattern.finditer(content))
latest = max(snapshots, key=lambda m: int(m.group(1)))
members = set(re.findall(r'"([^"]+)",\s*--\s*\[1\]', latest.group(2)))
print(f"Members: {len(members)}")

log_id = '26-06-21--22-00--Denmark--FreedomUA'
url = f"https://uwu-logs.xyz/reports/{log_id}/consumables/"
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

tbody = soup.find('tbody', id='potions-table-body')
print(f"tbody found: {tbody is not None}")

thead = soup.find('thead')
col_indices = {}
for i, th in enumerate(thead.find_all('th')):
    title = th.get('title', '')
    if title in POTION_COLUMNS:
        col_indices[title] = i
        print(f"  col '{title}' at index {i}")

print(f"col_indices: {col_indices}")

players = []
for tr in tbody.find_all('tr'):
    tds = tr.find_all('td')
    player_cell = tr.find('td', class_='player-cell')
    if not player_cell:
        continue
    a = player_cell.find('a')
    if not a:
        continue
    name = a.get_text(strip=True)
    if name not in members:
        continue

    try:
        total = int(tds[1].get_text(strip=True)) if len(tds) > 1 else 0
    except:
        total = 0

    row = {'name': name, 'total': total}
    for potion_name, key in POTION_COLUMNS.items():
        idx = col_indices.get(potion_name)
        val = ''
        if idx is not None and idx < len(tds):
            val = tds[idx].get_text(strip=True)
        try:
            row[key] = int(val)
        except:
            row[key] = 0
    players.append(row)

print(f"\nPlayers found: {len(players)}")
for p in players[:5]:
    print(p)
