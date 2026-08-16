"""
probe_uwu.py — швидка перевірка доступності uwu-logs.xyz перед збирачами.

Якщо сайт лежить, немає сенсу ганяти 7 збирачів крізь сотню 30-секундних
таймаутів (~1.5 год порожньої роботи): виходимо з кодом 1, bat пропускає
рейтинги і одразу переходить до арморі, який від uwu-logs не залежить.
"""
import sys
import time

import requests

from discord_notify import send_dm

sys.stdout.reconfigure(encoding="utf-8")

for attempt in range(2):
    try:
        r = requests.get("https://uwu-logs.xyz", timeout=15)
        print(f"uwu-logs.xyz живий (HTTP {r.status_code})")
        sys.exit(0)
    except Exception as e:
        print(f"  спроба {attempt + 1}: {type(e).__name__}")
        if attempt == 0:
            time.sleep(10)

print("uwu-logs.xyz недоступний — збирачі рейтингів пропущені")
send_dm("**[Probe]** uwu-logs.xyz лежить — рейтинги сьогодні пропущені, "
        "арморі оновлюється як зазвичай")
sys.exit(1)
