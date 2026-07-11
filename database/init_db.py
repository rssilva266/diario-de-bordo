from decimal import Decimal

from app import create_app
from database.models import Empresa, Plano, Usuario
from extensions import db


app = create_app()


with app.app_context():
    db.create_all()

    planos = [
        {
            "nome": "Starter",
            "limite_veiculos": 10,
            "valor_mensal_minimo": Decimal("249.00"),
            "valor_mensal_maximo": Decimal("249.00"),
            "preco_sob_consulta": False,
        },
        {
            "nome": "Standard",
            "limite_veiculos": 50,
            "valor_mensal_minimo": Decimal("499.00"),
            "valor_mensal_maximo": Decimal("699.00"),
            "preco_sob_consulta": False,
            "possui_ocr": True,
            "possui_indicadores_avancados": True,
            "possui_ranking": True,
            "possui_alertas": True,
            "possui_api": True,
            "possui_backup_diario": True,
        },
        {
            "nome": "Professional",
            "limite_veiculos": 250,
            "valor_mensal_minimo": None,
            "valor_mensal_maximo": None,
            "preco_sob_consulta": True,
            "possui_ocr": True,
            "possui_indicadores_avancados": True,
            "possui_ranking": True,
            "possui_alertas": True,
            "possui_api": True,
            "possui_backup_diario": True,
            "possui_multiempresa": True,
            "possui_aplicativo": True,
            "possui_ia": True,
            "possui_integracoes": True,
            "possui_suporte_prioritario": True,
        },
    ]

    for dados_plano in planos:
        plano = Plano.query.filter_by(
            nome=dados_plano["nome"]
        ).first()

        if plano is None:
            plano = Plano(**dados_plano)
            db.session.add(plano)

    db.session.commit()

    plano_starter = Plano.query.filter_by(
        nome="Starter"
    ).first()

    empresa = Empresa.query.first()

    if empresa is None:
        empresa = Empresa(
            razao_social="Empresa de Demonstração",
            nome_fantasia="MSM Fleet",
            plano_id=plano_starter.id,
            ativa=True,
        )

        db.session.add(empresa)
        db.session.commit()

    usuario_admin = Usuario.query.filter_by(
        usuario="admin"
    ).first()

    if usuario_admin is None:
        usuario_admin = Usuario(
            empresa_id=empresa.id,
            nome="Administrador",
            usuario="admin",
            email="admin@msmfleet.local",
            perfil="Administrador",
            ativo=True,
            trocar_senha=True,
        )

        usuario_admin.definir_senha("Admin@123")

        db.session.add(usuario_admin)
        db.session.commit()

    print("")
    print("Banco de dados inicializado com sucesso.")
    print("----------------------------------------")
    print("Empresa inicial: Empresa de Demonstração")
    print("Plano inicial: Starter")
    print("Usuário inicial: admin")
    print("Senha temporária: Admin@123")
    print("----------------------------------------")