"""Connexion Telegram interactive → écrit TELEGRAM_SESSION dans .env (chmod 600).

    uv run python -m scripts.telegram_login

Demande l'api_id / api_hash (https://my.telegram.org → « API development
tools »), puis le numéro de téléphone, le code reçu dans Telegram et, le cas
échéant, le mot de passe de la double authentification.

La session n'est JAMAIS affichée : elle donne un accès COMPLET au compte
Telegram (toutes les conversations), et un terminal garde son historique. Elle
est écrite dans .env en lecture seule pour toi (chmod 600) — root peut toujours
la lire, donc sur une machine partagée, préférer un serveur privé.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from app.config import settings

ENV_PATH = Path(".env")


def upsert_env(path: Path, values: dict[str, str]) -> None:
    """Écrit ou remplace des clés dans un .env, en gardant le reste du fichier."""
    lines = path.read_text().splitlines() if path.exists() else []
    for key, value in values.items():
        pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n")
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 600


def main() -> None:
    api_id = settings.telegram_api_id or int(input("TELEGRAM_API_ID : ").strip())
    api_hash = settings.telegram_api_hash or input("TELEGRAM_API_HASH : ").strip()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        me = client.get_me()
        print(f"\nConnectée en tant que {me.first_name} (@{me.username}).\n")
        print("Conversations récentes — repère celle de Yoann :\n")
        for i, d in enumerate(client.iter_dialogs(limit=20), start=1):
            ref = f"@{d.entity.username}" if getattr(d.entity, "username", None) else d.id
            kind = "groupe" if d.is_group else "canal" if d.is_channel else "privé"
            print(f"  {i:2}. {d.name!s:35.35} {kind:7} → {ref}")
        upsert_env(
            ENV_PATH,
            {
                "TELEGRAM_API_ID": str(api_id),
                "TELEGRAM_API_HASH": api_hash,
                "TELEGRAM_SESSION": client.session.save(),
            },
        )

    print(f"\n✓ Session écrite dans {ENV_PATH.resolve()} (chmod 600), jamais affichée.")
    print("\nEnsuite, déclare le fil avec la référence repérée ci-dessus :")
    print("  uv run python -m scripts.admin add-feed --name Yoann \\")
    print("      --chat <référence> --owner <ton email>")


if __name__ == "__main__":
    main()
