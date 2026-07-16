"""conclui diario no recebimento do material

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-07-16 16:00:00.000000
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "f0a1b2c3d4e5"
down_revision = "e9f0a1b2c3d4"
branch_labels = None
depends_on = None


def converter_data_hora(valor):
    if isinstance(valor, datetime):
        return valor

    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor)
        except ValueError:
            return None

    return None


def upgrade():
    conexao = op.get_bind()
    metadata = sa.MetaData()
    diarios = sa.Table(
        "diarios_bordo",
        metadata,
        autoload_with=conexao,
    )
    movimentacoes = sa.Table(
        "movimentacoes_materiais",
        metadata,
        autoload_with=conexao,
    )

    recebidos = conexao.execute(
        sa.select(
            diarios.c.id,
            movimentacoes.c.recebido_em,
        )
        .select_from(
            diarios.join(
                movimentacoes,
                movimentacoes.c.diario_bordo_id == diarios.c.id,
            )
        )
        .where(
            diarios.c.status == "Em andamento",
            movimentacoes.c.status.in_([
                "Recebido",
                "Recebido com ressalva",
            ]),
            movimentacoes.c.recebido_em.is_not(None),
        )
    ).all()

    for diario_id, recebido_em in recebidos:
        momento = converter_data_hora(recebido_em)
        if momento is None:
            continue

        conexao.execute(
            diarios.update()
            .where(diarios.c.id == diario_id)
            .values(
                status="Concluído",
                hora_retorno=momento.time().replace(microsecond=0),
            )
        )


def downgrade():
    # Não reabre diários para evitar alterar viagens concluídas manualmente.
    pass
