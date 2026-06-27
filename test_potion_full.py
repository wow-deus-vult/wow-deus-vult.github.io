import json, re, time, requests
from bs4 import BeautifulSoup

BASE_URL = "https://uwu-logs.xyz"
HEADERS = {"User-Agent": "Mozilla/5.0"}

POTION_COLUMNS = {
    "Potion of Speed":        "potionOfSpeed",
    "Potion of Wild Magic":   "potionOfWildMagic",
    "Insane Strength Potion": "insaneStrength",
    "Flame Cap":              "flameCap",
    "Destruction Potion":     "destructionPotion",
}

# Завантажуємо members з EPGP
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

# Тестові логи
test_logs = [
    "26-06-21--22-00--Denmark--FreedomUA",
    "26-06-22--23-10--Калабаня--FreedomUA",
    "26-06-23--21-41--Sweden--FreedomUA",
]

raids = []
for log_id in test_logs:
    url = f"{BASE_URL}/reports/{log_id}/consumables/"
    print(f"\n{log_id}...")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        tbody = soup.find('tbody', id='potions-table-body')
        thead = soup.find('thead')
        if not tbody or not thead:
            print("  немає таблиці")
            continue

        col_indices = {}
        for i, th in enumerate(thead.find_all('th')):
            title = th.get('title', '')
            if title in POTION_COLUMNS:
                col_indices[title] = i

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
                try:
                    row[key] = int(tds[idx].get_text(strip=True)) if idx and idx < len(tds) else 0
                except:
                    row[key] = 0
            players.append(row)

        parts = log_id.split("--")
        date_parts = parts[0].split("-")
        date_str = f"20{date_parts[0]}-{date_parts[1]}-{date_parts[2]}"
        uploader = parts[-2] if len(parts) >= 2 else ""

        raids.append({
            "raidUrl": f"{BASE_URL}/reports/{log_id}/",
            "consumablesUrl": url,
            "date": date_str,
            "uploader": uploader,
            "players": sorted(players, key=lambda p: p["total"], reverse=True),
        })
        print(f"  ✓ {len(players)} гравців")
        for p in players[:3]:
            print(f"    {p['name']}: total={p['total']}, speed={p['potionOfSpeed']}, wild={p['potionOfWildMagic']}")

    except Exception as e:
        print(f"  Помилка: {e}")
    time.sleep(0.5)

print(f"\nВсього рейдів: {len(raids)}")
with open('data/potion-stats-test.json', 'w', encoding='utf-8') as f:
    json.dump(raids, f, ensure_ascii=False, indent=2)
print("Збережено в data/potion-stats-test.json")
