"""cria movimentacoes de materiais

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
Create Date: 2026-07-16 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "movimentacoes_materiais",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("material", sa.String(length=250), nullable=False),
        sa.Column(
            "numero_movimentacao",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=True),
        sa.Column("unidade", sa.String(length=30), nullable=True),
        sa.Column("observacao_carga", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="Em trânsito",
        ),
        sa.Column("recebido_em", sa.DateTime(), nullable=True),
        sa.Column(
            "foto_recebimento",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("latitude_recebimento", sa.Float(), nullable=True),
        sa.Column("longitude_recebimento", sa.Float(), nullable=True),
        sa.Column("precisao_metros", sa.Float(), nullable=True),
        sa.Column("observacao_recebimento", sa.Text(), nullable=True),
        sa.Column("cancelado_em", sa.DateTime(), nullable=True),
        sa.Column("motivo_cancelamento", sa.Text(), nullable=True),
        sa.Column(
            "client_uuid_recebimento",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("diario_bordo_id", sa.Integer(), nullable=False),
        sa.Column("recebido_por_id", sa.Integer(), nullable=True),
        sa.Column("cancelado_por_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["cancelado_por_id"],
            ["usuarios.id"],
        ),
        sa.ForeignKeyConstraint(
            ["diario_bordo_id"],
            ["diarios_bordo.id"],
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
        ),
        sa.ForeignKeyConstraint(
            ["recebido_por_id"],
            ["usuarios.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_uuid_recebimento",
            name="uq_movimentacoes_client_uuid_recebimento",
        ),
        sa.UniqueConstraint(
            "diario_bordo_id",
            name="uq_movimentacao_material_diario",
        ),
    )
    op.create_index(
        "ix_movimentacao_material_empresa_numero",
        "movimentacoes_materiais",
        ["empresa_id", "numero_movimentacao"],
        unique=False,
    )
    op.create_index(
        "ix_movimentacao_material_empresa_status",
        "movimentacoes_materiais",
        ["empresa_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_movimentacoes_materiais_client_uuid_recebimento",
        "movimentacoes_materiais",
        ["client_uuid_recebimento"],
        unique=True,
    )


def downgrade():
    op.drop_index(
        "ix_movimentacoes_materiais_client_uuid_recebimento",
        table_name="movimentacoes_materiais",
    )
    op.drop_index(
        "ix_movimentacao_material_empresa_status",
        table_name="movimentacoes_materiais",
    )
    op.drop_index(
        "ix_movimentacao_material_empresa_numero",
        table_name="movimentacoes_materiais",
    )
    op.drop_table("movimentacoes_materiais")
