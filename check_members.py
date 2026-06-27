import re, requests
from bs4 import BeautifulSoup

with open('EPGP.lua', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(
    r'\["time"\]\s*=\s*(\d+).*?\["roster_info"\]\s*=\s*\{(.*?)\},\s*\n\s*\}',
    re.DOTALL
)
snapshots = list(pattern.finditer(content))
latest = max(snapshots, key=lambda m: int(m.group(1)))
members = sorted(set(re.findall(r'"([^"]+)",\s*--\s*\[1\]', latest.group(2))))
print(f"Гравців в EPGP: {len(members)}")
for n in members:
    print(n)

print("\n--- Порівняння з логом ---")
r = requests.get(
    'https://uwu-logs.xyz/reports/26-06-21--22-00--Denmark--FreedomUA/consumables/',
    headers={'User-Agent': 'Mozilla/5.0'}
)
soup = BeautifulSoup(r.text, 'html.parser')
tbody = soup.find('tbody', id='potions-table-body')
log_players = []
for tr in tbody.find_all('tr'):
    a = tr.find('a')
    if a:
        log_players.append(a.get_text(strip=True))

print(f"Гравців в логу: {len(log_players)}")
matched = [p for p in log_players if p in members]
print(f"Наших в логу: {len(matched)}")
print("Наші:", matched)
not_matched = [p for p in log_players if p not in members]
print("Не наші / твіни:", not_matched)
