"""Vincula motorista ao veículo.

Revision ID: 01e30df23aa6
Revises: 67228cd462ee
"""

from alembic import op
import sqlalchemy as sa


revision = "01e30df23aa6"
down_revision = "67228cd462ee"
branch_labels = None
depends_on = None


NOME_CHAVE_ESTRANGEIRA = (
    "fk_motoristas_veiculo_id_veiculos"
)

CONVENCAO_NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": (
        "fk_%(table_name)s_"
        "%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
    "pk": "pk_%(table_name)s",
}


def coluna_existe(inspector, tabela, coluna):
    colunas = inspector.get_columns(tabela)

    return any(
        item["name"] == coluna
        for item in colunas
    )


def chave_estrangeira_existe(inspector):
    chaves = inspector.get_foreign_keys(
        "motoristas"
    )

    for chave in chaves:
        colunas = (
            chave.get("constrained_columns")
            or []
        )

        tabela_referenciada = chave.get(
            "referred_table"
        )

        if (
            "veiculo_id" in colunas
            and tabela_referenciada == "veiculos"
        ):
            return True

    return False


def upgrade():
    conexao = op.get_bind()
    inspector = sa.inspect(conexao)

    if not coluna_existe(
        inspector,
        "motoristas",
        "veiculo_id",
    ):
        with op.batch_alter_table(
            "motoristas"
        ) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "veiculo_id",
                    sa.Integer(),
                    nullable=True,
                )
            )

    inspector = sa.inspect(conexao)

    if not chave_estrangeira_existe(
        inspector
    ):
        with op.batch_alter_table(
            "motoristas",
            naming_convention=CONVENCAO_NOMES,
        ) as batch_op:
            batch_op.create_foreign_key(
                NOME_CHAVE_ESTRANGEIRA,
                "veiculos",
                ["veiculo_id"],
                ["id"],
            )


def downgrade():
    conexao = op.get_bind()
    inspector = sa.inspect(conexao)

    if not coluna_existe(
        inspector,
        "motoristas",
        "veiculo_id",
    ):
        return

    possui_chave = chave_estrangeira_existe(
        inspector
    )

    with op.batch_alter_table(
        "motoristas",
        naming_convention=CONVENCAO_NOMES,
    ) as batch_op:

        if possui_chave:
            batch_op.drop_constraint(
                NOME_CHAVE_ESTRANGEIRA,
                type_="foreignkey",
            )

        batch_op.drop_column(
            "veiculo_id"
        )