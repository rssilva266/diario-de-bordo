import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../core/config/app_config.dart';
import 'api_exception.dart';

class ApiClient {
  ApiClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  String? token;

  Future<Map<String, dynamic>> get(String path) async {
    return _send('GET', path);
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Map<String, dynamic>? body,
  }) async {
    return _send('POST', path, body: body);
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required String filePath,
  }) async {
    return postMultipartFiles(
      path,
      fields: fields,
      files: {fileField: filePath},
    );
  }

  Future<Map<String, dynamic>> postMultipartFiles(
    String path, {
    required Map<String, String> fields,
    Map<String, String> files = const {},
  }) async {
    final uri = Uri.parse('${AppConfig.apiBaseUrl}$path');
    final request = http.MultipartRequest('POST', uri)
      ..headers['Accept'] = 'application/json'
      ..fields.addAll(fields);

    for (final entry in files.entries) {
      if (entry.value.isNotEmpty) {
        request.files.add(
          await http.MultipartFile.fromPath(entry.key, entry.value),
        );
      }
    }

    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    try {
      final streamed = await _client
          .send(request)
          .timeout(AppConfig.requestTimeout);
      final response = await http.Response.fromStream(streamed);
      return _decodeResponse(response);
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(
        'O servidor demorou para responder. Tente novamente.',
        networkFailure: true,
      );
    } on SocketException {
      throw const ApiException(
        'Não foi possível conectar ao servidor. Verifique sua internet.',
        networkFailure: true,
      );
    } on FormatException {
      throw const ApiException('O servidor retornou uma resposta inválida.');
    } on http.ClientException {
      throw const ApiException(
        'Falha de comunicação com o servidor.',
        networkFailure: true,
      );
    }
  }

  Future<Map<String, dynamic>> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
  }) async {
    final uri = Uri.parse('${AppConfig.apiBaseUrl}$path');
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    try {
      final response = switch (method) {
        'GET' => await _client
            .get(uri, headers: headers)
            .timeout(AppConfig.requestTimeout),
        'POST' => await _client
            .post(
              uri,
              headers: headers,
              body: jsonEncode(body ?? <String, dynamic>{}),
            )
            .timeout(AppConfig.requestTimeout),
        _ => throw UnsupportedError('Método HTTP não suportado: $method'),
      };

      return _decodeResponse(response);
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(
        'O servidor demorou para responder. Tente novamente.',
        networkFailure: true,
      );
    } on SocketException {
      throw const ApiException(
        'Não foi possível conectar ao servidor. Verifique sua internet.',
        networkFailure: true,
      );
    } on FormatException {
      throw const ApiException('O servidor retornou uma resposta inválida.');
    } on http.ClientException {
      throw const ApiException(
        'Falha de comunicação com o servidor.',
        networkFailure: true,
      );
    }
  }

  Map<String, dynamic> _decodeResponse(http.Response response) {
    final decoded = response.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        decoded['erro'] as String? ?? 'Não foi possível concluir a operação.',
        statusCode: response.statusCode,
      );
    }

    return decoded;
  }

  void close() => _client.close();
}
