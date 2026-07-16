from __future__ import annotations

import sys
from pathlib import Path


def substituir_unico(texto: str, antigo: str, novo: str, descricao: str) -> str:
    if novo in texto:
        return texto

    quantidade = texto.count(antigo)
    if quantidade != 1:
        raise RuntimeError(
            f"Não foi possível localizar {descricao} de forma segura "
            f"(ocorrências encontradas: {quantidade})."
        )

    return texto.replace(antigo, novo, 1)


def ajustar_menu(raiz: Path) -> None:
    caminho = raiz / "templates" / "layout" / "base.html"
    texto = caminho.read_text(encoding="utf-8")

    if "Movimentações de Materiais" not in texto:
        alvo_condicao = (
            "or request.path.startswith('/diario') or "
            "request.path.startswith('/ponto-eletronico')"
        )
        nova_condicao = (
            "or request.path.startswith('/diario') or "
            "request.path.startswith('/movimentacoes-materiais') or "
            "request.path.startswith('/ponto-eletronico')"
        )

        ocorrencias = texto.count(alvo_condicao)
        if ocorrencias < 2:
            raise RuntimeError(
                "Não foi possível identificar o menu Operações no base.html."
            )
        texto = texto.replace(alvo_condicao, nova_condicao)

        linha_diario = (
            '<li class="nav-item"><a href="/diario" class="nav-link '
            "{% if request.path.startswith('/diario') %}active{% endif %}\">"
            '<i class="nav-icon bi bi-journal-text"></i><p>Diário de Bordo'
            "</p></a></li>"
        )
        linha_movimentacoes = (
            linha_diario
            + "\n                            "
            + '<li class="nav-item"><a href="{{ '
            "url_for('diario.listar_movimentacoes_materiais') }}\" "
            + 'class="nav-link {% if request.path.startswith('
            "'/movimentacoes-materiais') %}active{% endif %}\">"
            + '<i class="nav-icon bi bi-box-seam"></i>'
            + "<p>Movimentações de Materiais</p></a></li>"
        )
        texto = substituir_unico(
            texto,
            linha_diario,
            linha_movimentacoes,
            "o item Diário de Bordo no menu",
        )

    caminho.write_text(texto, encoding="utf-8")


def ajustar_perfis(raiz: Path) -> None:
    controlador = raiz / "controllers" / "usuarios.py"
    texto = controlador.read_text(encoding="utf-8")
    texto = substituir_unico(
        texto,
        '    "Motorista",\n    "Operador",',
        '    "Motorista",\n    "Apontador",\n    "Operador",',
        "a lista de perfis do controlador de usuários",
    )
    controlador.write_text(texto, encoding="utf-8")

    template = raiz / "templates" / "usuarios.html"
    texto = template.read_text(encoding="utf-8")
    texto = substituir_unico(
        texto,
        '                                    "Motorista",\n'
        '                                    "Operador"',
        '                                    "Motorista",\n'
        '                                    "Apontador",\n'
        '                                    "Operador"',
        "a lista de perfis da edição de usuário",
    )
    texto = substituir_unico(
        texto,
        '                                <option value="Frota">\n'
        '                                    Frota\n'
        "                                </option>",
        '                                <option value="Apontador">\n'
        '                                    Apontador\n'
        '                                </option>\n\n'
        '                                <option value="Frota">\n'
        '                                    Frota\n'
        "                                </option>",
        "a lista de perfis do novo usuário",
    )
    template.write_text(texto, encoding="utf-8")


def ajustar_versao_mobile(raiz: Path) -> None:
    caminho = raiz / "mobile" / "pubspec.yaml"
    texto = caminho.read_text(encoding="utf-8")

    linhas = texto.splitlines()
    encontrou = False
    for indice, linha in enumerate(linhas):
        if linha.startswith("version:"):
            linhas[indice] = "version: 1.1.0+3"
            encontrou = True
            break

    if not encontrou:
        raise RuntimeError("A versão não foi encontrada no pubspec.yaml.")

    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python aplicar_ajustes_existentes.py <raiz-projeto>")

    raiz = Path(sys.argv[1]).resolve()
    ajustar_menu(raiz)
    ajustar_perfis(raiz)
    ajustar_versao_mobile(raiz)
    print("Menu, perfil Apontador e versão mobile ajustados.")


if __name__ == "__main__":
    main()
