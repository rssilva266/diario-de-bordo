import 'package:flutter/foundation.dart';

import '../models/user_model.dart';
import '../services/api_client.dart';
import '../services/api_exception.dart';
import '../services/auth_service.dart';
import '../services/auth_storage.dart';

enum SessionStatus { carregando, autenticado, desautenticado }

enum LoginErrorType { credenciais, rede, servidor, desconhecido }

class SessionController extends ChangeNotifier {
  SessionController({required ApiClient apiClient, required this._authStorage})
    : _apiClient = apiClient,
      _authService = AuthService(apiClient);

  final ApiClient _apiClient;
  final AuthStorage _authStorage;
  final AuthService _authService;

  SessionStatus status = SessionStatus.carregando;
  UserModel? usuario;
  bool enviandoLogin = false;
  String? erroLogin;
  LoginErrorType? tipoErroLogin;

  ApiClient get apiClient => _apiClient;

  Future<String> obterDispositivoId() {
    return _authStorage.obterDispositivoId();
  }

  Future<String?> obterUltimoUsuario() {
    return _authStorage.lerUltimoUsuario();
  }

  void limparErroLogin() {
    if (erroLogin == null && tipoErroLogin == null) return;
    erroLogin = null;
    tipoErroLogin = null;
    notifyListeners();
  }

  Future<void> restaurarSessao() async {
    final token = await _authStorage.lerToken();
    if (token == null || token.isEmpty) {
      status = SessionStatus.desautenticado;
      notifyListeners();
      return;
    }

    _apiClient.token = token;

    try {
      usuario = await _authService.usuarioAtual();
      status = SessionStatus.autenticado;
    } catch (_) {
      await _limparSessao();
    }
    notifyListeners();
  }

  Future<bool> login({required String usuario, required String senha}) async {
    final usuarioLimpo = usuario.trim();

    enviandoLogin = true;
    erroLogin = null;
    tipoErroLogin = null;
    notifyListeners();

    try {
      final resultado = await _authService.login(
        usuario: usuarioLimpo,
        senha: senha,
      );
      _apiClient.token = resultado.token;
      await _authStorage.salvarToken(resultado.token);
      await _authStorage.salvarUltimoUsuario(usuarioLimpo);
      this.usuario = resultado.usuario;
      status = SessionStatus.autenticado;
      return true;
    } on ApiException catch (erro) {
      if (erro.networkFailure) {
        tipoErroLogin = LoginErrorType.rede;
        erroLogin =
            'N\u00E3o foi poss\u00EDvel conectar ao servidor. Verifique sua internet.';
      } else if (erro.statusCode == 401) {
        tipoErroLogin = LoginErrorType.credenciais;
        erroLogin = 'Usu\u00E1rio ou senha inv\u00E1lidos.';
      } else if ((erro.statusCode ?? 0) >= 500) {
        tipoErroLogin = LoginErrorType.servidor;
        erroLogin =
            'O servi\u00E7o est\u00E1 temporariamente indispon\u00EDvel. Tente novamente.';
      } else {
        tipoErroLogin = LoginErrorType.desconhecido;
        erroLogin = erro.message;
      }
      return false;
    } catch (_) {
      tipoErroLogin = LoginErrorType.desconhecido;
      erroLogin = 'N\u00E3o foi poss\u00EDvel entrar. Tente novamente.';
      return false;
    } finally {
      enviandoLogin = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    status = SessionStatus.carregando;
    notifyListeners();
    await _limparSessao();
    notifyListeners();
  }

  Future<void> sessaoExpirada() async {
    await _limparSessao();
    tipoErroLogin = LoginErrorType.desconhecido;
    erroLogin = 'Sua sess\u00E3o expirou. Entre novamente.';
    notifyListeners();
  }

  Future<void> _limparSessao() async {
    _apiClient.token = null;
    usuario = null;
    await _authStorage.limparToken();
    status = SessionStatus.desautenticado;
  }

  @override
  void dispose() {
    _apiClient.close();
    super.dispose();
  }
}
