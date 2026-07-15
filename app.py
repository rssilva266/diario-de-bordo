import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from controllers.configuracoes import configuracoes_bp
from controllers.abastecimentos import abastecimentos_bp
from controllers.auth import auth_bp
from controllers.diario import diario_bp
from controllers.manutencoes import manutencoes_bp
from controllers.motoristas import motoristas_bp
from controllers.obras import obras_bp
from controllers.ponto import ponto_bp
from controllers.mobile_api import mobile_api_bp
from controllers.relatorios import relatorios_bp
from controllers.sistema import sistema_bp
from controllers.usuarios import usuarios_bp
from controllers.veiculos import veiculos_bp
from database.models import (
    Abastecimento,
    DiarioBordo,
    Manutencao,
    Motorista,
    Usuario,
    Veiculo,
)
from extensions import db, login_manager, migrate


def decimal_zero(valor):
    if valor is None:
        return Decimal("0")

    return Decimal(valor)


def dividir_decimal(
    dividendo,
    divisor,
    casas="0.01",
):
    if not divisor:
        return Decimal("0")

    return (
        Decimal(dividendo)
        / Decimal(divisor)
    ).quantize(
        Decimal(casas),
        rounding=ROUND_HALF_UP,
    )


def deslocar_mes(data_base, quantidade_meses):
    indice_mes = (
        data_base.year * 12
        + data_base.month
        - 1
        + quantidade_meses
    )

    ano = indice_mes // 12
    mes = indice_mes % 12 + 1

    return date(
        ano,
        mes,
        1,
    )


def obter_meses_dashboard(hoje, quantidade=6):
    inicio_mes_atual = hoje.replace(day=1)

    return [
        deslocar_mes(
            inicio_mes_atual,
            deslocamento,
        )
        for deslocamento in range(
            -(quantidade - 1),
            1,
        )
    ]


def criar_atividade(
    tipo,
    icone,
    titulo,
    descricao,
    data_registro,
    criado_em,
    valor=None,
    unidade=None,
):
    momento = criado_em

    if momento is None:
        momento = datetime.combine(
            data_registro,
            time.min,
        )

    return {
        "tipo": tipo,
        "icone": icone,
        "titulo": titulo,
        "descricao": descricao,
        "data": data_registro,
        "momento": momento,
        "valor": valor,
        "unidade": unidade,
    }


def create_app():
    app = Flask(__name__)

    base_dir = os.path.abspath(
        os.path.dirname(__file__)
    )

    caminho_banco = os.path.join(
        base_dir,
        "database",
        "banco.db",
    )

    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY",
        "chave-local-de-desenvolvimento",
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        "sqlite:///"
        + caminho_banco.replace("\\", "/")
    )

    app.config[
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    ] = False

    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["MAX_CONTENT_LENGTH"] = (
        8 * 1024 * 1024
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(veiculos_bp)
    app.register_blueprint(motoristas_bp)
    app.register_blueprint(obras_bp)
    app.register_blueprint(ponto_bp)
    app.register_blueprint(mobile_api_bp)
    app.register_blueprint(diario_bp)
    app.register_blueprint(abastecimentos_bp)
    app.register_blueprint(manutencoes_bp)
    app.register_blueprint(relatorios_bp)
    app.register_blueprint(configuracoes_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(sistema_bp)

    @login_manager.user_loader
    def carregar_usuario(usuario_id):
        try:
            usuario_id = int(usuario_id)
        except (TypeError, ValueError):
            return None

        return db.session.get(
            Usuario,
            usuario_id,
        )

    @app.before_request
    def exigir_troca_de_senha():
        if not current_user.is_authenticated:
            return None

        rotas_liberadas = {
            "auth.trocar_senha",
            "auth.logout",
            "static",
        }

        if (
            current_user.trocar_senha
            and request.endpoint
            not in rotas_liberadas
        ):
            return redirect(
                url_for("auth.trocar_senha")
            )

        return None

    @app.errorhandler(413)
    def arquivo_muito_grande(_erro):
        flash(
            "O arquivo enviado ultrapassa "
            "o limite de 8 MB.",
            "warning",
        )

        return redirect(
            request.referrer
            or url_for("dashboard")
        )

    @app.route("/")
    @login_required
    def dashboard():
        empresa = current_user.empresa
        hoje = date.today()

        inicio_mes = hoje.replace(day=1)

        fim_mes_anterior = (
            inicio_mes
            - timedelta(days=1)
        )

        inicio_mes_anterior = (
            fim_mes_anterior.replace(day=1)
        )

        meses_dashboard = obter_meses_dashboard(
            hoje,
            quantidade=6,
        )

        inicio_periodo_grafico = (
            meses_dashboard[0]
        )

        # ==========================================
        # VEÍCULOS E MOTORISTAS
        # ==========================================

        veiculos = (
            Veiculo.query
            .filter_by(empresa_id=empresa.id)
            .order_by(Veiculo.placa.asc())
            .all()
        )

        motoristas = (
            Motorista.query
            .filter_by(empresa_id=empresa.id)
            .order_by(Motorista.nome.asc())
            .all()
        )

        total_veiculos = len(veiculos)

        veiculos_ativos = sum(
            1
            for veiculo in veiculos
            if (
                veiculo.status
                or ""
            ).strip().lower() == "ativo"
        )

        veiculos_em_manutencao = sum(
            1
            for veiculo in veiculos
            if (
                veiculo.status
                or ""
            ).strip().lower() == "em manutenção"
        )

        veiculos_outros_status = (
            total_veiculos
            - veiculos_ativos
            - veiculos_em_manutencao
        )

        total_motoristas = len(motoristas)

        # ==========================================
        # DADOS DO MÊS ATUAL
        # ==========================================

        abastecimentos_mes = (
            Abastecimento.query
            .filter(
                Abastecimento.empresa_id
                == empresa.id,
                Abastecimento.data
                >= inicio_mes,
                Abastecimento.data
                <= hoje,
            )
            .order_by(
                Abastecimento.data.desc(),
                Abastecimento.id.desc(),
            )
            .all()
        )

        manutencoes_mes = (
            Manutencao.query
            .filter(
                Manutencao.empresa_id
                == empresa.id,
                Manutencao.data_entrada
                >= inicio_mes,
                Manutencao.data_entrada
                <= hoje,
            )
            .order_by(
                Manutencao.data_entrada.desc(),
                Manutencao.id.desc(),
            )
            .all()
        )

        diarios_mes = (
            DiarioBordo.query
            .filter(
                DiarioBordo.empresa_id
                == empresa.id,
                DiarioBordo.data
                >= inicio_mes,
                DiarioBordo.data
                <= hoje,
            )
            .order_by(
                DiarioBordo.data.desc(),
                DiarioBordo.id.desc(),
            )
            .all()
        )

        total_combustivel_mes = sum(
            (
                decimal_zero(
                    abastecimento.valor_total
                )
                for abastecimento
                in abastecimentos_mes
            ),
            Decimal("0"),
        )

        total_manutencao_mes = sum(
            (
                decimal_zero(
                    manutencao.valor_total
                )
                for manutencao
                in manutencoes_mes
            ),
            Decimal("0"),
        )

        custo_total_mes = (
            total_combustivel_mes
            + total_manutencao_mes
        )

        total_litros_mes = sum(
            (
                decimal_zero(
                    abastecimento.litros
                )
                for abastecimento
                in abastecimentos_mes
            ),
            Decimal("0"),
        )

        total_km_mes = sum(
            (
                diario.km_percorrida or 0
                for diario in diarios_mes
            ),
            0,
        )

        custo_por_km_mes = dividir_decimal(
            custo_total_mes,
            total_km_mes,
        )

        preco_medio_litro = dividir_decimal(
            total_combustivel_mes,
            total_litros_mes,
            casas="0.001",
        )

        # ==========================================
        # COMPARAÇÃO COM O MÊS ANTERIOR
        # ==========================================

        abastecimentos_mes_anterior = (
            Abastecimento.query
            .filter(
                Abastecimento.empresa_id
                == empresa.id,
                Abastecimento.data
                >= inicio_mes_anterior,
                Abastecimento.data
                <= fim_mes_anterior,
            )
            .all()
        )

        manutencoes_mes_anterior = (
            Manutencao.query
            .filter(
                Manutencao.empresa_id
                == empresa.id,
                Manutencao.data_entrada
                >= inicio_mes_anterior,
                Manutencao.data_entrada
                <= fim_mes_anterior,
            )
            .all()
        )

        custo_mes_anterior = sum(
            (
                decimal_zero(
                    item.valor_total
                )
                for item
                in abastecimentos_mes_anterior
            ),
            Decimal("0"),
        )

        custo_mes_anterior += sum(
            (
                decimal_zero(
                    item.valor_total
                )
                for item
                in manutencoes_mes_anterior
            ),
            Decimal("0"),
        )

        variacao_custo_mes = None

        if custo_mes_anterior > 0:
            variacao_custo_mes = (
                (
                    custo_total_mes
                    - custo_mes_anterior
                )
                * Decimal("100")
                / custo_mes_anterior
            ).quantize(
                Decimal("0.1"),
                rounding=ROUND_HALF_UP,
            )

        # ==========================================
        # DIÁRIOS EM ANDAMENTO
        # ==========================================

        diarios_em_andamento = (
            DiarioBordo.query
            .filter(
                DiarioBordo.empresa_id
                == empresa.id,
                DiarioBordo.status
                == "Em andamento",
            )
            .order_by(
                DiarioBordo.data.desc(),
                DiarioBordo.hora_saida.desc(),
            )
            .all()
        )

        total_diarios_em_andamento = len(
            diarios_em_andamento
        )

        # ==========================================
        # CNHS PRÓXIMAS OU VENCIDAS
        # ==========================================

        limite_cnh = (
            hoje
            + timedelta(days=30)
        )

        motoristas_cnh_alerta = [
            motorista
            for motorista in motoristas
            if (
                motorista.status == "Ativo"
                and motorista.validade_cnh
                and motorista.validade_cnh
                <= limite_cnh
            )
        ]

        total_cnh_alerta = len(
            motoristas_cnh_alerta
        )

        # ==========================================
        # PRÓXIMAS MANUTENÇÕES
        # ==========================================

        manutencoes_empresa = (
            Manutencao.query
            .filter_by(empresa_id=empresa.id)
            .order_by(
                Manutencao.data_entrada.desc(),
                Manutencao.id.desc(),
            )
            .all()
        )

        ultima_manutencao_por_veiculo = {}

        for manutencao in manutencoes_empresa:
            if (
                manutencao.veiculo_id
                not in ultima_manutencao_por_veiculo
            ):
                ultima_manutencao_por_veiculo[
                    manutencao.veiculo_id
                ] = manutencao

        manutencoes_proximas = []

        for manutencao in (
            ultima_manutencao_por_veiculo.values()
        ):
            veiculo = manutencao.veiculo

            if veiculo is None:
                continue

            alerta_data = False
            alerta_km = False
            vencida_data = False
            vencida_km = False

            if manutencao.proxima_manutencao_data:
                alerta_data = (
                    manutencao.proxima_manutencao_data
                    <= hoje + timedelta(days=30)
                )

                vencida_data = (
                    manutencao.proxima_manutencao_data
                    < hoje
                )

            if manutencao.proxima_manutencao_km:
                alerta_km = (
                    manutencao.proxima_manutencao_km
                    <= veiculo.km_atual + 1000
                )

                vencida_km = (
                    manutencao.proxima_manutencao_km
                    <= veiculo.km_atual
                )

            if alerta_data or alerta_km:
                manutencoes_proximas.append({
                    "veiculo": veiculo,
                    "manutencao": manutencao,
                    "vencida": (
                        vencida_data
                        or vencida_km
                    ),
                })

        total_manutencoes_proximas = len(
            manutencoes_proximas
        )

        # ==========================================
        # VEÍCULOS SEM MOVIMENTAÇÃO
        # ==========================================

        limite_sem_movimento = (
            hoje
            - timedelta(days=15)
        )

        diarios_empresa = (
            DiarioBordo.query
            .filter_by(empresa_id=empresa.id)
            .order_by(
                DiarioBordo.data.desc(),
                DiarioBordo.id.desc(),
            )
            .all()
        )

        ultima_movimentacao_por_veiculo = {}

        for diario in diarios_empresa:
            if (
                diario.veiculo_id
                not in ultima_movimentacao_por_veiculo
            ):
                ultima_movimentacao_por_veiculo[
                    diario.veiculo_id
                ] = diario.data

        veiculos_sem_movimento = [
            veiculo
            for veiculo in veiculos
            if (
                veiculo.status == "Ativo"
                and (
                    veiculo.id
                    not in ultima_movimentacao_por_veiculo
                    or ultima_movimentacao_por_veiculo[
                        veiculo.id
                    ] < limite_sem_movimento
                )
            )
        ]

        total_sem_movimento = len(
            veiculos_sem_movimento
        )

        # ==========================================
        # ALERTAS EXECUTIVOS
        # ==========================================

        alertas = []

        if total_diarios_em_andamento:
            alertas.append({
                "tipo": "warning",
                "icone": "bi-journal-exclamation",
                "titulo": "Diários em andamento",
                "texto": (
                    f"{total_diarios_em_andamento} "
                    f"diário(s) de bordo ainda "
                    f"não foi(ram) concluído(s)."
                ),
                "url": url_for(
                    "diario.listar_diarios",
                    status="Em andamento",
                ),
            })

        if total_cnh_alerta:
            alertas.append({
                "tipo": "danger",
                "icone": "bi-person-vcard",
                "titulo": "CNHs exigem atenção",
                "texto": (
                    f"{total_cnh_alerta} motorista(s) "
                    f"possui(em) CNH vencida ou "
                    f"vencendo nos próximos 30 dias."
                ),
                "url": url_for(
                    "motoristas.listar_motoristas"
                ),
            })

        if total_manutencoes_proximas:
            alertas.append({
                "tipo": "warning",
                "icone": "bi-wrench-adjustable",
                "titulo": "Manutenções próximas",
                "texto": (
                    f"{total_manutencoes_proximas} "
                    f"veículo(s) está(ão) próximo(s) "
                    f"da manutenção programada."
                ),
                "url": url_for(
                    "manutencoes.listar_manutencoes"
                ),
            })

        if total_sem_movimento:
            alertas.append({
                "tipo": "info",
                "icone": "bi-pause-circle",
                "titulo": "Veículos sem movimentação",
                "texto": (
                    f"{total_sem_movimento} veículo(s) "
                    f"ativo(s) não possui(em) diário "
                    f"nos últimos 15 dias."
                ),
                "url": url_for(
                    "veiculos.listar_veiculos"
                ),
            })

        if (
            total_manutencao_mes
            > total_combustivel_mes
            and custo_total_mes > 0
        ):
            alertas.append({
                "tipo": "warning",
                "icone": "bi-tools",
                "titulo": "Manutenção acima do combustível",
                "texto": (
                    "Neste mês, os gastos com "
                    "manutenção superaram os gastos "
                    "com combustível."
                ),
                "url": url_for(
                    "relatorios.listar_relatorios"
                ),
            })

        if not alertas:
            alertas.append({
                "tipo": "success",
                "icone": "bi-check-circle",
                "titulo": "Operação sem alertas críticos",
                "texto": (
                    "Nenhuma pendência importante foi "
                    "identificada neste momento."
                ),
                "url": None,
            })

        # ==========================================
        # GRÁFICO DOS ÚLTIMOS SEIS MESES
        # ==========================================

        abastecimentos_periodo = (
            Abastecimento.query
            .filter(
                Abastecimento.empresa_id
                == empresa.id,
                Abastecimento.data
                >= inicio_periodo_grafico,
                Abastecimento.data
                <= hoje,
            )
            .all()
        )

        manutencoes_periodo = (
            Manutencao.query
            .filter(
                Manutencao.empresa_id
                == empresa.id,
                Manutencao.data_entrada
                >= inicio_periodo_grafico,
                Manutencao.data_entrada
                <= hoje,
            )
            .all()
        )

        custos_por_mes = {
            (
                mes.year,
                mes.month,
            ): {
                "combustivel": Decimal("0"),
                "manutencao": Decimal("0"),
            }
            for mes in meses_dashboard
        }

        for abastecimento in abastecimentos_periodo:
            chave = (
                abastecimento.data.year,
                abastecimento.data.month,
            )

            if chave in custos_por_mes:
                custos_por_mes[chave][
                    "combustivel"
                ] += decimal_zero(
                    abastecimento.valor_total
                )

        for manutencao in manutencoes_periodo:
            chave = (
                manutencao.data_entrada.year,
                manutencao.data_entrada.month,
            )

            if chave in custos_por_mes:
                custos_por_mes[chave][
                    "manutencao"
                ] += decimal_zero(
                    manutencao.valor_total
                )

        grafico_meses = [
            mes.strftime("%m/%Y")
            for mes in meses_dashboard
        ]

        grafico_combustivel = [
            float(
                custos_por_mes[
                    (mes.year, mes.month)
                ]["combustivel"]
            )
            for mes in meses_dashboard
        ]

        grafico_manutencao = [
            float(
                custos_por_mes[
                    (mes.year, mes.month)
                ]["manutencao"]
            )
            for mes in meses_dashboard
        ]

        # ==========================================
        # RANKING DE CUSTOS POR VEÍCULO
        # ==========================================

        custos_veiculos = {
            veiculo.id: {
                "veiculo": veiculo,
                "combustivel": Decimal("0"),
                "manutencao": Decimal("0"),
                "total": Decimal("0"),
            }
            for veiculo in veiculos
        }

        for abastecimento in abastecimentos_periodo:
            if (
                abastecimento.veiculo_id
                in custos_veiculos
            ):
                custos_veiculos[
                    abastecimento.veiculo_id
                ]["combustivel"] += decimal_zero(
                    abastecimento.valor_total
                )

        for manutencao in manutencoes_periodo:
            if (
                manutencao.veiculo_id
                in custos_veiculos
            ):
                custos_veiculos[
                    manutencao.veiculo_id
                ]["manutencao"] += decimal_zero(
                    manutencao.valor_total
                )

        for item in custos_veiculos.values():
            item["total"] = (
                item["combustivel"]
                + item["manutencao"]
            )

        ranking_veiculos = sorted(
            [
                item
                for item in custos_veiculos.values()
                if item["total"] > 0
            ],
            key=lambda item: item["total"],
            reverse=True,
        )[:5]

        grafico_ranking_labels = [
            item["veiculo"].placa
            for item in ranking_veiculos
        ]

        grafico_ranking_valores = [
            float(item["total"])
            for item in ranking_veiculos
        ]

        participacao_maior_custo = None

        total_periodo_ranking = sum(
            (
                item["total"]
                for item in ranking_veiculos
            ),
            Decimal("0"),
        )

        if (
            ranking_veiculos
            and total_periodo_ranking > 0
        ):
            participacao_maior_custo = (
                ranking_veiculos[0]["total"]
                * Decimal("100")
                / total_periodo_ranking
            ).quantize(
                Decimal("0.1"),
                rounding=ROUND_HALF_UP,
            )

        # ==========================================
        # GRÁFICO DE STATUS DOS VEÍCULOS
        # ==========================================

        grafico_status_labels = [
            "Ativos",
            "Em manutenção",
            "Outros",
        ]

        grafico_status_valores = [
            veiculos_ativos,
            veiculos_em_manutencao,
            veiculos_outros_status,
        ]

        # ==========================================
        # ATIVIDADES RECENTES
        # ==========================================

        atividades = []

        ultimos_abastecimentos = (
            Abastecimento.query
            .filter_by(empresa_id=empresa.id)
            .order_by(
                Abastecimento.data.desc(),
                Abastecimento.id.desc(),
            )
            .limit(5)
            .all()
        )

        ultimas_manutencoes = (
            Manutencao.query
            .filter_by(empresa_id=empresa.id)
            .order_by(
                Manutencao.data_entrada.desc(),
                Manutencao.id.desc(),
            )
            .limit(5)
            .all()
        )

        ultimos_diarios = (
            DiarioBordo.query
            .filter_by(empresa_id=empresa.id)
            .order_by(
                DiarioBordo.data.desc(),
                DiarioBordo.id.desc(),
            )
            .limit(5)
            .all()
        )

        for abastecimento in ultimos_abastecimentos:
            atividades.append(
                criar_atividade(
                    tipo="abastecimento",
                    icone="bi-fuel-pump",
                    titulo=(
                        f"Abastecimento "
                        f"{abastecimento.veiculo.placa}"
                    ),
                    descricao=(
                        f"{abastecimento.posto} · "
                        f"{abastecimento.litros} L"
                    ),
                    data_registro=abastecimento.data,
                    criado_em=abastecimento.criado_em,
                    valor=abastecimento.valor_total,
                    unidade="R$",
                )
            )

        for manutencao in ultimas_manutencoes:
            atividades.append(
                criar_atividade(
                    tipo="manutencao",
                    icone="bi-tools",
                    titulo=(
                        f"Manutenção "
                        f"{manutencao.veiculo.placa}"
                    ),
                    descricao=(
                        f"{manutencao.tipo} · "
                        f"{manutencao.status}"
                    ),
                    data_registro=(
                        manutencao.data_entrada
                    ),
                    criado_em=manutencao.criado_em,
                    valor=manutencao.valor_total,
                    unidade="R$",
                )
            )

        for diario in ultimos_diarios:
            atividades.append(
                criar_atividade(
                    tipo="diario",
                    icone="bi-journal-text",
                    titulo=(
                        f"Diário "
                        f"{diario.veiculo.placa}"
                    ),
                    descricao=(
                        f"{diario.origem} → "
                        f"{diario.destino}"
                    ),
                    data_registro=diario.data,
                    criado_em=diario.criado_em,
                    valor=diario.km_percorrida,
                    unidade="km",
                )
            )

        atividades_recentes = sorted(
            atividades,
            key=lambda item: item["momento"],
            reverse=True,
        )[:8]

        return render_template(
            "dashboard.html",
            empresa=empresa,
            hoje=hoje,
            inicio_mes=inicio_mes,
            total_veiculos=total_veiculos,
            total_motoristas=total_motoristas,
            veiculos_ativos=veiculos_ativos,
            veiculos_em_manutencao=(
                veiculos_em_manutencao
            ),
            veiculos_outros_status=(
                veiculos_outros_status
            ),
            total_combustivel_mes=(
                total_combustivel_mes
            ),
            total_manutencao_mes=(
                total_manutencao_mes
            ),
            custo_total_mes=custo_total_mes,
            total_litros_mes=total_litros_mes,
            total_km_mes=total_km_mes,
            custo_por_km_mes=custo_por_km_mes,
            preco_medio_litro=preco_medio_litro,
            variacao_custo_mes=variacao_custo_mes,
            total_abastecimentos_mes=len(
                abastecimentos_mes
            ),
            total_manutencoes_mes=len(
                manutencoes_mes
            ),
            total_diarios_mes=len(
                diarios_mes
            ),
            total_diarios_em_andamento=(
                total_diarios_em_andamento
            ),
            total_cnh_alerta=total_cnh_alerta,
            total_manutencoes_proximas=(
                total_manutencoes_proximas
            ),
            total_sem_movimento=(
                total_sem_movimento
            ),
            alertas=alertas,
            ranking_veiculos=ranking_veiculos,
            participacao_maior_custo=(
                participacao_maior_custo
            ),
            atividades_recentes=(
                atividades_recentes
            ),
            grafico_meses=grafico_meses,
            grafico_combustivel=(
                grafico_combustivel
            ),
            grafico_manutencao=(
                grafico_manutencao
            ),
            grafico_ranking_labels=(
                grafico_ranking_labels
            ),
            grafico_ranking_valores=(
                grafico_ranking_valores
            ),
            grafico_status_labels=(
                grafico_status_labels
            ),
            grafico_status_valores=(
                grafico_status_valores
            ),
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)