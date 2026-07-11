import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from controllers.abastecimentos import abastecimentos_bp
from controllers.auth import auth_bp
from controllers.diario import diario_bp
from controllers.manutencoes import manutencoes_bp
from controllers.motoristas import motoristas_bp
from controllers.obras import obras_bp
from controllers.veiculos import veiculos_bp
from database.models import (
    Abastecimento,
    DiarioBordo,
    Motorista,
    Usuario,
    Veiculo,
)
from extensions import db, login_manager, migrate


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

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

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
    app.register_blueprint(diario_bp)
    app.register_blueprint(abastecimentos_bp)
    app.register_blueprint(manutencoes_bp)

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
            and request.endpoint not in rotas_liberadas
        ):
            return redirect(
                url_for("auth.trocar_senha")
            )

        return None

    @app.errorhandler(413)
    def arquivo_muito_grande(_erro):
        flash(
            "O arquivo enviado ultrapassa o limite de 8 MB.",
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

        total_veiculos = (
            Veiculo.query
            .filter_by(empresa_id=empresa.id)
            .count()
        )

        total_motoristas = (
            Motorista.query
            .filter_by(empresa_id=empresa.id)
            .count()
        )

        total_diarios = (
            DiarioBordo.query
            .filter_by(empresa_id=empresa.id)
            .count()
        )

        total_abastecimentos = (
            Abastecimento.query
            .filter_by(empresa_id=empresa.id)
            .count()
        )

        return render_template(
            "dashboard.html",
            empresa=empresa,
            total_veiculos=total_veiculos,
            total_motoristas=total_motoristas,
            total_abastecimentos=total_abastecimentos,
            total_diarios=total_diarios,
        )

    @app.route("/relatorios")
    @login_required
    def relatorios():
        return render_template(
            "relatorios.html"
        )

    @app.route("/configuracoes")
    @login_required
    def configuracoes():
        return render_template(
            "configuracoes.html"
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)