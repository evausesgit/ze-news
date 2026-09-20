# Ze News

Les liens que Yoann partage sur Telegram, résumés en une phrase par Codex,
classés par label et thème, à lire en cartes swipables. Détails techniques :
[ARCHITECTURE.md](ARCHITECTURE.md).

- **Fil** : swipe à gauche = suivante (la carte devient « lue », sa couleur
  s'éteint), à droite = précédente, double-clic ou double-tap = ouvre la source.
- **Langue** : anglais par défaut, bascule EN/FR sur chaque carte ou globalement.
- **Recherche** : texte, labels, thèmes, période, lu / non lu / ouvert.

## Mise en route

### 1. Accès Telegram (une fois)

1. Sur https://my.telegram.org → « API development tools » : créer une appli,
   noter `api_id` et `api_hash`.
2. Sur une machine **privée** :
   ```bash
   uv sync
   TELEGRAM_API_ID=… TELEGRAM_API_HASH=… uv run python -m scripts.telegram_login
   ```
   Le script liste tes conversations récentes (pour trouver la référence de
   celle avec Yoann) et affiche `TELEGRAM_SESSION=…`. Coller cette valeur
   directement dans les variables d'environnement du déploiement.

### 2. Connexion Google (Firebase)

Créer un projet Firebase, activer « Authentication → Google », ajouter le
domaine du site dans les domaines autorisés, et récupérer la config web
(`apiKey`, `authDomain`, `projectId`, `appId`) pour les variables
`NEXT_PUBLIC_FIREBASE_*`.

### 3. Déploiement (Coolify, compose)

Variables listées en tête de `docker-compose.yml`. Codex utilise le login
monté depuis `CODEX_HOME_HOST` (même principe que x-med).

### 4. Créer le fil et les membres

```bash
docker compose exec api python -m scripts.admin add-feed --name Yoann --chat @reference_telegram --owner ton.email@gmail.com
docker compose exec api python -m scripts.admin add-member --feed Yoann --email ami@gmail.com
docker compose exec api python -m scripts.admin list
```

Au cycle suivant, le worker remonte tout l'historique de la conversation, puis
Codex résume les liens par lots de 20, les plus récents d'abord.

## Où héberger le worker

`TELEGRAM_SESSION` ouvre **tout** ton compte Telegram, pas seulement la
conversation avec Yoann. Sur une machine où d'autres personnes ont `sudo`, elles
peuvent lire cette variable (`docker inspect`). Recommandation : faire tourner au
moins le service `worker` sur une machine dont tu es seule administratrice.

## Développement

Tout tester en local en une commande (Postgres jetable, API, front avec une
identité simulée) :

```bash
bash scripts/dev_up.sh --demo   # --demo = 6 liens réels résumés par Codex
# → http://127.0.0.1:3010
bash scripts/dev_down.sh        # tout arrêter (la base est supprimée)
```

Avec ton vrai Telegram configuré (cf. § Mise en route) :
`bash scripts/dev_up.sh --telegram` lance en plus un cycle d'ingestion.

```bash
uv sync --group dev
uv run --group dev pytest -q          # tests
uv run --group dev ruff check         # lint
uv run python -m scripts.try_link <url> ["message"]   # essai Codex sur une URL
DATABASE_URL=… uv run python -m scripts.demo_seed moi@example.com  # base de démo

# front, identité simulée (dev uniquement, ignorée en production)
cd web && npm install
ZENEWS_DEV_USER_EMAIL=moi@example.com API_INTERNAL_URL=http://127.0.0.1:8810 npm run dev
```
