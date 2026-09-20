"""Configuration par variables d'environnement (cf. .env.example)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./zenews.db"

    # Jeton partagé entre le proxy Next et l'API. S'il est défini, toute requête
    # qui ne le porte pas est refusée : l'API ne fait confiance aux en-têtes
    # d'identité (x-user-*) que s'ils viennent du proxy.
    internal_api_token: str = ""

    # --- Telegram (compte utilisateur via Telethon, pas un bot) ---
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    # StringSession Telethon : donne un accès COMPLET au compte Telegram.
    # Secret, jamais dans le dépôt ni sur une machine partagée.
    telegram_session: str = ""

    # --- Codex CLI (résumé + label) ---
    codex_bin: str = "codex"
    codex_model: str = "gpt-5.6-luna"
    # Effort PINNÉ : sinon codex hérite du config.toml ambiant (« high » en dev).
    codex_reasoning: str = "low"
    codex_timeout: int = 300
    # Recherche web native de codex, pour les liens qu'on n'a pas pu lire nous-mêmes.
    codex_web_search: bool = True

    # --- Worker ---
    poll_interval_seconds: int = 600
    enrich_batch_size: int = 20
    enrich_max_attempts: int = 3
    fetch_timeout_seconds: float = 15.0


settings = Settings()
