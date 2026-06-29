import sys
from datetime import datetime

logfile = r"D:\Uwu-parcer-DEUS\update_log.txt"
msg = sys.argv[1] if len(sys.argv) > 1 else ""

with open(logfile, "a", encoding="utf-8") as f:
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    if msg == "START":
        f.write(f"\n========================================\n")
        f.write(f"{now} - START\n")
        f.write(f"========================================\n")
    elif msg == "DONE":
        f.write(f"{now} - DONE\n")
