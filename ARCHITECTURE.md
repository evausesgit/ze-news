# Ze News — architecture

Les liens partagés dans une conversation Telegram (au départ : Yoann → Eva)
deviennent une base de connaissances : chaque lien est lu, résumé en une phrase
(EN + FR) par **Codex**, classé sous un **label** et des **thèmes**, puis
présenté en cartes swipables et cherchables. Multi-utilisateur dès la v1.

## Vue d'ensemble

```
Telegram (compte utilisateur)                         navigateur
      │ Telethon, toutes les 10 min                       │  Google (Firebase Auth)
      ▼                                                   ▼
┌──────────── worker ─────────────┐           ┌────── web (Next 16) ──────┐
│ 1. ingestion : nouveaux messages │           │ proxy.ts : vérifie le JWT │
│    → URLs → links + shares       │           │ Firebase, pose x-user-*   │
│ 2. enrichissement : lecture      │           │ + x-internal-token        │
│    (fxtwitter / HTML) → codex    │           │ /  : fil de cartes        │
│    exec → résumé, label, thèmes  │           │ /recherche : filtres      │
└───────────────┬──────────────────┘           └────────────┬──────────────┘
                │                                           │ /api/* (rewrite)
                ▼                                           ▼
          ┌──────────── PostgreSQL 16 ◄──────── api (FastAPI) ┐
          └───────────────────────────────────────────────────┘
```

Quatre services dans `docker-compose.yml` : `db`, `api`, `worker`, `web`.
Seul `web` est exposé.

## Modèle de données (`app/models.py`)

| Table | Rôle |
|---|---|
| `users` | Compte Google (firebase_uid, email), langue par défaut des cartes (`en`) |
| `feeds` | Une conversation Telegram surveillée + curseur `last_message_id` |
| `feed_members` | Qui voit quel fil (`owner` / `member`) |
| `links` | Le lien, dédoublonné par `canonical_url`, avec résumé EN/FR, label, statut (`pending`, `done`, `failed`, `dormant`) |
| `link_themes` | Thèmes libres (minuscules, anglais), 1 à 4 par lien |
| `shares` | Chaque apparition d'un lien dans un fil : message, expéditeur, date |
| `link_states` | État PAR utilisateur : `seen_at` (swipé) et `opened_at` (double-clic) |

Principe : le résumé est une connaissance **partagée** (calculée une fois),
l'état de lecture est **personnel**. Un utilisateur ne voit que les liens des
fils dont il est membre. Un même tweet partagé via twitter.com, x.com ou
fxtwitter.com = un seul `link`.

## Pipeline

1. **Ingestion** (`app/telegram_ingest.py`) : Telethon en compte utilisateur
   (un bot ne peut pas lire une conversation privée). Lit les messages après
   `last_message_id` ; au premier passage, tout l'historique. URLs = entités
   Telegram (liens cachés inclus) + aperçu de lien + regex de secours.
2. **Lecture** (`app/fetch.py`) : tweets via l'API publique **fxtwitter**
   (texte, auteur, date, tweet cité, sans clé) ; pages web via httpx + extraction
   légère (og:title, description, paragraphes).
3. **Codex** (`app/codex_cli.py`, `app/enrich.py`) : `codex exec` avec
   `--output-schema` (JSON imposé), prompt sur stdin, sandbox read-only,
   éphémère. Si la lecture a échoué (paywall, anti-bot), `--search` active la
   recherche web de Codex. Modèle `gpt-5.6-luna`, effort `low` (≈ 7-16 s par
   lien). 3 tentatives, puis `failed`.
4. Les liens en attente sont traités **du plus récemment partagé au plus
   ancien**, par lots de 20 : les nouveautés arrivent vite même pendant le
   rattrapage de l'historique. Les résumés demandés explicitement passent
   devant (`links.requested_at`).
5. **Mise en sommeil** : un lien dont le dernier partage date de plus de
   `ENRICH_MAX_AGE_DAYS` jours (180 par défaut) passe en `dormant` au lieu
   d'être résumé d'office — l'historique de Yoann compte des milliers de liens.
   Un nouveau partage récent le réveille. Depuis la recherche, « Résumer ce
   lien » le remet en tête de file (`POST /links/{id}/summarize`).

Labels (taxonomie fermée, `app/labels.py`) : AI, TECH, POLITICS, NEWS, ECONOMY,
STATS, SCIENCE, HEALTH, CULTURE, OTHER.

## API (`app/api/`)

| Méthode | Route | Rôle |
|---|---|---|
| GET/PUT | `/me` | Profil, fils accessibles, langue par défaut |
| GET | `/links` | Liste : `label` (OU), `theme` (ET), `q` (mots en ET), `date_from`/`date_to` (date de partage), `read` (all/unread/seen/opened), `include_dormant`, `offset`/`limit` |
| GET | `/links/{id}` | Un lien |
| POST | `/links/{id}/seen` | Marque vu (garde la 1re date) |
| POST | `/links/{id}/opened` | Marque ouvert (et vu) |
| DELETE | `/links/{id}/state` | Remet en non lu |
| POST | `/links/{id}/summarize` | Demande le résumé d'un lien en sommeil (tête de file) |
| GET | `/facets` | Compteurs par label, thèmes fréquents, total / non lus / en attente / en sommeil |

## Sécurité

- L'identité vient **uniquement** du proxy Next, qui vérifie le jeton Firebase
  et écrase les en-têtes `x-user-*`. L'API exige en plus `x-internal-token`
  (= `INTERNAL_API_TOKEN`) : un appel direct est refusé.
- `ZENEWS_ALLOWED_EMAILS` restreint l'accès à une liste de comptes Google.
- `TELEGRAM_SESSION` donne un **accès complet au compte Telegram** (toutes les
  conversations). Voir « Où héberger le worker » dans le README.
- Le contenu des pages est une donnée non fiable : le prompt le balise comme
  tel, et Codex tourne en sandbox read-only, sans session persistée.

## Tests

`uv run --group dev pytest -q` (SQLite en mémoire). Pour rejouer sur Postgres :
`TEST_DATABASE_URL=postgresql+psycopg://…/base_jetable` (la base est vidée).
