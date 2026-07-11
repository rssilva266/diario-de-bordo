# Atualização: Ponto Eletrônico

## O que foi incluído

- Menu reorganizado em Cadastros, Operações, Relatórios e Administração.
- Cadastro de usuários dentro de Cadastros.
- Backup e Atualizações dentro de Administração.
- Cadastro de colaboradores para o Ponto Eletrônico.
- Cadastro de locais de trabalho com latitude, longitude e raio de geocerca.
- Tela mobile de Ponto Eletrônico com captura facial e GPS.
- Registro de Entrada, Início do intervalo, Retorno e Saída.
- API `POST /api/ponto/registrar` preparada para aplicativo Android.
- Idempotência por `client_uuid`, evitando duplicação na sincronização.
- Fila offline no navegador: se não houver internet, a marcação fica no aparelho e é enviada quando a conexão voltar.
- Tela de Gestão do Ponto com foto, horário, precisão do GPS e situação da geocerca.

## Instalação

No terminal, dentro da pasta do projeto:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
flask --app app db upgrade
python app.py
```

## Primeira configuração

1. Entre com um usuário Administrador.
2. Acesse **Cadastros → Locais de Trabalho** e cadastre a coordenada da obra/unidade.
3. Acesse **Cadastros → Colaboradores**.
4. Cadastre o colaborador e vincule-o a um usuário do sistema e a um local de trabalho.
5. O colaborador acessa **Operações → Ponto Eletrônico** pelo celular.

## Observações importantes

- A primeira versão faz captura facial, mas ainda não executa reconhecimento biométrico automático nem prova de vida.
- A câmera e o GPS do navegador exigem HTTPS quando o sistema não está em `localhost`.
- O modo offline guarda os registros no navegador do aparelho. Não limpe os dados do navegador antes da sincronização.
- O módulo foi concebido como controle operacional de jornada, não como certificação oficial de REP.
