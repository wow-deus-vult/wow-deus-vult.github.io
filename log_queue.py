"""
log_queue.py — спільний модуль черги логів для Deus Vult скриптів.

Зберігає стан у data/pending_logs.json:
{
    "pending": ["log_id1", "log_id2", ...],   # ще не оброблені
    "done":    ["log_id3", "log_id4", ...]    # вже оброблені
}

Використання:
    from log_queue import LogQueue
    q = LogQueue("data/pending_logs.json")
    q.add_logs(all_log_ids)          # додає нові, не чіпає вже відомі
    for log_id in q.iter_pending():  # ітерація по черзі
        result = fetch(log_id)
        if result:
            q.mark_done(log_id)      # успіх → видаляємо з черги
        # при помилці — нічого не робимо, лог лишається в pending
"""

import json
import os


QUEUE_FILE = "data/pending_logs.json"


class LogQueue:
    def __init__(self, path=QUEUE_FILE):
        self.path = path
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.pending = data.get("pending", [])
            self.done    = set(data.get("done", []))
        else:
            self.pending = []
            self.done    = set()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({
                "pending": self.pending,
                "done":    sorted(self.done),
            }, f, ensure_ascii=False, indent=2)

    def add_logs(self, log_ids):
        """Додає нові логи в pending (ті що вже є в done або pending — ігноруються)."""
        known = set(self.pending) | self.done
        added = 0
        for log_id in log_ids:
            if log_id not in known:
                self.pending.append(log_id)
                known.add(log_id)
                added += 1
        if added:
            self._save()
        print(f"  Черга: {len(self.pending)} очікують, {len(self.done)} вже оброблено, +{added} нових")
        return added

    def mark_done(self, log_id):
        """Позначає лог як оброблений — видаляє з pending, додає в done."""
        if log_id in self.pending:
            self.pending.remove(log_id)
        self.done.add(log_id)
        self._save()

    def iter_pending(self):
        """Ітерує по копії pending (бо під час ітерації список змінюється)."""
        return list(self.pending)

    @property
    def pending_count(self):
        return len(self.pending)

    @property
    def done_count(self):
        return len(self.done)
