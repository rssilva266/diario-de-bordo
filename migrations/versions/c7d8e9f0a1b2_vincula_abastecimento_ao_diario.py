"""vincula abastecimento ao diario de bordo

Revision ID: c7d8e9f0a1b2
Revises: a9f3c1d2e4b5
Create Date: 2026-07-14 11:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = "c7d8e9f0a1b2"
down_revision = "a9f3c1d2e4b5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("abastecimentos") as batch_op:
        batch_op.add_column(
            sa.Column(
                "foto_odometro",
                sa.String(length=500),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "diario_bordo_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_abastecimentos_diario_bordo_id_diarios_bordo",
            "diarios_bordo",
            ["diario_bordo_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_abastecimentos_diario_bordo_id",
            ["diario_bordo_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("abastecimentos") as batch_op:
        batch_op.drop_index(
            "ix_abastecimentos_diario_bordo_id"
        )
        batch_op.drop_constraint(
            "fk_abastecimentos_diario_bordo_id_diarios_bordo",
            type_="foreignkey",
        )
        batch_op.drop_column("diario_bordo_id")
        batch_op.drop_column("foto_odometro")
