"""
dedup_helper.py — спільний хелпер дедуплікації для всіх fetch-скриптів.

Джерело істини: data/duplicate_logs_map.json — будується скриптом
fetch_total_damage.py (там є повний список гравців per_player).

Формат: {"дублікат_log_id": "канонічний_log_id", ...}

Інші скрипти (tank, heal, potion, raid_stats, guild_stats) викликають
is_duplicate_log(log_id) щоб пропустити обробку дублікатних логів —
вони все одно вже якісно покриті канонічним логом з тієї ж дати.

ВАЖЛИВО: запускай fetch_total_damage.py ПЕРШИМ у регламенті,
щоб мапа дублікатів була актуальною для решти скриптів.
"""

import json
import os

DUPLICATE_MAP_PATH = "data/duplicate_logs_map.json"


def load_duplicate_map():
    """Повертає dict {дублікат_log_id: канонічний_log_id}."""
    if not os.path.exists(DUPLICATE_MAP_PATH):
        return {}
    with open(DUPLICATE_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def is_duplicate_log(log_id, dup_map=None):
    """True якщо цей log_id — відомий дублікат іншого (канонічного) логу."""
    if dup_map is None:
        dup_map = load_duplicate_map()
    return log_id in dup_map


if __name__ == "__main__":
    m = load_duplicate_map()
    print(f"Дублікатів у мапі: {len(m)}")
    for dup, canon in list(m.items())[:10]:
        print(f"  {dup}  -->  {canon}")
