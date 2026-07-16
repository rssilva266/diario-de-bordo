import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../controllers/session_controller.dart';
import '../core/theme/app_colors.dart';
import '../widgets/brand_mark.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({required this.sessionController, super.key});

  final SessionController sessionController;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _usuarioController = TextEditingController();
  final _senhaController = TextEditingController();
  final _senhaFocus = FocusNode();

  bool _mostrarSenha = false;
  String _versao = '1.0.0';

  @override
  void initState() {
    super.initState();
    _carregarDadosLocais();
  }

  Future<void> _carregarDadosLocais() async {
    final ultimoUsuario = await widget.sessionController.obterUltimoUsuario();
    final packageInfo = await PackageInfo.fromPlatform();

    if (!mounted) return;

    if (ultimoUsuario != null && ultimoUsuario.isNotEmpty) {
      _usuarioController.text = ultimoUsuario;
    }

    setState(() => _versao = packageInfo.version);
  }

  @override
  void dispose() {
    _usuarioController.dispose();
    _senhaController.dispose();
    _senhaFocus.dispose();
    super.dispose();
  }

  Future<void> _entrar() async {
    FocusScope.of(context).unfocus();
    if (!_formKey.currentState!.validate()) return;

    await widget.sessionController.login(
      usuario: _usuarioController.text,
      senha: _senhaController.text,
    );
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: EdgeInsets.only(bottom: bottomInset),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight),
                child: Column(
                  children: [
                    const _BrandHeader(),
                    Transform.translate(
                      offset: const Offset(0, -34),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 420),
                          child: Column(
                            children: [
                              _LoginPanel(
                                formKey: _formKey,
                                usuarioController: _usuarioController,
                                senhaController: _senhaController,
                                senhaFocus: _senhaFocus,
                                mostrarSenha: _mostrarSenha,
                                onToggleSenha: () {
                                  setState(
                                    () => _mostrarSenha = !_mostrarSenha,
                                  );
                                },
                                onEntrar: _entrar,
                                sessionController: widget.sessionController,
                              ),
                              const SizedBox(height: 18),
                              Text(
                                'Motriva Fleet  \u00B7  v$_versao',
                                style: const TextStyle(
                                  color: AppColors.muted,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                              const SizedBox(height: 24),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.navy,
      padding: const EdgeInsets.fromLTRB(24, 38, 24, 66),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              BrandMark(size: 62),
              SizedBox(height: 22),
              Text(
                'Motriva Fleet',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 30,
                  height: 1.08,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.8,
                ),
              ),
              SizedBox(height: 9),
              Text(
                'Sua frota e sua opera\u00E7\u00E3o em movimento.',
                style: TextStyle(
                  color: Color(0xFFB9C7DA),
                  fontSize: 15,
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LoginPanel extends StatelessWidget {
  const _LoginPanel({
    required this.formKey,
    required this.usuarioController,
    required this.senhaController,
    required this.senhaFocus,
    required this.mostrarSenha,
    required this.onToggleSenha,
    required this.onEntrar,
    required this.sessionController,
  });

  final GlobalKey<FormState> formKey;
  final TextEditingController usuarioController;
  final TextEditingController senhaController;
  final FocusNode senhaFocus;
  final bool mostrarSenha;
  final VoidCallback onToggleSenha;
  final Future<void> Function() onEntrar;
  final SessionController sessionController;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(22, 24, 22, 22),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.border),
        borderRadius: BorderRadius.circular(10),
        boxShadow: const [
          BoxShadow(
            color: Color(0x180F172A),
            blurRadius: 24,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: AutofillGroup(
        child: Form(
          key: formKey,
          onChanged: sessionController.limparErroLogin,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Bem-vindo',
                style: TextStyle(
                  color: AppColors.ink,
                  fontSize: 23,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 5),
              const Text(
                'Acesse sua conta para continuar.',
                style: TextStyle(color: AppColors.muted, fontSize: 14),
              ),
              const SizedBox(height: 24),
              TextFormField(
                controller: usuarioController,
                textInputAction: TextInputAction.next,
                autocorrect: false,
                enableSuggestions: false,
                autofillHints: const [AutofillHints.username],
                onFieldSubmitted: (_) => senhaFocus.requestFocus(),
                decoration: const InputDecoration(
                  labelText: 'Usu\u00E1rio',
                  prefixIcon: Icon(Icons.person_outline),
                ),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return 'Informe seu usu\u00E1rio.';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 14),
              TextFormField(
                controller: senhaController,
                focusNode: senhaFocus,
                obscureText: !mostrarSenha,
                textInputAction: TextInputAction.done,
                autocorrect: false,
                enableSuggestions: false,
                autofillHints: const [AutofillHints.password],
                onFieldSubmitted: (_) => onEntrar(),
                decoration: InputDecoration(
                  labelText: 'Senha',
                  prefixIcon: const Icon(Icons.lock_outline),
                  suffixIcon: IconButton(
                    tooltip: mostrarSenha ? 'Ocultar senha' : 'Mostrar senha',
                    onPressed: onToggleSenha,
                    icon: Icon(
                      mostrarSenha
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                    ),
                  ),
                ),
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Informe sua senha.';
                  }
                  return null;
                },
              ),
              AnimatedBuilder(
                animation: sessionController,
                builder: (context, _) {
                  final erro = sessionController.erroLogin;
                  if (erro == null) return const SizedBox(height: 22);

                  return Padding(
                    padding: const EdgeInsets.only(top: 14, bottom: 14),
                    child: _LoginErrorPanel(
                      message: erro,
                      type: sessionController.tipoErroLogin,
                      onRetry: onEntrar,
                    ),
                  );
                },
              ),
              AnimatedBuilder(
                animation: sessionController,
                builder: (context, _) {
                  final enviando = sessionController.enviandoLogin;
                  return FilledButton(
                    onPressed: enviando ? null : onEntrar,
                    child: enviando
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              color: Colors.white,
                              strokeWidth: 2.5,
                            ),
                          )
                        : const Text('Entrar'),
                  );
                },
              ),
              const SizedBox(height: 18),
              const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.verified_user_outlined,
                    color: AppColors.muted,
                    size: 16,
                  ),
                  SizedBox(width: 7),
                  Text(
                    'Conex\u00E3o protegida',
                    style: TextStyle(color: AppColors.muted, fontSize: 12),
                  ),
                ],
              ),
              const SizedBox(height: 9),
              const Text(
                'Problemas de acesso? Fale com o administrador da sua empresa.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: AppColors.muted,
                  fontSize: 11,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LoginErrorPanel extends StatelessWidget {
  const _LoginErrorPanel({
    required this.message,
    required this.type,
    required this.onRetry,
  });

  final String message;
  final LoginErrorType? type;
  final Future<void> Function() onRetry;

  bool get _podeTentarNovamente {
    return type == LoginErrorType.rede || type == LoginErrorType.servidor;
  }

  String get _title {
    return switch (type) {
      LoginErrorType.credenciais => 'Acesso n\u00E3o autorizado',
      LoginErrorType.rede => 'Sem conex\u00E3o',
      LoginErrorType.servidor => 'Servidor indispon\u00EDvel',
      _ => 'N\u00E3o foi poss\u00EDvel entrar',
    };
  }

  IconData get _icon {
    return switch (type) {
      LoginErrorType.rede => Icons.wifi_off_outlined,
      LoginErrorType.servidor => Icons.cloud_off_outlined,
      _ => Icons.error_outline,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1F2),
        border: Border.all(color: const Color(0x44EF4444)),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(_icon, color: AppColors.danger, size: 20),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _title,
                  style: const TextStyle(
                    color: AppColors.ink,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  message,
                  style: const TextStyle(
                    color: AppColors.inkSoft,
                    fontSize: 12,
                    height: 1.35,
                  ),
                ),
                if (_podeTentarNovamente) ...[
                  const SizedBox(height: 7),
                  TextButton.icon(
                    onPressed: onRetry,
                    style: TextButton.styleFrom(
                      foregroundColor: AppColors.primaryDark,
                      padding: EdgeInsets.zero,
                      minimumSize: const Size(0, 32),
                      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    ),
                    icon: const Icon(Icons.refresh, size: 17),
                    label: const Text('Tentar novamente'),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
