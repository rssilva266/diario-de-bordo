"""adiciona ponto eletronico

Revision ID: a9f3c1d2e4b5
Revises: 0055a231c0e9
Create Date: 2026-07-11 22:55:00
"""
from alembic import op
import sqlalchemy as sa


revision = "a9f3c1d2e4b5"
down_revision = "0055a231c0e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "locais_trabalho",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("endereco", sa.String(length=250), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("raio_metros", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("empresa_id", "nome", name="uq_local_trabalho_empresa_nome"),
    )

    op.create_table(
        "colaboradores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("matricula", sa.String(length=50), nullable=False),
        sa.Column("cpf", sa.String(length=14), nullable=True),
        sa.Column("funcao", sa.String(length=100), nullable=True),
        sa.Column("telefone", sa.String(length=30), nullable=True),
        sa.Column("jornada_diaria_minutos", sa.Integer(), nullable=False, server_default="480"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("local_trabalho_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["local_trabalho_id"], ["locais_trabalho.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id"),
        sa.UniqueConstraint("empresa_id", "matricula", name="uq_colaborador_empresa_matricula"),
    )

    op.create_table(
        "ponto_marcacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_uuid", sa.String(length=80), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("capturado_em", sa.DateTime(), nullable=False),
        sa.Column("recebido_em", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("precisao_metros", sa.Float(), nullable=True),
        sa.Column("distancia_local_metros", sa.Float(), nullable=True),
        sa.Column("dentro_geocerca", sa.Boolean(), nullable=True),
        sa.Column("foto_path", sa.String(length=500), nullable=False),
        sa.Column("dispositivo_id", sa.String(length=200), nullable=True),
        sa.Column("dispositivo_info", sa.String(length=300), nullable=True),
        sa.Column("ip_origem", sa.String(length=80), nullable=True),
        sa.Column("status_sincronizacao", sa.String(length=30), nullable=False, server_default="Sincronizado"),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("colaborador_id", sa.Integer(), nullable=False),
        sa.Column("local_trabalho_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["colaborador_id"], ["colaboradores.id"]),
        sa.ForeignKeyConstraint(["local_trabalho_id"], ["locais_trabalho.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ponto_marcacoes_client_uuid", "ponto_marcacoes", ["client_uuid"], unique=True)


def downgrade():
    op.drop_index("ix_ponto_marcacoes_client_uuid", table_name="ponto_marcacoes")
    op.drop_table("ponto_marcacoes")
    op.drop_table("colaboradores")
    op.drop_table("locais_trabalho")
