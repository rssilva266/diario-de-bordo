import 'package:flutter/foundation.dart';

import '../models/user_model.dart';
import '../services/api_client.dart';
import '../services/api_exception.dart';
import '../services/auth_service.dart';
import '../services/auth_storage.dart';

enum SessionStatus { carregando, autenticado, desautenticado }

class SessionController extends ChangeNotifier {
  SessionController({
    required ApiClient apiClient,
    required this._authStorage,
  })  : _apiClient = apiClient,
        _authService = AuthService(apiClient);

  final ApiClient _apiClient;
  final AuthStorage _authStorage;
  final AuthService _authService;

  SessionStatus status = SessionStatus.carregando;
  UserModel? usuario;
  bool enviandoLogin = false;
  String? erroLogin;

  ApiClient get apiClient => _apiClient;

  Future<String> obterDispositivoId() {
    return _authStorage.obterDispositivoId();
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
    enviandoLogin = true;
    erroLogin = null;
    notifyListeners();

    try {
      final resultado = await _authService.login(
        usuario: usuario.trim(),
        senha: senha,
      );
      _apiClient.token = resultado.token;
      await _authStorage.salvarToken(resultado.token);
      this.usuario = resultado.usuario;
      status = SessionStatus.autenticado;
      return true;
    } on ApiException catch (erro) {
      erroLogin = erro.message;
      return false;
    } catch (_) {
      erroLogin = 'Não foi possível entrar. Tente novamente.';
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
    erroLogin = 'Sua sessão expirou. Entre novamente.';
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
