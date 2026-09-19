"""Connexion Telegram interactive → affiche la StringSession à mettre dans TELEGRAM_SESSION.

    TELEGRAM_API_ID=... TELEGRAM_API_HASH=... uv run python -m scripts.telegram_login

API id/hash : https://my.telegram.org → « API development tools ».

⚠️ La chaîne affichée donne un accès COMPLET à ton compte Telegram. À lancer sur
une machine privée (pas la machine partagée), à coller directement dans les
variables d'environnement Coolify, jamais dans un fichier du dépôt.
"""

from __future__ import annotations

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from app.config import settings


def main() -> None:
    api_id = settings.telegram_api_id or int(input("TELEGRAM_API_ID : "))
    api_hash = settings.telegram_api_hash or input("TELEGRAM_API_HASH : ").strip()
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = client.get_me()
        print(f"\nConnectée en tant que {me.first_name} (@{me.username}).")
        print("\nConversations récentes (pour choisir le fil) :")
        for d in client.iter_dialogs(limit=15):
            ref = f"@{d.entity.username}" if getattr(d.entity, "username", None) else d.id
            print(f"  {d.name!s:40} → {ref}")
        print("\nTELEGRAM_SESSION=" + client.session.save())


if __name__ == "__main__":
    main()
