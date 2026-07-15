import 'package:flutter/material.dart';

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
      backgroundColor: AppColors.navy,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(24, 32, 24, 24 + bottomInset),
              child: ConstrainedBox(
                constraints: BoxConstraints(minHeight: constraints.maxHeight - 56),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Align(
                            alignment: Alignment.centerLeft,
                            child: BrandMark(size: 70),
                          ),
                          const SizedBox(height: 28),
                          Text(
                            'Diário de Bordo',
                            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.6,
                                ),
                          ),
                          const SizedBox(height: 8),
                          const Text(
                            'Acesse sua conta para iniciar o trabalho.',
                            style: TextStyle(
                              color: Color(0xFFB7C0CC),
                              fontSize: 16,
                            ),
                          ),
                          const SizedBox(height: 34),
                          TextFormField(
                            controller: _usuarioController,
                            textInputAction: TextInputAction.next,
                            autocorrect: false,
                            autofillHints: const [AutofillHints.username],
                            onFieldSubmitted: (_) => _senhaFocus.requestFocus(),
                            decoration: const InputDecoration(
                              labelText: 'Usuário',
                              prefixIcon: Icon(Icons.person_outline),
                            ),
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Informe seu usuário.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 14),
                          TextFormField(
                            controller: _senhaController,
                            focusNode: _senhaFocus,
                            obscureText: !_mostrarSenha,
                            textInputAction: TextInputAction.done,
                            autofillHints: const [AutofillHints.password],
                            onFieldSubmitted: (_) => _entrar(),
                            decoration: InputDecoration(
                              labelText: 'Senha',
                              prefixIcon: const Icon(Icons.lock_outline),
                              suffixIcon: IconButton(
                                tooltip: _mostrarSenha ? 'Ocultar senha' : 'Mostrar senha',
                                onPressed: () {
                                  setState(() => _mostrarSenha = !_mostrarSenha);
                                },
                                icon: Icon(
                                  _mostrarSenha
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
                            animation: widget.sessionController,
                            builder: (context, _) {
                              final erro = widget.sessionController.erroLogin;
                              if (erro == null) return const SizedBox(height: 22);

                              return Padding(
                                padding: const EdgeInsets.only(top: 14, bottom: 14),
                                child: Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Icon(
                                      Icons.error_outline,
                                      color: Color(0xFFFCA5A5),
                                      size: 20,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        erro,
                                        style: const TextStyle(
                                          color: Color(0xFFFCA5A5),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            },
                          ),
                          AnimatedBuilder(
                            animation: widget.sessionController,
                            builder: (context, _) {
                              final enviando = widget.sessionController.enviandoLogin;
                              return FilledButton(
                                onPressed: enviando ? null : _entrar,
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
                          const SizedBox(height: 12),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
