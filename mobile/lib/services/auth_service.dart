import '../models/user_model.dart';
import 'api_client.dart';

class LoginResult {
  const LoginResult({required this.token, required this.usuario});

  final String token;
  final UserModel usuario;
}

class AuthService {
  const AuthService(this._apiClient);

  final ApiClient _apiClient;

  Future<LoginResult> login({
    required String usuario,
    required String senha,
  }) async {
    final json = await _apiClient.post(
      '/auth/login',
      body: {'usuario': usuario, 'senha': senha},
    );

    return LoginResult(
      token: json['token'] as String,
      usuario: UserModel.fromJson({
        ...(json['usuario'] as Map<String, dynamic>),
        'colaborador_vinculado': json['colaborador_vinculado'],
      }),
    );
  }

  Future<UserModel> usuarioAtual() async {
    final json = await _apiClient.get('/auth/me');
    return UserModel.fromJson({
      ...(json['usuario'] as Map<String, dynamic>),
      'colaborador_vinculado': json['colaborador_vinculado'],
    });
  }
}
