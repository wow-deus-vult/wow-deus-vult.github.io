"""
wow_paths.py — автовизначення шляхів до WoW-інсталяцій.

Інсталяції переїжджають і перейменовуються ("– 3" → "hd 4 _бойовий"), тому
жодних жорстких шляхів: активна інсталяція = та, де GearScore.lua свіжіший.
"""
import glob
import os

_GS_REL = os.path.join("WTF", "Account", "*", "SavedVariables", "GearScore.lua")


def all_installs():
    """Всі корені інсталяцій WoW на D: (де є WTF з GearScore)."""
    roots = set()
    for p in glob.glob(os.path.join(r"D:\\", "world of warcraft*", _GS_REL)):
        root = p
        for _ in range(5):
            root = os.path.dirname(root)
        roots.add(root)
    return sorted(roots)


def active_install():
    """Корінь активної інсталяції — з найсвіжішим GearScore.lua."""
    best_root, best_mtime = None, -1.0
    for root in all_installs():
        for p in glob.glob(os.path.join(root, _GS_REL)):
            m = os.path.getmtime(p)
            if m > best_mtime:
                best_root, best_mtime = root, m
    if best_root is None:
        raise RuntimeError("Не знайдено жодної WoW-інсталяції з GearScore.lua")
    return best_root


def data_dir():
    return os.path.join(active_install(), "Data")


def examiner_lua():
    """Examiner.lua активної інсталяції (може не існувати — це ок)."""
    hits = glob.glob(os.path.join(active_install(), "WTF", "Account", "*",
                                  "SavedVariables", "Examiner.lua"))
    return hits[0] if hits else os.path.join(active_install(), "WTF",
                                             "Examiner.lua.missing")


def gearscore_luas():
    """Всі GearScore.lua всіх інсталяцій (мердж по даті захищає від старих)."""
    return [p for p in glob.glob(os.path.join(r"D:\\", "world of warcraft*", _GS_REL))
            if "копія" not in p.lower()]


def wdb_itemcaches():
    """itemcache.wdb всіх інсталяцій (обидві локалі)."""
    return [p for p in glob.glob(os.path.join(r"D:\\", "world of warcraft*",
                                              "Cache", "WDB", "*", "itemcache.wdb"))
            if "копія" not in p.lower()]
