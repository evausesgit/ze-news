"""expéditeurs anonymisés : sender_name ne garde que les initiales

Revision ID: 7c1e2a9f4b10
Revises: d64370c64165
Create Date: 2026-09-22 10:00:00.000000

"""
import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7c1e2a9f4b10'
down_revision: str | Sequence[str] | None = 'd64370c64165'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _initials(name: str) -> str:
    # Copie figée de app.telegram_ingest.initials : une migration ne doit pas
    # changer de comportement si le code applicatif évolue.
    if name == "moi":
        return name
    return "".join(w[0].upper() for w in re.findall(r"[^\W\d_]+", name))[:3]


def upgrade() -> None:
    """Remplace les noms complets déjà stockés par leurs initiales."""
    conn = op.get_bind()
    shares = sa.table("shares", sa.column("sender_name", sa.String))
    names = conn.execute(sa.select(shares.c.sender_name).distinct()).scalars().all()
    for name in names:
        new = _initials(name or "")
        if new != name:
            conn.execute(
                shares.update().where(shares.c.sender_name == name).values(sender_name=new)
            )


def downgrade() -> None:
    """Irréversible : les noms complets ne sont pas conservés."""
