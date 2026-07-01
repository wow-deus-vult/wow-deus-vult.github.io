"""
validate_json.py — перевірка всіх data/*.json перед git push.
Запускається автоматично з update_guild_data.bat після збирачів.
Якщо хоч один файл пошкоджений або порожній — виходить з кодом 1,
і git push не відбувається.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

DATA_DIR = "data"

# Файли які ОБОВ'ЯЗКОВО мають бути валідними і непорожніми
REQUIRED = {
    "guild-data.json":    lambda d: len(d.get("rows", [])) > 0,
    "guild-heal.json":    lambda d: len(d.get("rows", [])) > 0,
    "guild-tank.json":    lambda d: len(d.get("rows", [])) > 0,
    "potion-stats.json":  lambda d: len(d.get("honorBoard", [])) > 0,
    "total-damage.json":  lambda d: len(d.get("allTime", {}).get("rows", [])) > 0,
    "guild-stats.json":   lambda d: d.get("icc_raids", 0) > 0,
    "raid-stats.json":    lambda d: d.get("totalRaids", 0) > 0,
}

errors = []
warnings = []

for filename, check_fn in REQUIRED.items():
    path = os.path.join(DATA_DIR, filename)

    # Файл існує?
    if not os.path.exists(path):
        errors.append(f"MISSING: {filename}")
        continue

    # Файл не порожній?
    if os.path.getsize(path) == 0:
        errors.append(f"EMPTY: {filename}")
        continue

    # Валідний JSON?
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"INVALID JSON: {filename} — {e}")
        continue

    # Перевірка що дані непорожні
    if not check_fn(data):
        errors.append(f"EMPTY DATA: {filename} — дані порожні або відсутні")
        continue

    # Перевірка свіжості (якщо є lastUpdated або updated)
    updated_str = data.get("lastUpdated") or data.get("updated")
    if updated_str:
        try:
            if "T" in str(updated_str):
                updated = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            else:
                updated = datetime.fromisoformat(updated_str).replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
            if age_hours > 48:
                warnings.append(f"STALE ({age_hours:.0f}h): {filename}")
        except Exception:
            pass

    print(f"OK: {filename}")

print()

if warnings:
    for w in warnings:
        print(f"WARN: {w}")
    print()

if errors:
    print("=" * 50)
    print("VALIDATION FAILED — git push скасовано!")
    print("=" * 50)
    for e in errors:
        print(f"  ERROR: {e}")
    sys.exit(1)
else:
    print("Validation passed — всі файли валідні.")
    sys.exit(0)
