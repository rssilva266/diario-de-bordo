from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python validar_instalacao.py <raiz-projeto>")

    raiz = Path(sys.argv[1]).resolve()
    os.chdir(raiz)
    sys.path.insert(0, str(raiz))

    from app import app
    from controllers.usuarios import PERFIS_PERMITIDOS
    from extensions import db
    from sqlalchemy import inspect

    rotas = {regra.rule for regra in app.url_map.iter_rules()}
    rotas_esperadas = {
        "/movimentacoes-materiais",
        "/movimentacoes-materiais/<int:movimentacao_id>/cancelar",
        "/api/mobile/materiais/pendentes",
        "/api/mobile/materiais/historico",
        "/api/mobile/materiais/<int:movimentacao_id>/receber",
    }
    faltando = rotas_esperadas - rotas
    if faltando:
        raise RuntimeError(f"Rotas ausentes: {sorted(faltando)}")

    if "Apontador" not in PERFIS_PERMITIDOS:
        raise RuntimeError("O perfil Apontador não foi habilitado.")

    for template in (
        "diario.html",
        "movimentacoes_materiais.html",
        "usuarios.html",
        "layout/base.html",
    ):
        app.jinja_env.get_template(template)

    with app.app_context():
        inspetor = inspect(db.engine)
        if "movimentacoes_materiais" not in inspetor.get_table_names():
            raise RuntimeError("A tabela de movimentações não foi criada.")

        colunas = {
            coluna["name"]
            for coluna in inspetor.get_columns("movimentacoes_materiais")
        }
        esperadas = {
            "material",
            "numero_movimentacao",
            "status",
            "foto_recebimento",
            "recebido_em",
            "recebido_por_id",
            "diario_bordo_id",
        }
        ausentes = esperadas - colunas
        if ausentes:
            raise RuntimeError(
                f"Colunas ausentes na movimentação: {sorted(ausentes)}"
            )

    arquivos_mobile = (
        raiz / "mobile" / "lib" / "screens" / "material_screen.dart",
        raiz / "mobile" / "lib" / "services" / "material_service.dart",
        raiz / "mobile" / "lib" / "models" / "material_movement.dart",
        raiz / "mobile" / "test" / "material_models_test.dart",
    )
    for arquivo in arquivos_mobile:
        if not arquivo.is_file():
            raise RuntimeError(f"Arquivo mobile ausente: {arquivo}")

    print("VALIDACAO_MATERIAIS_OK")


if __name__ == "__main__":
    main()
