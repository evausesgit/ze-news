# CLAUDE.md

Ze News : liens partagés sur Telegram → résumés par Codex → cartes swipables et
recherche, multi-utilisateur. **`ARCHITECTURE.md` fait foi** (schéma, pipeline,
endpoints) ; le garder synchronisé avec le code. Langue du projet : français.

## Commandes

- Tests : `uv run --group dev pytest -q` · Lint : `uv run --group dev ruff check`
- Front : `cd web && npx tsc --noEmit && npx next build`
- Migrations : `uv run alembic revision --autogenerate -m "…"` puis `alembic upgrade head`
  (l'API les joue au démarrage du conteneur).

## Règles

- Codex = **CLI `codex exec`** (pas l'API Claude ni OpenAI), même mécanique que
  x-med (`app/codex_cli.py`). `--search` est une option GLOBALE : avant `exec`.
  Effort et modèle toujours passés explicitement.
- Piège PATH : codex est dans `~/.npm-global/bin`, absent du PATH des process
  lancés par un agent → `CODEX_BIN` en chemin absolu.
- Multi-utilisateur : toute requête sur les liens passe par les fils de
  l'utilisateur (`feed_members`). Ne jamais renvoyer un lien hors de ses fils.
- État de lecture = `link_states` (par utilisateur), jamais sur `links`.
- Labels : liste fermée dans `app/labels.py`, dupliquée pour l'affichage dans
  `web/lib/api.ts` (`LABEL_NAMES`) — modifier les deux.
- `TELEGRAM_SESSION` est un secret de niveau compte : jamais dans le dépôt, les
  logs ou un fichier sur la machine partagée.
