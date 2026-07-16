import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthStorage {
  static const _tokenKey = 'mobile_auth_token';
  static const _deviceIdKey = 'mobile_device_id';
  static const _lastUsernameKey = 'mobile_last_username';
  static const _storage = FlutterSecureStorage();

  Future<String?> lerToken() => _storage.read(key: _tokenKey);

  Future<void> salvarToken(String token) {
    return _storage.write(key: _tokenKey, value: token);
  }

  Future<void> limparToken() => _storage.delete(key: _tokenKey);

  Future<String?> lerUltimoUsuario() {
    return _storage.read(key: _lastUsernameKey);
  }

  Future<void> salvarUltimoUsuario(String usuario) {
    return _storage.write(key: _lastUsernameKey, value: usuario);
  }

  Future<String> obterDispositivoId() async {
    final existente = await _storage.read(key: _deviceIdKey);
    if (existente != null && existente.isNotEmpty) return existente;

    final random = Random.secure();
    final novoId = List.generate(
      32,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();

    await _storage.write(key: _deviceIdKey, value: novoId);
    return novoId;
  }
}
