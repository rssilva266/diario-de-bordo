from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class Plano(db.Model):
    __tablename__ = "planos"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    nome = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
    )

    limite_veiculos = db.Column(
        db.Integer,
        nullable=False,
    )

    valor_mensal_minimo = db.Column(
        db.Numeric(10, 2),
        nullable=True,
    )

    valor_mensal_maximo = db.Column(
        db.Numeric(10, 2),
        nullable=True,
    )

    preco_sob_consulta = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_ocr = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_indicadores_avancados = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_ranking = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_alertas = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_api = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_backup_diario = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_multiempresa = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_aplicativo = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_ia = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_integracoes = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    possui_suporte_prioritario = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    empresas = db.relationship(
        "Empresa",
        back_populates="plano",
        lazy=True,
    )


class Empresa(db.Model):
    __tablename__ = "empresas"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    razao_social = db.Column(
        db.String(150),
        nullable=False,
    )

    nome_fantasia = db.Column(
        db.String(150),
        nullable=True,
    )

    cnpj = db.Column(
        db.String(18),
        unique=True,
        nullable=True,
    )

    ativa = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    criada_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    plano_id = db.Column(
        db.Integer,
        db.ForeignKey("planos.id"),
        nullable=False,
    )

    plano = db.relationship(
        "Plano",
        back_populates="empresas",
    )

    usuarios = db.relationship(
        "Usuario",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    veiculos = db.relationship(
        "Veiculo",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    motoristas = db.relationship(
        "Motorista",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    obras = db.relationship(
        "Obra",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    diarios_bordo = db.relationship(
        "DiarioBordo",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    abastecimentos = db.relationship(
        "Abastecimento",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )

    manutencoes = db.relationship(
        "Manutencao",
        back_populates="empresa",
        cascade="all, delete-orphan",
        lazy=True,
    )


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    nome = db.Column(
        db.String(120),
        nullable=False,
    )

    usuario = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=True,
    )

    senha_hash = db.Column(
        db.String(255),
        nullable=False,
    )

    perfil = db.Column(
        db.String(30),
        nullable=False,
        default="Administrador",
    )

    ativo = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    trocar_senha = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    ultimo_acesso = db.Column(
        db.DateTime,
        nullable=True,
    )

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="usuarios",
    )

    abastecimentos = db.relationship(
        "Abastecimento",
        back_populates="usuario",
        lazy=True,
    )

    manutencoes = db.relationship(
        "Manutencao",
        back_populates="usuario",
        lazy=True,
    )

    @property
    def is_active(self):
        return self.ativo

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(
            self.senha_hash,
            senha,
        )


class Obra(db.Model):
    __tablename__ = "obras"

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "codigo",
            name="uq_obra_empresa_codigo",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    codigo = db.Column(
        db.String(50),
        nullable=False,
    )

    nome = db.Column(
        db.String(150),
        nullable=False,
    )

    cliente = db.Column(
        db.String(150),
        nullable=True,
    )

    localizacao = db.Column(
        db.String(200),
        nullable=True,
    )

    responsavel = db.Column(
        db.String(150),
        nullable=True,
    )

    data_inicio = db.Column(
        db.Date,
        nullable=True,
    )

    data_fim_prevista = db.Column(
        db.Date,
        nullable=True,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Planejada",
    )

    observacoes = db.Column(
        db.Text,
        nullable=True,
    )

    criada_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="obras",
    )

    veiculos = db.relationship(
        "Veiculo",
        back_populates="obra",
        lazy=True,
    )

    diarios_bordo = db.relationship(
        "DiarioBordo",
        back_populates="obra",
        lazy=True,
    )

    abastecimentos = db.relationship(
        "Abastecimento",
        back_populates="obra",
        lazy=True,
    )

    manutencoes = db.relationship(
        "Manutencao",
        back_populates="obra",
        lazy=True,
    )


class Veiculo(db.Model):
    __tablename__ = "veiculos"

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "placa",
            name="uq_veiculo_empresa_placa",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    placa = db.Column(
        db.String(10),
        nullable=False,
    )

    modelo = db.Column(
        db.String(120),
        nullable=False,
    )

    ano = db.Column(
        db.Integer,
        nullable=True,
    )

    combustivel = db.Column(
        db.String(30),
        nullable=True,
    )

    km_atual = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Ativo",
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
    )

    obra_id = db.Column(
        db.Integer,
        db.ForeignKey("obras.id"),
        nullable=True,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="veiculos",
    )

    obra = db.relationship(
        "Obra",
        back_populates="veiculos",
    )

    motoristas = db.relationship(
        "Motorista",
        back_populates="veiculo",
        lazy=True,
    )

    diarios_bordo = db.relationship(
        "DiarioBordo",
        back_populates="veiculo",
        lazy=True,
    )

    abastecimentos = db.relationship(
        "Abastecimento",
        back_populates="veiculo",
        lazy=True,
    )

    manutencoes = db.relationship(
        "Manutencao",
        back_populates="veiculo",
        lazy=True,
    )


class Motorista(db.Model):
    __tablename__ = "motoristas"

    __table_args__ = (
        db.UniqueConstraint(
            "empresa_id",
            "cpf",
            name="uq_motorista_empresa_cpf",
        ),
        db.UniqueConstraint(
            "empresa_id",
            "cnh",
            name="uq_motorista_empresa_cnh",
        ),
    )

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    nome = db.Column(
        db.String(150),
        nullable=False,
    )

    cpf = db.Column(
        db.String(14),
        nullable=False,
    )

    cnh = db.Column(
        db.String(11),
        nullable=False,
    )

    categoria_cnh = db.Column(
        db.String(5),
        nullable=False,
    )

    validade_cnh = db.Column(
        db.Date,
        nullable=False,
    )

    telefone = db.Column(
        db.String(20),
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Ativo",
    )

    observacoes = db.Column(
        db.Text,
        nullable=True,
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    empresa_id = db.Column(
        db.Integer,
        db.ForeignKey("empresas.id"),
        nullable=False,
    )

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=True,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="motoristas",
    )

    veiculo = db.relationship(
        "Veiculo",
        back_populates="motoristas",
    )

    diarios_bordo = db.relationship(
        "DiarioBordo",
        back_populates="motorista",
        lazy=True,
    )

    abastecimentos = db.relationship(
        "Abastecimento",
        back_populates="motorista",
        lazy=True,
    )

    @property
    def dias_para_vencimento_cnh(self):
        if not self.validade_cnh:
            return None

        return (
            self.validade_cnh - date.today()
        ).days

    @property
    def situacao_cnh(self):
        dias = self.dias_para_vencimento_cnh

        if dias is None:
            return "Não informada"

        if dias < 0:
            return "Vencida"

        if dias <= 30:
            return "Vence em breve"

        return "Regular"


class DiarioBordo(db.Model):
    __tablename__ = "diarios_bordo"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    data = db.Column(
        db.Date,
        nullable=False,
    )

    hora_saida = db.Column(
        db.Time,
        nullable=False,
    )

    hora_retorno = db.Column(
        db.Time,
        nullable=True,
    )

    km_inicial = db.Column(
        db.Integer,
        nullable=False,
    )

    km_final = db.Column(
        db.Integer,
        nullable=True,
    )

    origem = db.Column(
        db.String(200),
        nullable=False,
    )

    destino = db.Column(
        db.String(200),
        nullable=False,
    )

    finalidade = db.Column(
        db.String(250),
        nullable=True,
    )

    ocorrencias = db.Column(
        db.Text,
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Em andamento",
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    atualizado_em = db.Column(
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

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=False,
    )

    motorista_id = db.Column(
        db.Integer,
        db.ForeignKey("motoristas.id"),
        nullable=False,
    )

    obra_id = db.Column(
        db.Integer,
        db.ForeignKey("obras.id"),
        nullable=True,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="diarios_bordo",
    )

    veiculo = db.relationship(
        "Veiculo",
        back_populates="diarios_bordo",
    )

    motorista = db.relationship(
        "Motorista",
        back_populates="diarios_bordo",
    )

    obra = db.relationship(
        "Obra",
        back_populates="diarios_bordo",
    )

    @property
    def km_percorrida(self):
        if self.km_final is None:
            return None

        return self.km_final - self.km_inicial


class Abastecimento(db.Model):
    __tablename__ = "abastecimentos"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    data = db.Column(
        db.Date,
        nullable=False,
    )

    hora = db.Column(
        db.Time,
        nullable=True,
    )

    posto = db.Column(
        db.String(150),
        nullable=False,
    )

    combustivel = db.Column(
        db.String(30),
        nullable=False,
    )

    litros = db.Column(
        db.Numeric(10, 3),
        nullable=False,
    )

    valor_litro = db.Column(
        db.Numeric(10, 3),
        nullable=False,
    )

    valor_total = db.Column(
        db.Numeric(12, 2),
        nullable=False,
    )

    km = db.Column(
        db.Integer,
        nullable=False,
    )

    tanque_cheio = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    numero_nota = db.Column(
        db.String(80),
        nullable=True,
    )

    comprovante = db.Column(
        db.String(500),
        nullable=True,
    )

    observacoes = db.Column(
        db.Text,
        nullable=True,
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    atualizado_em = db.Column(
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

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=False,
    )

    motorista_id = db.Column(
        db.Integer,
        db.ForeignKey("motoristas.id"),
        nullable=False,
    )

    obra_id = db.Column(
        db.Integer,
        db.ForeignKey("obras.id"),
        nullable=True,
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="abastecimentos",
    )

    veiculo = db.relationship(
        "Veiculo",
        back_populates="abastecimentos",
    )

    motorista = db.relationship(
        "Motorista",
        back_populates="abastecimentos",
    )

    obra = db.relationship(
        "Obra",
        back_populates="abastecimentos",
    )

    usuario = db.relationship(
        "Usuario",
        back_populates="abastecimentos",
    )


class Manutencao(db.Model):
    __tablename__ = "manutencoes"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    tipo = db.Column(
        db.String(40),
        nullable=False,
    )

    descricao = db.Column(
        db.String(300),
        nullable=False,
    )

    fornecedor = db.Column(
        db.String(150),
        nullable=True,
    )

    data_entrada = db.Column(
        db.Date,
        nullable=False,
    )

    data_saida = db.Column(
        db.Date,
        nullable=True,
    )

    km = db.Column(
        db.Integer,
        nullable=False,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="Agendada",
    )

    valor_pecas = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
    )

    valor_mao_obra = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
    )

    valor_total = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0,
    )

    proxima_manutencao_data = db.Column(
        db.Date,
        nullable=True,
    )

    proxima_manutencao_km = db.Column(
        db.Integer,
        nullable=True,
    )

    numero_nota = db.Column(
        db.String(80),
        nullable=True,
    )

    comprovante = db.Column(
        db.String(500),
        nullable=True,
    )

    observacoes = db.Column(
        db.Text,
        nullable=True,
    )

    criado_em = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    atualizado_em = db.Column(
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

    veiculo_id = db.Column(
        db.Integer,
        db.ForeignKey("veiculos.id"),
        nullable=False,
    )

    obra_id = db.Column(
        db.Integer,
        db.ForeignKey("obras.id"),
        nullable=True,
    )

    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False,
    )

    empresa = db.relationship(
        "Empresa",
        back_populates="manutencoes",
    )

    veiculo = db.relationship(
        "Veiculo",
        back_populates="manutencoes",
    )

    obra = db.relationship(
        "Obra",
        back_populates="manutencoes",
    )

    usuario = db.relationship(
        "Usuario",
        back_populates="manutencoes",
    )