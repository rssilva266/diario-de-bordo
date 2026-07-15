import 'dart:math';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthStorage {
  static const _tokenKey = 'mobile_auth_token';
  static const _deviceIdKey = 'mobile_device_id';
  static const _storage = FlutterSecureStorage();

  Future<String?> lerToken() => _storage.read(key: _tokenKey);

  Future<void> salvarToken(String token) {
    return _storage.write(key: _tokenKey, value: token);
  }

  Future<void> limparToken() => _storage.delete(key: _tokenKey);

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
