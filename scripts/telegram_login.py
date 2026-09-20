"""Connexion Telegram interactive → écrit TELEGRAM_SESSION dans .env (chmod 600).

    uv run python -m scripts.telegram_login          # code dans l'app Telegram
    uv run python -m scripts.telegram_login --sms    # code par SMS

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
import sys
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


PHONE_RE = re.compile(r"\+?\d{8,15}")


def ask_phone() -> str:
    """Redemande tant que le numéro n'est pas plausible.

    Un numéro vide partait jusqu'ici tel quel vers Telethon, qui plantait sur
    un `TypeError` illisible dix appels plus bas.
    """
    while True:
        raw = input("Numéro au format international (ex. +33612345678) : ")
        phone = re.sub(r"[\s.\-()]", "", raw.strip())
        if PHONE_RE.fullmatch(phone):
            return phone
        print("  Numéro vide ou invalide : indicatif puis chiffres, par exemple +33612345678.")


def sign_in(client, phone: str) -> None:
    """Envoie le code puis connecte. Le code expire vite : ne pas traîner.

    Telegram choisit seul la voie d'envoi : dans l'application s'il existe une
    session active sur le compte, par SMS sinon. Forcer le SMS n'est plus
    possible (`force_sms` est obsolète côté Telethon et sans effet).
    """
    from telethon.errors import (
        FloodWaitError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        PhoneNumberInvalidError,
        SessionPasswordNeededError,
    )

    try:
        sent = client.send_code_request(phone)
    except PhoneNumberInvalidError:
        raise SystemExit(f"Numéro refusé par Telegram : {phone}") from None
    except FloodWaitError as e:
        raise SystemExit(
            f"Trop de tentatives : Telegram impose d'attendre {e.seconds // 60 + 1} minute(s)."
        ) from None

    voie = {"app": "dans l'application Telegram (conversation « Telegram »)",
            "sms": "par SMS"}.get(
        type(sent.type).__name__.replace("SentCodeType", "").lower(),
        f"par {type(sent.type).__name__}",
    )
    print(f"\nCode envoyé {voie}. Il expire en quelques minutes.")

    for essai in range(3):
        code = input("Code reçu : ").strip()
        try:
            client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
            return
        except SessionPasswordNeededError:
            import getpass

            client.sign_in(password=getpass.getpass("Mot de passe (double authentification) : "))
            return
        except PhoneCodeInvalidError:
            print("Code invalide." + (" Dernier essai." if essai == 1 else ""))
        except PhoneCodeExpiredError:
            raise SystemExit(
                "Code expiré. Relance le script et saisis le code dès sa réception."
            ) from None
    raise SystemExit("Trois codes invalides : relance le script.")


def main() -> None:
    if "--sms" in sys.argv:
        print("Note : forcer le SMS n'est plus possible, Telegram choisit la voie d'envoi.\n")
    api_id = settings.telegram_api_id or int(input("TELEGRAM_API_ID : ").strip())
    api_hash = settings.telegram_api_hash or input("TELEGRAM_API_HASH : ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    client.connect()
    try:
        if not client.is_user_authorized():
            sign_in(client, ask_phone())
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
    finally:
        client.disconnect()

    print(f"\n✓ Session écrite dans {ENV_PATH.resolve()} (chmod 600), jamais affichée.")
    print("\nEnsuite, déclare le fil avec la référence repérée ci-dessus :")
    print("  uv run python -m scripts.admin add-feed --name Yoann \\")
    print("      --chat <référence> --owner <ton email>")


if __name__ == "__main__":
    main()
