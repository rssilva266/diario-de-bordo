from datetime import datetime

from extensions import db


class ConfiguracaoEmpresa(db.Model):
    __tablename__ = "configuracoes_empresa"

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            name="uq_configuracoes_empresa_empresa_id",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    email = db.Column(
        db.String(150),
        nullable=True,
    )

    telefone = db.Column(
        db.String(20),
        nullable=True,
    )

    whatsapp = db.Column(
        db.String(20),
        nullable=True,
    )

    cep = db.Column(
        db.String(9),
        nullable=True,
    )

    logradouro = db.Column(
        db.String(180),
        nullable=True,
    )

    numero = db.Column(
        db.String(20),
        nullable=True,
    )

    complemento = db.Column(
        db.String(120),
        nullable=True,
    )

    bairro = db.Column(
        db.String(100),
        nullable=True,
    )

    cidade = db.Column(
        db.String(100),
        nullable=True,
    )

    estado = db.Column(
        db.String(2),
        nullable=True,
    )

    responsavel = db.Column(
        db.String(150),
        nullable=True,
    )

    logo = db.Column(
        db.String(500),
        nullable=True,
    )

    exibir_logo_relatorios = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    rodape_relatorios = db.Column(
        db.String(300),
        nullable=True,
    )

    criada_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    atualizada_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
    )

    empresa = db.relationship(
        "Empresa",
        backref=db.backref(
            "configuracao",
            uselist=False,
        ),
    )