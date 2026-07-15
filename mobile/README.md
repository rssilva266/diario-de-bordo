# Diário de Bordo Mobile

Aplicativo Android de ponto eletrônico e diário de bordo.

## Recursos desta etapa

- autenticação integrada aos usuários do sistema web;
- sessão persistida no armazenamento seguro do Android;
- tela principal de viagens e navegação separada para o ponto operacional;
- identificação do motorista pelo CPF do colaborador vinculado ao login;
- veículo, KM, obra e combustível preenchidos a partir dos cadastros web;
- abertura do diário sempre com status "Em andamento";
- bloqueio de uma nova viagem enquanto existir diário aberto;
- finalização separada com hora de chegada e KM final;
- abastecimento opcional com litros, valor unitário e total automático;
- câmera traseira para foto do odômetro e do cupom fiscal;
- histórico dos últimos diários do motorista;
- sequência de entrada, início do intervalo, retorno e saída;
- selfie frontal obrigatória em cada marcação;
- captura do GPS e validação da geocerca cadastrada;
- histórico das marcações do dia;
- identificação única do aparelho e prevenção de duplicidade;
- salvamento local quando a conexão falhar durante o envio;
- fila por usuário, com selfie preservada na área privada do aplicativo;
- sincronização automática ao abrir, voltar ou atualizar e botão para tentar novamente;
- orientação antes da selfie e aviso quando a precisão do GPS estiver baixa;
- identidade visual azul alinhada ao sistema web.

## Funcionamento offline

O aplicativo primeiro captura GPS e selfie e tenta enviar a marcação. Se a
comunicação falhar, salva o registro no aparelho com o mesmo identificador
único usado no primeiro envio. Ao sincronizar, o servidor usa esse
identificador para evitar uma marcação duplicada.

Erros de regra do servidor, credenciais ou geocerca não são guardados como
offline, pois precisam ser corrigidos antes de uma nova tentativa.

A abertura e a finalização do Diário de Bordo exigem conexão, pois o servidor
precisa validar em tempo real se o motorista ou o veículo já possui uma viagem
em andamento.

## Desenvolvimento

Emulador Android, com o Flask executando no mesmo computador:

```powershell
flutter run
```

Celular físico conectado à mesma rede do computador:

```powershell
flutter run --dart-define=API_BASE_URL=http://192.168.1.11:5000/api/mobile
```

Produção:

```powershell
flutter build apk --release --dart-define=API_BASE_URL=https://seudominio.com/api/mobile
```
