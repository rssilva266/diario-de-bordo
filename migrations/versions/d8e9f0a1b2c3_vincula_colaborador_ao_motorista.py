"""vincula colaborador diretamente ao motorista

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-07-15 09:00:00
"""
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def somente_digitos(valor):
    return "".join(
        caractere
        for caractere in str(valor or "")
        if caractere.isdigit()
    )


def normalizar_nome(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    sem_acentos = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.casefold().split())


def upgrade():
    with op.batch_alter_table("colaboradores") as batch_op:
        batch_op.add_column(
            sa.Column("motorista_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_colaboradores_motorista_id_motoristas",
            "motoristas",
            ["motorista_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_colaboradores_motorista_id",
            ["motorista_id"],
        )

    conexao = op.get_bind()
    colaboradores = conexao.execute(sa.text(
        "SELECT id, empresa_id, nome, cpf FROM colaboradores"
    )).mappings().all()
    motoristas = conexao.execute(sa.text(
        "SELECT id, empresa_id, nome, cpf FROM motoristas"
    )).mappings().all()

    motoristas_usados = set()

    for colaborador in colaboradores:
        candidatos_empresa = [
            motorista
            for motorista in motoristas
            if motorista["empresa_id"] == colaborador["empresa_id"]
            and motorista["id"] not in motoristas_usados
        ]

        cpf = somente_digitos(colaborador["cpf"])
        candidatos = []

        if cpf:
            candidatos = [
                motorista
                for motorista in candidatos_empresa
                if somente_digitos(motorista["cpf"]) == cpf
            ]

        if not candidatos:
            nome = normalizar_nome(colaborador["nome"])
            candidatos = [
                motorista
                for motorista in candidatos_empresa
                if nome and normalizar_nome(motorista["nome"]) == nome
            ]

        if len(candidatos) != 1:
            continue

        motorista_id = candidatos[0]["id"]
        conexao.execute(
            sa.text(
                "UPDATE colaboradores "
                "SET motorista_id = :motorista_id "
                "WHERE id = :colaborador_id"
            ),
            {
                "motorista_id": motorista_id,
                "colaborador_id": colaborador["id"],
            },
        )
        motoristas_usados.add(motorista_id)


def downgrade():
    with op.batch_alter_table("colaboradores") as batch_op:
        batch_op.drop_constraint(
            "uq_colaboradores_motorista_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_colaboradores_motorista_id_motoristas",
            type_="foreignkey",
        )
        batch_op.drop_column("motorista_id")
