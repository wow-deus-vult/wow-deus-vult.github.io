"""
watchdog.py -- перевіряє чи запустився регламент сьогодні.
Запускати о 12:00 через Task Scheduler.
Якщо хоча б один output файл не оновлювався сьогодні -- шле DM.
"""

import os
from datetime import date, datetime
from discord_notify import send_dm

BASE = os.path.dirname(os.path.abspath(__file__))

SCRIPTS = {
    "Heal":         "data/guild-heal.json",
    "Tank":         "data/guild-tank.json",
    "Total Damage": "data/total-damage.json",
    "Potion":       "data/potion-stats.json",
}


def check():
    today = date.today()
    failed = []
    ok = []

    for name, rel_path in SCRIPTS.items():
        path = os.path.join(BASE, rel_path)
        if not os.path.exists(path):
            failed.append(f"{name} — файл відсутній")
            continue

        mtime = datetime.fromtimestamp(os.path.getmtime(path)).date()
        if mtime < today:
            failed.append(f"{name} — останнє оновлення {mtime}")
        else:
            ok.append(name)

    if failed:
        lines = ["**[Watchdog] Регламент НЕ запустився!**", ""]
        lines += [f"❌ {f}" for f in failed]
        if ok:
            lines += [""] + [f"✅ {s}" for s in ok]
        send_dm("\n".join(lines))
    else:
        print("Watchdog: всі скрипти відпрацювали сьогодні, все OK")


if __name__ == "__main__":
    check()
