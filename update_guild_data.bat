@echo off
cd /d D:\Uwu-parcer-DEUS

set LOGFILE=D:\Uwu-parcer-DEUS\update_log.txt

python log_writer.py START

echo [1/7] DPS collector...
python fetch_guild_data.py >> %LOGFILE% 2>&1

echo [2/7] Heal collector...
python fetch_heal_data.py >> %LOGFILE% 2>&1

echo [3/7] Total Damage collector (builds duplicate_logs_map)...
python fetch_total_damage.py >> %LOGFILE% 2>&1

echo [4/7] Potion collector...
python fetch_potion_data.py >> %LOGFILE% 2>&1

echo [5/7] Guild Stats collector...
python fetch_guild_stats.py >> %LOGFILE% 2>&1

echo [6/7] Raid Stats collector...
python fetch_raid_stats.py >> %LOGFILE% 2>&1

echo [7/7] Tank Rating collector...
python fetch_tank_data.py >> %LOGFILE% 2>&1

echo [8/8] Armory (GearScore/Examiner + wowhead + DBC)...
python parse_armory.py >> %LOGFILE% 2>&1
python update_enchants_cache.py >> %LOGFILE% 2>&1
python parse_armory.py --export >> %LOGFILE% 2>&1

echo Validating JSON files...
python validate_json.py >> %LOGFILE% 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo VALIDATION FAILED - skipping git push >> %LOGFILE%
    python log_writer.py DONE
    exit /b 1
)

echo Git push...
git fetch origin master >> %LOGFILE% 2>&1
git reset --mixed origin/master >> %LOGFILE% 2>&1
git add data/guild-data.json data/guild-heal.json data/guild-tank.json data/potion-stats.json data/total-damage.json data/guild-stats.json data/raid-stats.json data/duplicate_logs_map.json data/pending_total_damage.json data/pending_potion.json data/pending_guild_stats.json data/pending_raid_stats.json data/pending_heal_rating.json data/pending_tank_rating.json data/potion-stats_cache.json data/total-damage_cache.json data/guild-stats_cache.json data/raid-stats_cache.json data/guild-heal_cache.json data/guild-tank_cache.json armory/armory_data.json armory/items_cache.json armory/enchants_cache.json armory/gs_best.json >> %LOGFILE% 2>&1
git diff --staged --quiet || git commit -m "Auto-update guild data %date%" >> %LOGFILE% 2>&1
git push origin master >> %LOGFILE% 2>&1

python log_writer.py DONE
