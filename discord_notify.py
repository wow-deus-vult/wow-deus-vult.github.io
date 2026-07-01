"""
discord_notify.py — відправка DM через Discord бота.
Токен читається з .env (DISCORD_BOT_TOKEN=...).
"""

import os
import requests

_USER_ID = "421251618412036106"


def _get_token() -> str:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DISCORD_BOT_TOKEN="):
                    return line.split("=", 1)[1].strip()
    return os.environ.get("DISCORD_BOT_TOKEN", "")


def send_dm(message: str) -> bool:
    token = _get_token()
    if not token:
        print("  [discord] .env не знайдено або токен відсутній")
        return False

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(
            "https://discord.com/api/v10/users/@me/channels",
            headers=headers,
            json={"recipient_id": _USER_ID},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  [discord] не вдалось відкрити DM: {r.status_code} {r.text}")
            return False

        channel_id = r.json()["id"]

        r2 = requests.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            json={"content": message},
            timeout=10,
        )
        if r2.status_code == 200:
            print("  [discord] сповіщення надіслано")
            return True
        print(f"  [discord] помилка: {r2.status_code} {r2.text}")
        return False

    except Exception as e:
        print(f"  [discord] виняток: {e}")
        return False
