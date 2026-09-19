"""Taxonomie fermée des labels : Codex doit choisir UN label dans cette liste.

Garder la liste courte et stable : c'est le filtre principal du dashboard. Les
nuances plus fines passent par les thèmes libres (`link_themes`).
Pour ajouter un label : l'ajouter ici (le schéma Codex et l'API suivent).
"""

LABELS: dict[str, dict[str, str]] = {
    "AI": {"en": "AI", "fr": "IA"},
    "TECH": {"en": "Tech", "fr": "Tech"},
    "POLITICS": {"en": "Politics", "fr": "Politique"},
    "NEWS": {"en": "News", "fr": "Actu"},
    "ECONOMY": {"en": "Economy", "fr": "Économie"},
    "STATS": {"en": "Stats", "fr": "Stats"},
    "SCIENCE": {"en": "Science", "fr": "Science"},
    "HEALTH": {"en": "Health", "fr": "Santé"},
    "CULTURE": {"en": "Culture", "fr": "Culture"},
    "OTHER": {"en": "Other", "fr": "Autre"},
}

LABEL_CODES: list[str] = list(LABELS)
